# ADR-0012: Resource governance via GPU-first subagents, a VRAM-budget placer, a soft CPU/RAM budget

- **Status:** Accepted (Slice 8.5 CI-half design; user-directed, 2026-07-01)
- **Date:** 2026-07-01
- **Revises:** [ADR-0007](ADR-0007-model-manager-inference.md) (Model Manager v1),
  [ADR-0010](ADR-0010-subagents.md) decisions 6-7 (subagents = CPU-only) and its 2026-07-01 addendum.

## Context

Slice 8.5 (docs/ROADMAP.md) revises two pure-core ports **before** the Slice 11 swap builds on
them. It is the same "design the interface around the rule from day one; retrofitting is a rewrite"
logic as the one hard rule. Two user-directed corrections drive it:

1. **Subagents are GPU-first, CPU-overflow (not CPU-only).** ADR-0010 dec 6-7 spent the whole GPU on
   the cortex and ran every subagent on CPU. The user's revision: fit each spawn onto the GPU when
   the VRAM soft cap has headroom, spilling to CPU only when it does not. This makes the
   `ModelManager`'s VRAM accounting real. Today `CORTEX_VRAM_SOFT_CAP_GB` (14 GB, ADR-0004) is
   documentation, not an enforced knob.
2. **Container-scoped resource caps so the machine stays usable.** A soft budget bounds how much
   CPU/RAM admitted subagents may commit, so a spawn burst never starves the user's foreground.

Feasibility of every cap was adversarially verified (2026-07-01 research in [[resource-governance-wsl2]]).
The **decisive constraint: there is no per-process GPU-compute-utilization cap on this stack**. MIG
is absent on consumer/laptop GPUs, MPS is unusable under WSL2, and `nvidia-smi` clock/power knobs
are host-only + whole-GPU. So "limit the GPU" is **not a driver knob**; it is modeled as the VRAM
fit-test (which bounds GPU concurrency) plus, if ever needed, a scheduler concurrency policy. The
user's locked decisions: per-subagent CPU via docker `--cpus` (elastic quota); the global CPU/RAM
ceiling enforced **softly** by the scheduler's admission budget (**no `.wslconfig`, no parent cgroup,
no hard WSL limits**); the host-side GPU clock clamp **dropped**.

Constraints unchanged from prior slices: the hard rule (no state in a model process), gate 2 (100%
line+branch **without a GPU**), gate 1 (≤ 300 lines/file), ports-before-adapters, extensibility-first
design. The **real**
dual-endpoint `llama-server` processes, `-ngl` flags, and per-container cgroup caps are the **host +
Slice-11 half**. They sit behind these ports, never in them.

## Decisions

1. **`ModelManager` (and `acquire`) is UNCHANGED; placement is a NEW `SubagentPlacer` port.** ADR-0010
   dec 6 established that the GPU (exclusive lease) and the subagent pool (bounded admission) are
   different resources behind different ports, "composed at the orchestrator, not merged." VRAM
   placement is a **third** contract (a fit-test that reserves headroom and decides GPU-vs-CPU), so
   by the same logic it is its own port, not a fattening of `ModelManager`. Interface Segregation:
   `SingleResidentModelManager` (the cortex lease) and Slice 11's process-lifecycle manager keep
   `acquire(model) -> ModelLease` with **zero change** and **no raising placement stubs**. The
   ROADMAP's prose "the ModelManager becomes a VRAM-budget accountant" is realized as this dedicated
   port under the same responsibility, which the swap orchestrator composes with `acquire` (Slice 11).

   ```python
   class SubagentPlacer(Protocol):
       def place(self, request: PlacementRequest) -> Placement: ...
       def release(self, placement: Placement) -> None: ...
   ```

2. **`VramBudgetPlacer` is the pure VRAM-budget accountant.** It owns a live ledger of GPU-placed
   subagent VRAM and fit-tests each spawn against the policy cap, **not** llama.cpp `--fit`, which
   sizes to *free* VRAM, not the soft cap. The formula:

   ```
   headroom = soft_cap_gb − cortex_reservation_gb − placed_gb
   place(request):  vram_gb ≤ headroom  →  GPU (reserve vram_gb, -ngl 99)
                    else                →  CPU (reserve nothing,  -ngl 0)
   ```

   The **whole** model goes on GPU or CPU, with no partial straddle for a 2-4B (verified
   worst-of-both-worlds). "Bigger subagents up to ~4B when it fits" is emergent: nothing caps
   `vram_gb` but headroom, so a larger model fits when the pool is empty and overflows as `placed_gb`
   rises. `place`/`release` are **synchronous and lock-free**: with no `await` inside, a coroutine's
   read-modify-write of `placed_gb` runs to completion without interleaving (single-threaded asyncio
   atomicity), so the concurrent-batch spawns (`asyncio.gather`, ADR-0010 addendum) race the headroom
   correctly with no lock. The VRAM fit-test **is** the GPU-concurrency limiter: with ~2.7 GB headroom
   (14 GB cap − ~11.3 GB cortex) and ~2 GB/subagent, at most one subagent lands on GPU and the rest
   spill to CPU, so **no separate `max_gpu_subagents` knob** (it would be a second dial for the same
   constraint; the user lowers the cap or raises the reservation to reserve more). A future
   compute-contention cap slots in behind this port if host measurement demands it.

3. **Placement value types** (`cortex_core/placement.py`, importing no ports as in `subagents.py`):

   ```python
   class PlacementTarget(Enum):        # GPU = "gpu" (-ngl 99);  CPU = "cpu" (-ngl 0)
       @property
       def ngl(self) -> int: ...       # GPU → 99, CPU → 0 (the number the host server-start uses)
   PlacementRequest(model, vram_gb, cpus, memory_gb)   # frozen; __post_init__ asserts all > 0
   Placement(target: PlacementTarget, reserved_gb: float)   # reserved_gb = vram_gb on GPU else 0.0
   ```

   `Placement` carries `reserved_gb` so `release` is exact and self-contained (no back-reference to
   the request). `ngl` is derived from `target` (they are isomorphic, so no redundant field). The
   endpoint is **not** on `Placement`: the runner routes by `target` (decision 6), keeping the placer
   pure VRAM policy with no endpoint knowledge.

4. **`SubagentScheduler.admit` gains a two-dimensional soft CPU/RAM budget.** `admit(request)` (was
   `admit()`) reserves the request's `cpus`/`memory_gb` against summed soft targets; over budget the
   spawn **waits** (an `asyncio.Condition`; depth-1 guarantees no spawn waits on another spawn, so it
   cannot deadlock), matching the user's "soft budget, not a hard wall." A charge larger than the
   whole budget is a config error that could wait forever, so it raises `ValueError` up front (the
   only guard; a well-formed charge always eventually fits as peers release). This delivers ADR-0010
   dec 6's deferred "hard RAM-ceiling rejection" as soft-budget-with-loud-rejection-of-the-impossible.
   `ConcurrencyScheduler` (the bare counting semaphore) is **replaced** by `ResourceBudgetScheduler`;
   its `admit()` no longer satisfies the revised port, and the two-dimensional budget subsumes the
   `max_concurrency` count.

5. **The runner composes the two ports; no VRAM is held while waiting.** `SubagentRunner.run` orders
   **admit (CPU/RAM, may wait) OUTER → place (VRAM, sync, instant) INNER → release in `finally`**:

   ```python
   async with self._scheduler.admit(self._request):          # waits on the soft budget
       placement = self._placer.place(self._request)          # sync fit-test, cannot block
       try:
           backend = self._backends[placement.target]         # route to GPU or CPU (decision 6)
           ... existing load-task + stream_tool_loop body ...
       finally:
           self._placer.release(placement)
   ```

   Because `place` runs only after admission and never blocks, the "reserved VRAM then no CPU slot"
   leak is **impossible by construction**. No rollback path exists. Admission charges the request's
   full `cpus`/`memory_gb` regardless of where it lands (conservative; a GPU placement barely touches
   host CPU, so this over-charges safely). Placement-aware charging is a later refinement behind the
   unchanged `admit(request)`. The existing failure contract is preserved exactly: a missing task or an
   `InferenceError` still becomes an `ok=False` `SubagentResult` (no new failure branches).

6. **A placement reaches inference via two backends selected by `target`. `InferenceBackend` and the
   proto are untouched.** `LlamaCppBackend.stream` resolves its endpoint from its own manager's lease
   (backend.py:148); it takes no endpoint argument. Rather than make one backend's `acquire` return
   different endpoints per placement (a racy `last_endpoint` reconciliation), the runner holds
   `backends: Mapping[PlacementTarget, InferenceBackend]`, a GPU backend (over the GPU sidecar) and a
   CPU backend (over the CPU sidecar), and selects `backends[placement.target]`. Each backend keeps
   the unchanged `SingleResidentModelManager`/lease mechanism. `stream`'s signature and
   `proto/body.proto` do not change. In CI the subagent path is off; tests route both branches through
   fakes.

7. **The ledgers are live-resource state, categorically NOT the durable state the hard rule governs.**
   `placed_gb` (GB on the GPU now) and `cpu_used`/`mem_used_gb` (container shares admitted now) are
   semaphore counts denominated in resources, in the same class as the `asyncio.Lock`
   `SingleResidentModelManager` already holds and the `Semaphore` the old scheduler held (both accepted
   pure-core state). They carry **no** conversation/task/message/output content, are keyed by nothing,
   are constructed at zero, mutated only by their single owning object under the reserve/release
   lifecycle, and are **never persisted**. Losing them on a model swap is **correct, not a violation**:
   an evicted model's VRAM is physically freed and its containers are gone, so the accurate post-swap
   ledger *is* zero, and persisting it would be the bug (it would claim VRAM no live process holds).
   Contrast the `TaskStore`: a task lost on swap **is** a bug, because the work still needs doing. The
   hard rule forbids state that must **outlive** a swap from living in a model; these ledgers are state
   that a swap **invalidates and rebuilds around**, like a lock or a connection pool. The durable path
   (task in Redis, conversation in the store) is untouched.

8. **Opt-in unchanged; CI-default is byte-for-byte the current behavior.** `CORTEX_SUBAGENTS_BACKEND`
   defaults to `none`, so `build_subagents` returns `None` and no placer/scheduler is constructed at
   runtime, so the GPU-less dev loop and CI run exactly as before. The pure `VramBudgetPlacer` /
   `ResourceBudgetScheduler` are exercised only by core unit tests, 100% line+branch without a GPU.

## Consequences

CI-half increments (each small, green under `just check`, no GPU):

1. **Placement values + revised ports** are `placement.py` (`PlacementTarget`/`PlacementRequest`/
   `Placement`), the `SubagentPlacer` port, and `SubagentScheduler.admit(request)`; `ModelManager`
   untouched.
2. **Pure impls + contract tests.** `VramBudgetPlacer` (`placer.py`) and `ResourceBudgetScheduler`
   (replacing `ConcurrencyScheduler` in `scheduler.py`), each the reference impl its Slice-11 adapter
   must re-satisfy, covered 100% via pure arithmetic + asyncio primitives.
3. **Runner composition + routing.** `SubagentRunner` gains `backends`/`placer`/`request`, composes
   admit→place→release, and routes by target; existing subagent behavior preserved (the Slice-7 tests
   are the guard).
4. **Wiring + config.** `build_subagents` builds the placer, scheduler, request, and two backends;
   `BrainRuntimeConfig` gains `vram_soft_cap_gb`/`cortex_reservation_gb`, `SubagentsConfig` gains
   `gpu_endpoint` + the per-subagent/budget knobs and drops `max_concurrency`. Docs + ROADMAP.

**Deferred to Slice 11, behind these unchanged ports (additive, no churn):**
- `SubagentScheduler.drain()` quiesces the pool for a swap (evict → load brain → swap back). Adding a
  method is additive; the swap composes `drain` + `release` (subagents) with `acquire` (brain) at the
  orchestrator, never merging the ports.
- **CUDA-OOM → re-place on CPU.** `place` is optimistic; a real CUDA OOM fails loudly at process start.
  Today that surfaces as `ok=False` (the existing contract, no corruption). Auto-recovery (re-issue a
  CPU-forced request) is a Slice-11/host refinement (a real GPU is needed to trigger it; simulating
  one in the pure core to cover a retry branch would be the vacuous coverage AGENTS.md forbids).
- The real process-lifecycle `ModelManager` adapter (the deferred `cortex_model_manager` package,
  ADR-0007) whose `acquire` performs the swap; placement-aware CPU charging; the Intel NPU as a third
  `PlacementTarget` (recorded in
  [refinements/index.md#resource-governance](../refinements/index.md#resource-governance), which since
  2026-07-19 also carries the two feasibility unknowns the ROADMAP used to hold).

**Deferred to the host half (user):** two real `llama-server` sidecars (GPU `-ngl 99` + CPU `-ngl 0`)
in `docker/docker-compose.subagents.yml`; the per-container `--cpus`/`--memory`/`--memory-swap` caps; the
measured `vram_gb`/`cortex_reservation_gb`/budget numbers; real GPU-placed-subagent validation; the
runbook update.

Config gains, at the composition root only: `CORTEX_VRAM_SOFT_CAP_GB`, `CORTEX_VRAM_CORTEX_GB`,
`CORTEX_SUBAGENTS_GPU_ENDPOINT`, `CORTEX_SUBAGENTS_VRAM_GB`, `CORTEX_SUBAGENTS_CPUS`,
`CORTEX_SUBAGENTS_MEMORY_GB`, `CORTEX_SUBAGENTS_CPU_BUDGET`, `CORTEX_SUBAGENTS_MEM_BUDGET_GB`
(replacing `CORTEX_SUBAGENTS_MAX_CONCURRENCY`).

## Risks

- **VRAM-estimate accuracy.** The fit-test trusts a static `vram_gb`; real footprint is weights + KV
  (grows with context) + fragmentation, allocated lazily. Optimistic → CUDA OOM at runtime (degrades
  to `ok=False`, no corruption); pessimistic → spurious CPU overflow. The port is right; the *number*
  is host-tuned in the runbook (the CI/host split).
- **Soft budget is not a wall.** By the user's constraint (no parent cgroup / `.wslconfig`), the
  scheduler bounds only the subagents it admitted; a mis-sized per-container cap, or the cortex/brain
  themselves, can still exceed the intended global ceiling. Deliberate tradeoff; a hard wall remains a
  refinement behind the same port.
- **No GPU-util cap at all.** A single GPU-placed subagent can still spike utilization and stutter the
  foreground; only concurrency + smaller ctx/batch govern it. Accepted, not solved (the stack offers
  no lever, per [[resource-governance-wsl2]]).
- **Pre-existing backend-lock serialization.** `LlamaCppBackend` holds the manager lease for the whole
  stream, so subagents sharing one backend serialize at its lock regardless of the admission budget (a
  Slice-7 property, not introduced here). GPU-first (≈1 GPU subagent) makes it moot on the GPU path;
  genuine CPU-sidecar `--parallel` concurrency is a host-half wiring concern.
- **Float drift.** Repeated `+=`/`-=` on `placed_gb`/`cpu_used` can leave a tiny residue; with coarse
  (0.1 GB) config values it never crosses a boundary. Fixed-precision rounding is a no-interface-impact
  fallback if it ever bites.

## Addendum (2026-07-16): the admission wall refuses as a value; placement-aware charging declined

Two deferrals recorded above closed together on the backlog pass that read them against the tree
([docs/refinements/index.md#resource-governance](../refinements/index.md#resource-governance)): **a hard budget
wall** and **placement-aware CPU charging**. Both entries described themselves as tweaks behind the
same unchanged `SubagentScheduler` port. Neither was, for opposite reasons.

### What the budget charges today, precisely

`admit(request)` sums one number per dimension: `PlacementRequest.cpus` (fractional CPU shares,
the per-container `--cpus`) and `memory_gb` (host RAM, the per-container `--memory`). Both are
static per roster entry, read from config, identical for every spawn of that entry; nothing is
measured. The budget bounds neither wall clock nor tokens nor VRAM (that is the placer's ledger),
only how much simultaneous committed CPU/RAM the scheduler will vouch for. A CPU-placed spawn and a
GPU-placed spawn are charged **the same**, and must be: `SubagentRunner.run` admits *before* it
places (decision 5), so at charge time the target does not exist yet.

Note what "soft" does and does not mean here, because the risk paragraph above blurs it. With
respect to what it charges the budget is already **hard**: a waiting spawn holds none of it, and
nothing is admitted past the targets. "Soft" means only that it binds nothing it did not admit
(the cortex, the brain container, a mis-sized container cap), which is a statement about cgroups,
not about this port.

### Placement-aware CPU charging: declined

1. **The port cannot express it.** `admit` takes a `PlacementRequest`, which carries no placement,
   and is entered before `place` runs. A placement-aware charge therefore needs either a port
   change (a target argument, or an `admit` that yields a re-chargeable handle) or the
   admit/place inversion decision 5 exists to prevent: a GPU-placed spawn queuing for a CPU slot
   would hold reserved VRAM while it waits, which is exactly the leak this ADR calls impossible by
   construction. "Behind the same port" was wrong.
2. **The discount would buy nothing.** Charging a GPU placement less admits more spawns at once.
   Same-entry spawns cannot use that concurrency: each roster entry holds one `LlamaCppBackend`
   per target, and `LlamaCppBackend.stream` holds its `SingleResidentModelManager` lock for the
   whole stream, so they serialize there instead. Measured live on the CPU subagent server
   (Qwen3.5-2B, `docker-compose.subagents.yml`): two concurrent spawns took 4.8 s through two
   backend objects and 10.0 s through one shared object, a ratio of 2.08, which is full
   serialization. A larger admission budget would move the queue from the scheduler to that lock.
3. **There is nothing to discount in the shipped wiring.** `CORTEX_SUBAGENTS_VRAM_GB` is set to
   5.5 deliberately above the GPU headroom, so every spawn overflows to CPU today; and at the
   documented 14 GB cap minus roughly 11.3 GB of cortex, at most one subagent is ever GPU-placed.

**Both numbers in item 3 have since been measured away, and the decline stands (2026-08-09).** The
ask is 3.5 GiB against the 5.4 GiB the 14 GB cap leaves beside an 8.6 GiB cortex, so one spawn of
the admitted pair is GPU-placed and the other overflows, and item 2's "they serialize there
instead" holds only for spawns sharing a target: an entry's two lock objects give it two-way
overlap. The discount still buys nothing, because that overlap is capped at two by the lock objects
rather than by the budget, so admitting a third spawn only moves it from the queue onto a lock.

Recorded as declined rather than deferred: it reopens only with the Slice 11 GPU-placed runtime,
which is also when a second GPU-capable executor could make the concurrency real, and it reopens
as a port change, not a tweak.

### The hard wall: the refusal that existed was delivered as a crash

The entry's own words ("bounds only what the scheduler admits") describe hard enforcement over
processes the scheduler never admitted. That is a cgroup/`.wslconfig` capability the user's
locked constraint above rules out, and no implementation of a port that only sees admissions can
supply it. Declined at that reading.

At decision 4's reading ("over budget the spawn **waits** ... matching the user's soft budget, not
a hard wall") the wall is refuse-instead-of-queue, and **one such refusal already existed**: a
charge larger than the whole budget raises rather than waiting forever. Its boundary behaviour was
the defect. It raised a bare `ValueError` out of `SubagentRunner.run`, through
`SpawnSubagentsTool.invoke` and its `asyncio.gather` (taking every sibling subagent's answer with
it), through `CompositeToolRegistry` and `ToolDispatcher`, which catches only `ToolError`, to
`_turn_task`'s deliberately broad handler in `converse.py`, which fails the turn with
`ERROR_CODE_INTERNAL`; and since `_start_next_turn` refuses to start anything once a stream has
failed, the whole `Converse` stream ends there. `SubagentsConfig` never checked an ask against the
budget either, so a deployment could reach that state from env alone. Of the four possible answers
at the boundary, the code implemented the worst.

**Decided, and now implemented:**

- **A transient full budget still queues.** Unchanged, and deliberately so. The work runs seconds
  later, depth-1 guarantees the queue drains, and refusing it would discard a subtask the user
  asked for to save resources that a waiting spawn does not hold anyway. Overturning it is the
  user's call, not a refinement's.
- **An impossible charge is refused as a value.** `ResourceBudgetScheduler.admit` raises the typed
  `SubagentAdmissionError` (documented on the port, so any Slice 11 adapter owes the same
  contract), and `SubagentRunner` degrades exactly that error to an `ok=False` `SubagentResult`
  whose `detail` says it was refused before running, that no retry can fit it, and that the cortex
  should answer without this subtask. That joins "task not found" and "unknown subagent model" as
  the runner's fail-closed outcomes, restoring its contract that every outcome is a persisted
  value. A refused member no longer takes its batch down.
- **The misconfiguration is refused at boot.** `SubagentsConfig` now rejects any roster entry
  (the flat-field default included) whose `cpus`/`memory_gb` exceeds `cpu_budget`/`mem_budget_gb`,
  with equality allowed since such an entry runs alone. A subagent the machine may never run is a
  wiring error, and it belongs with the other two config guards rather than in a tool result.

**Rejected at the boundary:** failing the turn (what the code did, and it discards good work for a
config error); degrading the spawn to CPU (meaningless here, since a CPU placement costs *more*
host CPU, and placement is not the scheduler's to decide); and refusing transiently, above.

**Expressing the difference to the caller.** `SubagentResult` carries `ok` and `detail` only, and
the spawn tool renders a failure as `FAILED: {detail}`, so "refused because full" is distinguished
from "failed" **by its text**, phrased like the dispatcher's `BUDGET_EXHAUSTED_MSG`. A structured
refusal kind on `SubagentResult` is **not** added: nothing would read it (the aggregate is prose
the model consumes, and the seam carries no subagent result), which is the dead-until-a-consumer
test the blended-relevance field failed the same day.

**Neither half depends on measuring GPU utilization**, which this ADR establishes is unavailable on
this stack. The wall counts config numbers; the declined discount would have too.

**Deferred, with triggers, in the backlog:** a **bounded wait** (refuse after N seconds queued)
if a real deployment ever shows a turn stalling in admission long enough to matter, which needs a
timeout design and a `Clock`, not a policy flip; and a **read timeout on the subagent HTTP client**,
which is the actual unbounded-wait hazard here, since `build_subagents` builds
`httpx.Timeout(connect, read=None)` and one wedged `llama-server` stream would hold its admission
forever while every queued peer waits behind it.

## Addendum (2026-07-17): `drain()` landed with the brain handoff

The consequences above deferred `SubagentScheduler.drain()` to Slice 11; ADR-0030 decision 4
designed its semantics and its drain sub-slice has now landed it, additive on the port exactly as
pinned here (composed at the swap conductor, never merging the ports; `admit`'s signature and the
queue-on-transient-fullness policy untouched). What landed, and where it sharpens this ADR's
sketch:

- **`async drain(*, timeout_s) -> bool` plus `undrain()`**, implemented by
  `ResourceBudgetScheduler` and by the new `AdmitAllScheduler` fake, both passing one drain
  contract suite (`test_scheduler_drain.py`). The reversal verb, which neither this ADR nor
  ADR-0030 named, is `undrain`: synchronous and idempotent, owed by the conductor in a `finally`
  on swap-back and aborted handoff alike, which is what makes ADR-0030's chaos criterion ("the
  scheduler is admitting again, drain always released") satisfiable.
- **Refuse, not queue, for the whole window.** From `drain` until `undrain`, every `admit`
  raises the typed `SubagentAdmissionError` with `POOL_DRAINING_MSG` instead of queuing, a
  deliberate divergence from the admission wall's queue-on-transient-fullness philosophy: a
  brain-phase spawn queued against its own drain would deadlock the turn against its own swap.
  A spawn already *waiting* on a full budget when the drain begins is woken and refused rather
  than left to sleep through the handoff and admit into the brain phase on wake (drain
  `notify_all`s the same condition the budget queues on; mutation-proven).
- **The bounded wait reports, it never kills.** `drain` waits for the in-flight count (an int
  beside the float ledgers, so drain-complete detection never trusts float residue) to reach
  zero under `asyncio.timeout`; the conductor passes `CORTEX_SWAP_DRAIN_TIMEOUT_S` (default
  60 s, ADR-0030 config, arriving with the conductor's wiring). On timeout it returns False
  with nothing killed, since v1 never kills a subagent mid-stream: the conductor must abort
  the handoff before anything is evicted, and the window still holds until `undrain`.
- **The runner's refusal text stopped overclaiming.** Its wrapper used to assert every
  admission refusal was a permanent resource-budget misconfiguration, which the drain window
  falsifies; the cause-specific guidance now travels in each raise site's message (the
  impossible charge keeps the misconfiguration diagnosis, the drain window says delegation
  resumes when the handoff ends) under a neutral "refused before running" wrapper.

Validated live as well as over the contract suite: a `ResourceBudgetScheduler.drain` issued
while a real admission held a streaming generation against the compose CPU `llama-server`
(gemma-4-E4B) stayed pending until the stream finished, then resolved clean, with an admit
issued mid-window refused as `POOL_DRAINING_MSG` and admission resuming after `undrain`.

Of this ADR's Slice 11 deferrals, CUDA-OOM re-place and the real GPU-placed runtime stay open
for the model-host sub-slice per ADR-0030's mapping; placement-aware charging stays declined
per the addendum above.

## Addendum (2026-07-18): the re-place landed, and it does not sniff for a CUDA OOM

The consequences above deferred **CUDA-OOM re-place on CPU** to Slice 11 with an explicit
reason: "a real GPU is needed to trigger it; simulating one in the pure core to cover a retry
branch would be the vacuous coverage AGENTS.md forbids." ADR-0030's mapping schedules it into the
model-host sub-slice as "a single CPU re-run after a GPU-placed failure, recorded in the result's
detail", and it has now landed there. Two things this ADR assumed turned out to be wrong, so the
shape differs from the one-liner and the difference is the whole content of this note.

**The trigger is not a CUDA OOM, because on this stack there may not be one.** This ADR says "a
real CUDA OOM fails loudly at process start". Measured on the dev GPU (8 GB card, 8188 MiB)
during this sub-slice's recon: a 14.4 GB GGUF started with `-ngl 99` did **not** fail. llama.cpp
logged `failed to fit params to free device memory: n_gpu_layers already set by user to 99, abort`
and then loaded anyway, reaching a serving `/health` in 176.9 s with 7762 MiB of dedicated VRAM in
use and the remainder spilling to shared system memory, which is WDDM GPU-memory oversubscription
under WSL2. So an over-committed GPU-placed model here loads slowly and serves rather than dying,
and a branch keyed on an OOM would have been a branch that cannot fire: exactly the defect this
ADR was trying to avoid, arrived from the other direction.

**What the retry keys on instead.** Any `AttemptFailure.INFERENCE` from a **GPU** placement, which
is the honest reading of "a GPU-placed failure": the placed backend did not answer. That is
reachable, and reachable for a reason this repo already has written down: ADR-0030's last addendum
records that the swap back restarts each evicted tier best effort, so admission can reopen onto a
GPU subagent server that did not come back, and every spawn placed there fails at its backend.
The re-place is that case's mitigation as well as the OOM's. Sniffing llama-server's text for "out
of memory" was rejected: it is untestable without the real message, and it would narrow a working
recovery to one cause of it.

**The three properties that keep it a re-place rather than a retry loop**, each pinned by a named
test proven fallible by mutation (`test_runner.py` records the measured counts): a malformed
constrained reply does **not** retry, being a property of the model and the prompt rather than of
where it ran; the GPU reservation is released **before** the re-run, in the `finally` that already
existed, so a re-run never misreports headroom to a concurrent spawn (decision 7's ledger is a
live-resource count); and the re-run re-uses the same admission and the same `DispatchBudget`, so
it buys no second CPU/RAM charge (the charge is target independent by design, "a CPU-placed spawn
and a GPU-placed spawn are charged the same, and must be") and cannot spend past the turn's
allowance.

**Two interpretations recorded rather than left to the next reader.** The taint of the two attempts
is **unioned**, because an attempt that read untrusted content before its backend died did consume
it and under-reporting taint costs safety rather than precision. And the core cannot tell whether a
deployment serves both placement targets from one `llama-server`: no port carries an endpoint, by
design, and `CORTEX_SUBAGENTS_GPU_ENDPOINT` still defaults to the CPU server. A deployment that
leaves that default therefore gets a second attempt at the same server, one wasted load on an
already failing path, which is a configuration answer rather than a reason to teach the placement
port about topology.

The refactor this needed is recorded because it changed no behaviour: the streaming half of the
runner moved to `subagent_attempt.py` (`PlacedAttempt`, returning an `AttemptOutcome` instead of
persisting a result), leaving `runner.py` holding the composition. Two attempts of one task cannot
be expressed while "run it" and "store it" are one function, and both files sit well inside the
line cap where one would not have.

## Addendum (2026-07-18): the host half landed, relocated, and its per-model caps are gone

The consequences above deferred a **host half** to the user: "two real `llama-server` sidecars (GPU
`-ngl 99` + CPU `-ngl 0`) in `docker/docker-compose.subagents.yml`; the per-container
`--cpus`/`--memory`/`--memory-swap` caps; the measured `vram_gb`/`cortex_reservation_gb`/budget
numbers; real GPU-placed-subagent validation; the runbook update." Most of it landed with the
model-host sub-slice, and it landed **somewhere else**, which is the content of this note.

**The GPU sidecar is a tier of the model-host supervisor, not a service.** ADR-0030 decision 3 put
the one container that may spawn a model process where the GPU reservation and the models mount
already are, so the GPU-placed subagent executor is a hosted tier on `:8083` with `-ngl 99`, opt-in
behind `CORTEX_MODEL_FILE_SUBAGENT_GPU`. The CPU `-ngl 0` sidecar stays its own container exactly as
this ADR described. Routing is a **separate** setting from hosting:
`CORTEX_SUBAGENTS_GPU_ENDPOINT` still defaults to the CPU server, deliberately, because a
deployment that has named no GPU artifact would otherwise point GPU-placed spawns at a tier that
answers nothing. So opting in is three settings together (the artifact, the endpoint, and the tier's
id in `CORTEX_SWAP_EVICT_MODELS`), written in the gpu override's checklist rather than left implied.

**The caps landed, and they are per container, so they are per supervisor and not per model.** Both
containers carry `cpus`/`mem_limit`/`memswap_limit` (verified applied by the runtime as
`NanoCpus`/`Memory`/`MemorySwap`), and on the CPU subagent container the defaults are the hard twin
of this ADR's soft admission budgets, which is what makes those budgets more than an honour system.
The loss to know about: the cortex, the deep model and the GPU subagent are now **processes in one
cgroup**, so no per-model CPU or RAM cap exists. ADR-0030 wins as the later and more specific
decision, and its own security argument is what buys it, since a per-model cap wants a container per
model, which wants a controller that can start containers, which is the docker-socket shape that
ADR rejected. The values ship as user-tunable placeholders: the 8 GB dev GPU cannot hold a real
tier pair, so what was validated is the mechanism and not the arithmetic. Note that llama.cpp mmaps
the GGUF, so mapped model pages count against the memory cap and a cap below the artifact size makes
a load thrash rather than fail.

**What stays host-side is real GPU-placed-*subagent* validation**, for this ADR's own reason: a
subagent is only ever placed on the GPU when `CORTEX_SUBAGENTS_VRAM_GB` fits under the soft cap
minus the resident cortex, which needs a card that holds the cortex first. The measured `vram_gb`
and budget numbers stay host-side with it. Recorded in
[docs/refinements/index.md#resource-governance](../refinements/index.md#resource-governance) and its
[index](../refinements/index.md) until 2026-07-19, when host-side work was extracted into its own
directory; both this validation and the placeholder cap numbers now live in
[docs/host/index.md#gpu-tier-scale](../host/index.md#gpu-tier-scale), with the sentences above kept verbatim
there and pointer stubs left behind.

## Addendum (2026-07-19): the GPU-placed-subagent validation splits, mechanism here and arithmetic host-side

The host-half addendum above says "**What stays host-side is real GPU-placed-*subagent*
validation**, for this ADR's own reason: a subagent is only ever placed on the GPU when
`CORTEX_SUBAGENTS_VRAM_GB` fits under the soft cap minus the resident cortex, which needs a card
that holds the cortex first." The last clause asserts that the dev GPU does not hold the cortex.
It does: [ADR-0029](ADR-0029-vision-screen-capture.md) measured `gemma-4-12b-it-qat-q4_0.gguf`
resident on the 8 GB card on 2026-07-17 at `-ngl 99 --ctx-size 4096 --parallel 1` **with its
vision projector**, and [ADR-0030](ADR-0030-brain-handoff.md) records the model alone taking 7715
of that card's 8188 MiB.

**What is true instead, and it is narrower.** The card holds the cortex with roughly 470 MiB to
spare, so nothing multi-GB fits *beside* it. A GPU placement **beside a resident cortex**, which is
the arithmetic this ADR budgets for, therefore stays host-side and stays item 6 of
[docs/host/index.md#gpu-tier-scale](../host/index.md#gpu-tier-scale), with the measured `vram_gb` and budget
numbers. The cgroup cap placeholders are unaffected and stay host-side for their own reason, which
is the tier pair.

**What comes back to the agent.** The `VramBudgetPlacer`'s GPU arm has never fired against a real
placement, and firing it needs no resident cortex: the budget is three env values
(`CORTEX_VRAM_SOFT_CAP_GB`, `CORTEX_VRAM_CORTEX_GB`, `CORTEX_SUBAGENTS_VRAM_GB`), the tier is one
small artifact behind `CORTEX_MODEL_FILE_SUBAGENT_GPU` on the supervisor's `:8083`, and
`CORTEX_SUBAGENTS_GPU_ENDPOINT` has to be pointed at it because it defaults to the CPU server. What
that proves is the route from a GPU verdict to an `-ngl 99` process plus the ledger that accounts
for it, which is the same mechanism-versus-tier-scale split the model swap already runs on
([ADR-0030](ADR-0030-brain-handoff.md)). It is recorded as actionable now in
[docs/refinements/index.md](../refinements/index.md), with the reasoning in
[docs/refinements/index.md#resource-governance](../refinements/index.md#resource-governance). Nobody has run it
yet, so the "never fired against a real placement" sentence above stays true until somebody does.

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-08-04): the GPU arm fired, and both verdicts are witnessed against live tiers

Somebody ran it. The sentence the addendum above left standing is retired: the `VramBudgetPlacer`'s
GPU arm has now fired against a real placement, and the arm that overflows to CPU has been shown
firing beside it on the same stack, because an arm that cannot be made to stay silent proves nothing
about the one that fires.

**The stack.** The base file plus the `gpu`, `subagents` and `modelhost-loopback` overrides, models
on the host mount, with the ADR-0004 subagent pick (`gemma-4-E4B` QAT q4_0) hosted twice: as the
sidecar's `-ngl 99` tier on `:8083` (put in the roster by `CORTEX_MODEL_FILE_SUBAGENT_GPU`, started
by hand because the daemon starts only the cortex, READY between 9 s and 12 s after the start
returned in 0.007 s) and as the subagents override's `-ngl 0` CPU server on `:8082`. The tier's argv
was read out of the container rather than assumed: `--model .../gemma-4-E4B_q4_0-it.gguf --port 8083
-ngl 99 --ctx-size 8192 --parallel 2`, beside the cortex tier's own `-ngl 99 --ctx-size 16384
--parallel 1`.

**The GPU verdict.** Soft cap 20 GB (the shipped 14 is a placeholder sized for an 8 GB card),
reservation 11.3 GB, ask 5.5 GB, so the headroom of 8.7 GB holds exactly one spawn. A batch of two
concurrent spawns of one roster entry landed one on each target, which is the ledger and not the
scheduler: both were admitted, and the second was refused the GPU only because the first had already
debited 5.5 GB of an 8.7 GB allowance. The GPU-placed one is visible in the tier's own log as its
only task, 18 prompt tokens at 104.83 tok/s and 4 generated at 81.07 tok/s, 221.05 ms in total; its
sibling took 12536.83 ms on the CPU server. That ratio is the route being real: no arrangement of the
core could make a CPU server answer in 221 ms.

**The CPU verdict, which is the shipped configuration.** With the soft cap left at 14 GB the headroom
is 2.7 GB, under the same 5.5 GB ask, and both spawns overflowed; the GPU tier's task count did not
move. So the deliberate placeholder pairing this ADR ships (an ask above the placeholder headroom) is
confirmed to route nothing at the tier, which is what makes the three-setting opt-in of the host-half
addendum the whole story rather than most of it.

**How it is run, and how it was reddened.** The suite is
`brain/packages/orchestrator/tests/test_subagent_gpu_live.py`, `integration`-marked and therefore
outside CI and the coverage gate, run as two commands against one stack (the arms select themselves
from the budget in the environment); the procedure is
[runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md). It reads the three env values through
`BrainRuntimeConfig` and `SubagentsConfig`, the same settings classes the composition root reads, so
the arm a run takes is the deployment's arithmetic rather than the test's, and it records the target
each spawn was handed because nothing else can: the ledger is private and no log line names a
verdict. Proved able to fail before being trusted, by pointing `CORTEX_SUBAGENTS_GPU_ENDPOINT` at a
closed port under the GPU-arm budget: the placement still happens, the backend does not answer, and
the re-place addendum's single CPU re-run fires, so the run reddens on a third placement with the
runner's "a GPU-placed subagent did not answer" warning in the captured log. That is also the first
time the re-place has fired from a real GPU placement rather than from a failing fake.

**What this does not touch.** The cap numbers of the host-half addendum stay placeholders, and
nothing here re-opens placement-aware charging: one hosted GPU tier is still one backend object per
target per roster entry.

## Addendum (2026-08-04): the fit beside a resident cortex, and what the placeholder numbers cost

The run above kept the 12B cortex resident throughout, which makes it the fit test the host
directory carried as its own item ("a GPU-placed subagent beside a resident cortex"). That item is
closed with this note, and the numbers are the point of it, because **the fit was never a question
about the card**.

**What the two tiers cost, measured with `nvidia-smi` on the development card (24463 MiB).** Nothing
loaded and no containers: 1872 MiB, and 1888 MiB with the stack up and both tiers stopped, so the
supervisor container itself holds nothing measurable. The cortex tier resident (`gemma-4-12b-it-qat-q4_0.gguf`
with its projector, `-ngl 99 --ctx-size 16384 --parallel 1`): 10022 to 10034 MiB of total used, which
is 8146 MiB above that floor. The GPU-placed subagent tier beside it (the E4B pick, `-ngl 99
--ctx-size 8192 --parallel 2`): 13334 to 13405 MiB with both resident, so the tier itself is
3319 MiB. Both resident leaves **11110 MiB free**.

**The arithmetic that refused every placement is the placeholders, not the hardware.** This ADR's
budget ships as a 14 GB soft cap, an 11.3 GB cortex reservation and a 5.5 GB subagent ask, so the
headroom is 2.7 GB and the ask never fits. Measured, the same pair of tiers costs 14.00 GB of total
used (12.02 GB of it above the floor), so the two really do sit at the deliberate cap, while the
placeholder pair claims 16.8 GB for them. Two corrections make it up: the cortex reservation is
about 0.8 GB high against this build of llama.cpp (10.51 GB total used against the 11.3 GB
[ADR-0004](ADR-0004-model-lineup.md) measured for the same tier shape on an older build, so the
reservation is conservative, which is the safe direction for a placer), and the subagent ask is
about 2 GB high (3.48 GB measured). Corrected, the pair fits the shipped cap by hundredths of a GB,
which is too thin to deploy on. **The honest lever is the soft cap itself**, which is a user policy
value (this card keeps roughly 10 of its 24 GB for other work) rather than anything the placer can
decide: the GPU arm above fired under a 20 GB cap, and any cap that leaves the ask under the
headroom will do it.

**Co-residency costs throughput and nothing else.** Generating alone, the cortex ran at
71.82 tok/s and the subagent tier at 96.96 tok/s; generating at the same time, 50.54 and 63.50.
Through the spawn batch itself the cortex answered 339 tokens at 61.71 tok/s and its tier never left
READY. So the "a spawn placed on the GPU that then degrades the cortex" failure this fit test was
written to watch for is a roughly 30% slowdown while both generate, which is contention on one card
and an argument about the cap rather than about the placer, exactly as the item predicted.

**Two halves of the item's own recipe were deliberately not run**, and neither weakens the result.
`CORTEX_SWAP_EVICT_MODELS` was left unset, since what it buys is a handoff stopping this tier before
the deep model loads, which belongs to the tier-scale swap items and needs the overlay that answers
a confirm card. And the spawn came from the live delegation suite invoking the spawn tool directly
as the cortex would, which is the method that item named for itself.

## Addendum (2026-08-07): `SubagentPlacer` learns which residency it is fit-testing against

Decision 2 fixed this port's arithmetic to `soft_cap - cortex_reservation - placed`, which describes
the machine truthfully except during a brain handoff, when the cortex has been evicted and a deep
model holds the card. The port therefore grows two verbs, `charge_handoff(resident_gb=)` and
`charge_standing()`, and `VramBudgetPlacer` fit-tests against a resident term they set rather than
against the constructor's cortex figure. The whole argument, the ordering against the swap's own fit
check, and the live numbers are recorded where the handoff lives, at
[ADR-0030](ADR-0030-brain-handoff.md)'s handoff-window addendum; what belongs here is the port
change itself and its cost, which is that a `SubagentPlacer` implementation now owes two more
methods (a no-op pair is the honest degenerate form for one with no notion of a resident) and that
the protocol moved into `ports_placement.py` for the line cap, re-exported from `ports.py` so no
call site moved.

The sibling this does **not** touch is the admission wall: `SubagentScheduler.admit` still charges
every spawn its full `cpus`/`memory_gb` regardless of placement, and the placement-aware charge stays
declined on the admission-wall addendum's own reasoning, reopening on a second GPU-capable executor.

## Addendum (2026-08-07): the cortex reservation, re-measured at the shipped tier shape

`CORTEX_VRAM_CORTEX_GB` moves from **11.3 to 8.6**. It is the term decision 2 subtracts from the
soft cap on every spawn's fit-test, so it alone decides whether GPU subagent work is reachable, and
until this sitting it had never been measured on the card the deployment runs. The two figures that
questioned it, [ADR-0004](ADR-0004-model-lineup.md)'s own incidental note and the co-residency
measurement at [ADR-0030](ADR-0030-brain-handoff.md), both declined to act: the first because a
text-only start on a different llama.cpp build is not a controlled reading, the second because
lowering the reservation widens what the placer admits and that is this ADR's decision rather than
the handoff's. This is the controlled reading both asked for.

**What was measured.** The tier at its shipped shape, read out of the running child's argv rather
than assumed: `-ngl 99 --ctx-size 16384 --parallel 1 --jinja --mmproj <the gemma-4-12B projector>
--image-max-tokens 1024 --ubatch-size 1024`, started by the model-host sidecar off the read-only
mount on the 24463 MiB card, ready 30.3 s after `start`. `nvidia-smi` total used was sampled every
0.2 to 0.3 s throughout, and every figure below is the min and max of one phase's samples.

| Phase | Total used (MiB) | Above the floor (MiB) |
| --- | --- | --- |
| Floor, stack up and the tier stopped, immediately before the load | 1261 to 1301 (36 samples) | n/a |
| Idle, loaded, no request served yet | 9701 to 9745 | 8400 to 8484 |
| Long-context generation: 13180 prompt tokens, 924 decoded | 9716 to 9721 | 8415 to 8460 |
| One vision turn, a real 1304x1172 overlay screenshot | 9742 to 9805 | 8441 to 8544 |
| Vision on a near-full context, 13003 prompt tokens, repeated 3 times | 9762 to 9832 | 8461 to 8573 |
| Idle again, after the images, no request | 9764 to 9818 | 8463 to 8557 |
| Floor, tier stopped again, after the whole run | 1259 to 1308 (65 samples) | n/a |

**Idle is 8400 to 8484 MiB and the peak is 8573 MiB**, both above the floor. So the tier's whole
range under everything this deployment can send it is a little over 8.3 GiB, against the 11.3 the
placer reserved.

**How the floor was established, for every reading.** It was read twice, with the tier stopped and
the rest of the stack standing, once immediately before the load and once immediately after the last
arm: 1261 to 1301 MiB, then 1259 to 1308 MiB. The two brackets agree within 7 MiB at either end, so
the Windows desktop under this session did not move while the readings were taken and the same floor
is honestly subtracted from all of them. That mattered because the floor is not a constant of the
machine: this repo has recorded it at 1552, at 1867 to 1932, and as high as 2836 MiB in other
sessions, and a floor read once and reused across sessions is how a gigabyte of error reaches a
number that bounds admission. Nothing here reuses one.

**Preallocation against arrival, which is the question a reservation actually asks.** A generation
that filled the context moved nothing: 13180 prompt tokens at 2983.16 tok/s and 924 decoded at
50.69 tok/s ran inside 9716 to 9721 MiB, entirely within the idle band. llama.cpp takes the 16K KV
and its compute buffers at load, so text work of any length is already paid for. What does arrive
with the work is the vision path, about 70 to 90 MiB on the first image, and it **stays**: idle
after the images reads 9764 to 9818 against 9701 to 9745 before them. Three repeats of the
near-full-context vision turn landed at 9773 to 9806, 9762 to 9832 and 9767 to 9788, so the step is
reproducible rather than a sample. The peak is therefore a load-time figure plus one late,
permanent, small allocation, which is exactly the shape that makes a reservation cheap to size.

**Two numbers in two units, which is where most of the gap was.** The old 11.3 GB is `nvidia-smi`
**total used** with the model resident: [ADR-0004](ADR-0004-model-lineup.md)'s table says so in
words ("VRAM is `nvidia-smi` total used, the table convention above") and
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md)'s header repeats it. Every other term in
this ADR's budget is a tier's own cost: the subagent ask is one model's footprint, and the soft cap
exists to leave the rest of the card to the user's desktop, so the desktop's own gigabyte belongs
outside the budget, not inside one of its terms. Measured the old way, total used, this tier peaks
at 9832 MiB, which is 9.60 GiB against 11.3 reserved; measured the way the budget means, it peaks
at 8573 MiB. The reservation was about 1.7 GiB high in its own unit and about 2.6 GiB high in the
budget's, and the difference between those two corrections is the floor being counted twice.

**The margin, and what it is for.** 8.6 GiB is 8806 MiB, which is **233 MiB above the measured
peak**. That covers, more than twice over, each of the three things that could move the reading:
the sampler's own spread inside a fixed phase (21 to 70 MiB), the floor bracket's disagreement
(7 MiB at either end), and the one allocation that genuinely arrives with the work (70 to 90 MiB
for the first image, already inside the peak, so a second unmeasured allocation of that size is
still covered). It does not pretend to cover a different llama.cpp build or a raised
`CORTEX_IMAGE_MAX_TOKENS`, both of which move the tier itself; a deployment that changes either
re-measures, which is the same rule `CORTEX_SWAP_BRAIN_VRAM_MIB` already lives under.

**What the number was not chosen to do.** 8.5 would have left exactly the 5.5 GiB
`docker-compose.subagents.yml` asks per spawn, so the shipped ask would have started landing on the
GPU on the strength of a 131 MiB margin. That is choosing the answer. The ask is itself the term
that is wrong: the GPU-placed subagent tier measured **3319 MiB** on this card, 3.24 GiB, so 5.5 is
about 2.3 GiB high, and correcting a reservation to compensate for a placeholder would leave two
wrong numbers agreeing. At 8.6 the reservation leaves 5.4 GiB of headroom, which admits one spawn at
the tier's **measured** cost and refuses a second, and still refuses the placeholder. That the ask
remains a placeholder is recorded as this area's own deferral rather than fixed here, because it is
a resource ask with its own measurement and its own compose default.

**What changes for a running deployment.** Under 11.3 the headroom was 2.7 GiB and nothing the
shipped stack spawns could fit it, so every subagent overflowed to the CPU whatever the card had
free. Under 8.6 the headroom is 5.4 GiB and a spawn declared at the tier's measured cost is
GPU-placed. Nothing about the fit-test, the ledger, or the handoff charge changes: the
handoff-window addendum above still replaces this term with the deep tier's declared cost for the
length of a swap and restores it after, and the value it restores is now this one.

**The instrument, and what it cannot say.** Per-process GPU attribution
(`nvidia-smi --query-compute-apps`) returns nothing under WSL2, verified with the tier resident and
serving, so total used minus a bracketed floor is the only reading available and every figure here
is that. It resolves what is claimed: the difference being ruled out is about 2.8 GiB against an
in-phase spread of at most 70 MiB. It cannot separate an allocation by the tier from the desktop
moving by the same amount at the same instant, which is why the vision step was repeated three
times and why the floor was read at both ends rather than once. And it says nothing about whether a
load spilled, which is the standing lesson [ADR-0030](ADR-0030-brain-handoff.md) records: nothing
here spilled, the card holding 14631 MiB free at the peak, but a memory reading is not what would
have told us.

## Addendum (2026-08-08): the subagent VRAM ask, measured, and the two placeholders it replaces

`CORTEX_SUBAGENTS_VRAM_GB` moves from **5.5 to 3.5**, and the `SubagentsConfig` default under it
from **2.0 to 3.5**. This is the term decision 2 fit-tests against the headroom the addendum above
left, and it was the last unmeasured number in that budget: the reservation re-measurement made it
the only reason the shipped stack still refused every GPU placement, so it opened as this area's
own deferral rather than being met halfway by a reservation.

**What was measured.** The GPU-placed subagent tier at its shipped shape, read out of the running
child's argv inside the sidecar rather than assumed:
`--model <the gemma-4-E4B QAT q4_0 pick> --host 0.0.0.0 --port 8083 -ngl 99 --ctx-size 8192
--parallel 2 --jinja --chat-template-kwargs {"enable_thinking": false}`, started through the
control API on the 24463 MiB card with the cortex resident throughout, ready **7.07 s** after
`start`. `nvidia-smi` total used was sampled every 0.2 s throughout, and every figure below is the
min and max of one phase's samples.

| Phase | Total used (MiB) | The tier's own cost (MiB) |
| --- | --- | --- |
| Floor, cortex resident and this tier stopped, immediately before the load | 10448 to 10500 (106 samples) | n/a |
| Idle, loaded, no request served yet | 13728 to 13803 (117 samples) | 3228 to 3355 |
| Two concurrent requests, each filling its own slot | 13752 to 13773 (20 samples) | 3252 to 3325 |
| Four concurrent requests, three rounds, 23.0 s | 13760 to 13838 (100 samples) | 3260 to 3390 |
| The whole resident phase, peak included | 13728 to **13838** (349 samples) | up to **3410** |
| Floor again, tier stopped at the end of the session | 10428 to 10493 (84 samples) | n/a |

**The floor is bracketed, for the reason the reservation's own reading gives.** Read before the
load and again after the last arm, it agrees within 20 MiB at the low end and 7 MiB at the high
end, so the desktop did not drift under the session and no movement of its own is folded into the
tier. The cost is therefore **3338 MiB** against the higher floor and **3410 MiB** against the
lower, which is 3.26 to 3.33 GiB, and the higher of the two is the one the ask has to cover.

**Nothing arrives with the work, and here that is total rather than nearly so.** Both slots were
driven to their own limit: each request reported 3803 prompt tokens and 293 decoded for exactly
4096, which is the whole of one slot's half of the 8192 KV, and twelve such requests with four in
flight at once moved the reading no further than the idle band's own spread. llama.cpp takes the KV
and its compute buffers at load, as it does for the cortex, and unlike the cortex this tier has no
vision path at all (no projector is named for it), so the late permanent allocation the reservation
had to cover does not exist here. The peak is a load-time figure.

**The ask is 3.5 GiB**, which is 3584 MiB and **174 MiB above the conservative peak**. That covers
each of the two things that could move the reading, more than once over: the sampler's own spread
inside the resident phase (110 MiB, and 75 MiB within idle alone) and the floor bracket's
disagreement (20 MiB). It does not pretend to cover a different llama.cpp build, a raised
`CORTEX_SUBAGENT_CTX_SIZE`, or a raised `CORTEX_SUBAGENTS_PARALLEL`, each of which moves the tier
itself; a deployment that changes one re-measures, the same rule `CORTEX_VRAM_CORTEX_GB` and
`CORTEX_SWAP_BRAIN_VRAM_MIB` already live under.

**The two placeholders erred in opposite directions, which is why both moved.** The compose default
of 5.5 was about 2.1 GiB above the tier's peak and refused every GPU placement. The code default of
2.0, which is what a deployment gets when it wires subagents without that compose file, was about
1.3 GiB **below** it: that one admitted a spawn onto room the tier would then overrun, which is the
unsafe direction and the more interesting of the two errors, and it had been quoted as the
"GPU-less-safe placeholder" the whole time. They are one number now, declared once per tree, and
the two declarations are tied together by nothing but the comments that say so:
`scripts/crosscheck.py` reads module-level constants in Python, Rust and TypeScript, and neither a
pydantic `Field` default nor a compose environment value is in its grammar.

**What changes for a running deployment.** With the soft cap at 14 GB and the reservation at 8.6
GiB the headroom is 5.4 GiB, so one spawn is GPU-placed and the next overflows to the CPU server,
which is what one tier process can serve anyway. Measured on the stack rather than argued: under
the old ask the GPU arm of `test_subagent_gpu_live.py` could not even select itself (ask 5.5
against headroom 5.4), both spawns went to the CPU server and the tier served no task at all; under
3.5 the same command with nothing overridden places one spawn on the tier, which answers in
**152.11 ms** (18 prompt tokens at 152.54 tok/s, 3 generated at 87.95 tok/s) against **13134.73 ms**
for the sibling that overflowed, and the tier's served-task count moves by exactly one. The suite
was proved able to fail first, the same way the arm's own sitting proved it: with the GPU endpoint
pointed at a closed port under this budget the run reddens on three placements rather than two,
because a GPU-placed attempt whose backend did not answer re-runs once on the CPU.

**The gated pins were proved able to fail too**, each mutation applied to the shipped default alone
and reverted, and the two pins fail on different mutations, which is what says they are not one
test twice. At 5.5 the placement pin reddens on the first spawn overflowing and the margin pin
stays green, since 5.5 covers the tier amply and simply does not fit. At 3.4 it is the other way
round: the margin pin reddens at 71.6 MiB against the 130 it has to clear, and the placement pin
passes, one spawn still fitting. At the old code default of 2.0 both redden, the margin at
-1362 MiB and the placement on the **second** spawn, which a 2.0 ask leaves room for. They read the
deployment's own numbers rather than literals, so a later move of the cap or the reservation is
answered here rather than silently absorbed, which is what the pin they replace was for.

**What the ask still does not model**, stated here because correcting it does not fix it: the
ledger charges one tier's whole footprint per spawn, while the tier is a standing process that a
second spawn allocates nothing on. So the refusal of that second spawn is a decode-speed choice
dressed as a memory one. That is the older modelling gap recorded in
[refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager), unchanged by
this and now the honest reading of what the second placement means. The roster's alternate entry
(`docker-compose.subagents-roster.yml`, `vram_gb` 2.5) is deliberately left alone: no GPU executor
exists for it, its `gpu_endpoint` falling back to its own CPU server, so its figure charges a
ledger for a placement that always runs on the CPU, which is the interim one-executor stance rather
than a measurement anyone can take today.

## Addendum (2026-08-09): the read timeout landed, and the fix was two clients

The consequences above deferred **a read timeout on the subagent HTTP client**, calling it the
actual unbounded-wait hazard under the admission budget. It landed on 2026-08-09, designed and
recorded at the [ADR-0005 stall-ceiling addendum](ADR-0005-llamacpp-engine.md), which is where the
derivations and the per-read semantics live. Three things about it belong here, where the deferral
was written.

**The count was wrong by one, in the direction that mattered.** Both this ADR and the backlog entry
named `build_subagents`. The resident tier's client (`builders.build_inference_backend`) had the
same `read=None`, and after a handoff the **deep model streams through that very object**, so the
site the deferral missed is the one carrying the slowest model in the lineup. Both are now built by
one factory, `builders.build_generation_client`.

**The pool's ceiling is not a peer's generation.** This ADR's own budget makes admission the queue
that matters, but the wire queue is shorter than it looks: a backend holds its model lease for the
whole stream, so two spawns of one entry on one target are serial brain side, ahead of the request
(measured at 4.8 s through two backend objects against 10.0 s through one,
[docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md)). The ceiling therefore covers one
CPU call's own time to first token, and its 600 s is twice the longest whole subtask measured on
the shipped entry.

**What the wall still cannot see.** The admission budget refuses a charge that cannot fit and the
ceiling now refuses a stream that has gone quiet, but neither bounds a subagent that keeps
producing tokens: a repetition loop holds its admission exactly as the wedged stream used to. That
is filed as the total generation cap in
[refinements/index.md#resource-governance](../refinements/index.md#resource-governance), the one deferral this
close opened.

## Addendum (2026-08-09): the admission wait is bounded, and the queue-depth half is not

The admission-wall addendum above kept queuing deliberately and deferred **a bounded wait** to a
deployment that showed a turn stalling long enough to matter. It lands here ahead of that trigger,
because the read-timeout close the same day removed the excuse: with a wedged stream now bounded on
both generation clients, the only remaining way for the queue to stop moving is a subagent that
keeps talking, which is filed as its own deferral rather than fixed, and an unbounded wait behind
it is a delegated turn with no end at all. `ResourceBudgetScheduler.admit` now refuses
after `wait_timeout_s` seconds with the same typed `SubagentAdmissionError` the runner already
degrades to an `ok=False` result, wired from `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 3600 s,
zero meaning never queue at all).

### The port really was unchanged, and here is the check rather than the claim

The backlog puts this area's entries "behind the unchanged
`SubagentPlacer`/`SubagentScheduler`/`ModelManager` ports", a blanket this area is on record for
getting wrong twice (placement-aware charging needed an argument `admit` has
nowhere to carry; hard enforcement needed a cgroup a port that only sees admissions cannot reach).
So the signature was opened and read before anything was designed:
`admit(request) -> AbstractAsyncContextManager[None]`, `drain(*, timeout_s) -> bool`, `undrain()`.
A wait bound is expressible without touching any of it, and for a reason worth writing down rather
than a coincidence: the bound is **policy the budget owns**, not a per-spawn ask, so it belongs
where the budget's other two numbers already live, on the implementation's constructor. Every
caller of `admit` is the runner, and it wants the refusal, not the knob. What the port *did* gain
is a sentence of contract: an implementation that queues owes a bound on that queue and the same
typed refusal when it elapses. `AdmitAllScheduler` satisfies that vacuously, having no queue, which
is why the drain contract suite needed no new case; the twin is unchanged.

### Deriving 3600 s, from measurements and not from feel

A bound that refuses a legitimately queued spawn is worse than the unbounded wait it replaces: it
turns a slow success into a failure. So the number is the worst wait the **shipped** stack can
produce while everything is working, doubled.

- `MAX_SPAWN_BATCH` is **8**, the cap on one `spawn_subagents` call (ADR-0010 batch-cap addendum).
- The shipped budget admits **two** at a time: `CORTEX_SUBAGENTS_CPU_BUDGET=4.0` against an ask of
  `CORTEX_SUBAGENTS_CPUS=2.0`, and the memory pair caps at the same two whichever declaration is in
  force (8.0 against the compose file's 3.0, or against the code default's 2.0, where cpus binds
  first). That is also why `--parallel` is 2 on the CPU server.
- **Admitted is not concurrent, and how far short it falls is a placement question.** One roster
  entry holds one `LlamaCppBackend` per target and a backend holds its model lease for the whole
  stream, measured at **4.8 s through two backend objects against 10.0 s through one**
  ([docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md)). Two spawns of one entry
  therefore overlap when they land on different targets and serialize when they share one, so a
  slot frees twice per whole subtask in the first case and once in the second. The shipped wiring
  is the overlapping one: `CORTEX_SUBAGENTS_VRAM_GB` is 3.5 against the 5.4 GiB the 14 GB soft cap
  leaves beside the 8.6 GiB cortex reservation, so exactly one of the admitted pair is GPU-placed
  and the other overflows, and both dial the one CPU server, because
  `CORTEX_SUBAGENTS_GPU_ENDPOINT` defaults to it and an alternate's empty `gpu_endpoint` normalizes
  to its `endpoint`. Serialization is what a closed GPU tier leaves, not the standing case
  ([ADR-0018](ADR-0018-heterogeneous-subagents.md) measured this pair on the running deployment).
- A whole CPU subtask on the shipped entry is **200 to 300 s**: a three subtask batch runs 10 to 15
  minutes serialized at about 0.35 tok/s (same runbook, derived in the
  [ADR-0005 stall-ceiling addendum](ADR-0005-llamacpp-engine.md)).

The last of a full batch of eight therefore waits three whole subtasks while the admitted pair
overlaps, about **900 s**, and six of them when both spawns land on one target, about **1800 s**;
every second of either is a spawn that was going to run. The bound is **twice the serial figure**,
the same doubling the pool's own stall ceiling carries for the same reason (on this hardware the
honest reading is that ten minutes of silence is a wedge, and an hour of queuing is a pool that is
not draining). Note what that makes it: an **upper bound** over both placements, four times the
wait the shipped stack actually produces, rather than an equality against a single serial reading.
Two knobs would have been wrong here where they were right for the stall ceiling: the budget is one
object across roster entries by design, so there is one queue and one bound.

**Corrected the same day it was written (2026-08-09).** The bullet above first read the backend
lock as unconditional ("a slot frees once per whole subtask, not twice"), which is the premise
[ADR-0018](ADR-0018-heterogeneous-subagents.md) had measured false the day before: an entry that
omits `gpu_endpoint` fronts one server with two lock objects, so its spawns overlap two ways. The
number does not move, because the serial reading is still reachable with the GPU tier closed and
3600 s is twice it. What moves is what the derivation claims: an upper bound, not an equality, and
a conservative one by a factor of four wherever the GPU path is open.

**What the bound does refuse**, said plainly rather than left to be discovered: two full batches
queued at once, which is 16 CPU subtasks, will lose its tail to the bound while the entry
serializes (the sixteenth spawn is admitted 4200 s in) and will clear it while the pair overlaps
(2100 s in). So the deployment that should raise `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` is the one
that both routinely queues more than one batch and collapses its admitted pair onto a single
target, which means a GPU subagent tier that is down or a VRAM ask that never fits the headroom;
where that pair straddles the two targets the shipped default already covers two batches and the
knob wants leaving alone. The refusal names the bound either way, so its reader lands on the right
knob. The GPU tier only shortens these waits (a GPU-placed spawn measured **221.05 ms**
against **12536.83 ms** for the sibling that overflowed), so sizing on the CPU path is the
conservative direction.

### Depth and wait answer different questions; only one shipped

The entry asked for both "no timeout and no queue-depth bound". They are not the same refusal: a
**depth** bound refuses early, when the queue is already provably longer than the budget can drain;
the **wait** bound refuses late, after the caller has paid. Only the wait bound shipped, and the
reason is that the scheduler has charges and no durations. It knows a waiter asks for 2.0 cpus; it
has no idea whether that waiter is thirty seconds or five minutes of work, so any depth number is a
guess where the wait number above is arithmetic over measurements. Five waiters asking 0.5 cpus
each drain in a fraction of the time five asking 2.0 do, and depth cannot tell them apart.

**What is left unanswered**, therefore: a spawn joining a queue that is already hopeless still pays
the whole hour before it is told, so the model hears "refused" an hour late instead of at once, and
`MAX_SPAWN_BATCH` plus depth-1 are still the only things bounding how long that queue can get.
Filed as its own deferral in
[refinements/index.md#resource-governance](../refinements/index.md#resource-governance), with the trigger that
makes it worth its guess: the first deployment observed hitting this bound, which is also the first
one with a measured drain rate to derive a depth from.

### `asyncio.timeout`, not the `Clock` port, and why that is the consistent choice

The entry, and the ADR-0005 addendum that pointed here, both expected "a timeout design over a
`Clock`". The bound is enforced by `asyncio.timeout` around the wait loop instead, which is the
idiom `drain` already uses on this very condition object, and the reasons are three:

- **A duration belongs on a monotonic clock.** `Clock.now()` is wall time; an NTP step during an
  hour-long wait would fire this bound early or late. The event loop's clock cannot step.
- **The `Sleeper`/`Clock` pair exists for poll loops.** Its own charter says so: the core may not
  reach for `asyncio.sleep`, because a poll loop that did would make every test of it a real-time
  test (`health_gate.py`). This is not a poll loop; it is a bounded wait on an event, and an
  already-expired bound drives its timeout path with no wall-clock time at all, which is exactly
  why `drain` was allowed the same mechanism. Every test of the new refusal runs in microseconds.
- **One class, one way of bounding a wait.** A scheduler whose two waits timed out by two different
  mechanisms would be a question with no good answer at the next reading.

The core still reads no wall clock and still owns no timer. Injecting a `Clock` here would have
bought a decoration: the deadline would have been read from it and enforced somewhere else.

### Distrust green

Six mutations, each applied to production code alone with the whole `packages` suite re-run, so the
counts are measured rather than aimed at:

| Mutation | Reddened | Which |
| --- | --- | --- |
| the `asyncio.timeout` wrapper dropped (the unbounded wait restored) | 4 | the three bound cases plus the wiring one |
| the refusal interpolates a literal instead of the configured bound | 2 | `..._is_refused_and_names_it`, `..._hands_the_pool_its_configured_admission_bound` |
| `TimeoutError` allowed to escape untyped | 4 | the same four as the first row |
| the builder keeps the core default instead of `config.admission_wait_s` | 1 | `test_build_subagents_hands_the_pool_its_configured_admission_bound` |
| `DEFAULT_ADMISSION_WAIT_S` retuned to 600.0 | 2 | `test_subagents_default_to_disabled`, `..._clears_the_worst_wait_one_batch_can_legitimately_produce` |
| the non-negative bound check dropped | 1 | `test_rejects_a_negative_wait_bound` |

Every test that can queue is wrapped in an `asyncio.timeout(10)`, because the defect under test is
an unbounded wait and a mutation that hangs the suite proves nothing. That wrapper is itself
witnessed: the first row's run took **139 s** against the suite's usual **98 s**, which is those
four tests reaching their guard and failing rather than the run never ending.

## Addendum (2026-08-09): `SubagentPlacer` learns that a target can be absent, not only full

The companion to the co-residency-era addendum above, which taught this port *which residency* it
is fit-testing against. That one is arithmetic: a handoff makes the card smaller and the resident
term says so. This one is not arithmetic at all, and the distinction is the whole reason it is a
second pair of verbs rather than a cleverer number.

**The failure.** Restarting each `CORTEX_SWAP_EVICT_MODELS` tier after a brain handoff is
deliberately best effort (ADR-0030 decision 4), so a peer that will not come back is logged and
swallowed, and admission then reopens onto a `llama-server` that is not running. Every GPU-placed
spawn afterwards dials a dead endpoint, fails at its backend, and is re-run on the CPU by the
re-place this ADR's own addendum landed: correct, honest, and paying two loads to learn what the
swap back already knew. The full argument, the down-versus-evicted rule, and what clears the
record live at the ADR-0030 tier-outage addendum; what belongs here is the port.

**The decision.** `SubagentPlacer` gains `close_gpu()` and `open_gpu()`, both sync and idempotent.
While closed, `place` **must** answer CPU for every request without consulting the headroom.
Neither verb moves the placed ledger, so a spawn placed before a close still releases the same
amount after it, and an implementation with no GPU target of its own may make both no-ops, which
is the same honest degenerate form the charge pair already allows.

**Why not express it as a charge.** Two reasons, and the second is the one that would have bitten.
A resident charged large enough to crowd the soft cap out would make the placer report "no room"
where the truth is "no server", which is a lie a future reader would have to reverse-engineer. And
the handoff pair heals itself: `charge_standing` fires whenever the cortex is serving again, so a
tier outage encoded as a charge would be silently reopened by the next successful swap back. The
two pairs are independent by contract, and `test_a_handoff_charge_does_not_reopen_a_closed_gpu`
pins exactly that.

**Why the placer keeps one bit while the record keeps one entry per tier.** The brain has no
declared mapping from a hosted tier id to the GPU endpoint a roster entry dials, so the placer
cannot skip *a* tier, only *the* GPU. The record behind it is per tier because that is what an
operator reads and what the retry acts on. The conservative direction is the right one: over
refusing the GPU costs decode rate, under refusing costs a dead load per spawn.

**One implementation, one contract suite.** `VramBudgetPlacer` is still the only `SubagentPlacer`
in the repo, and `test_placer.py` is where the port's checks live, so the new verbs are pinned
there beside the old ones and exercised end to end in the core's `test_residency_tiers.py`, where
a real residency scope is what writes them. Distrust green: consulting the headroom before the
closed flag in `place` reddens 7 tests across two packages, two of them in `test_placer.py`.

## Addendum (2026-08-19): the subagent memory budget is one number, and the gates now hold it

The budget the admission scheduler runs against and the cgroup that catches anything admitted past
it were the same number written four times, agreeing only by hand. `SubagentsConfig.mem_budget_gb`
declared `8.0`; `docker/docker-compose.subagents.yml` passed `${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}`
into the brain, spent `${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g` as the CPU subagent container's
`mem_limit` and again as its `memswap_limit`, and claimed the twinning in prose twice more. Raising
the field to 12 left a container capped at 8 while the scheduler believed it could admit 12 GB of
subagents, which is precisely the failure this record exists to prevent, and nothing reported it.

The constant scan (`scripts/crosscheck.py`) could not be pointed at it as it stood, for two
independent reasons. Both are now resolved, and the reasoning matters more than the entry.

### The site: a named constant, not a reducer that reads calls

`values.py` reduces a declaration's right-hand side and **refuses what it cannot read** rather than
guessing, which is the property that keeps the gate from agreeing with itself. `Field(default=8.0,
gt=0)` is a call, so it was refused. The two ways forward were to teach the reducer that call, or
to give the number a name the reducer already reads.

The name wins, and not narrowly. A reducer that reads `Field(...)` is a reducer that knows pydantic:
it would have to pick the `default` keyword out of a call that also accepts a positional default and
a `default_factory`, in a module that is deliberately language-agnostic and understands four value
forms and no call at all. Every such rule is a place where the gate infers a value nobody wrote
down. And the alternative is not a workaround but this package's own idiom: `admission_wait_s`,
`max_tokens` and `run_timeout_s` already cite module constants in their `Field(...)`, three of them
imported from the core. So `DEFAULT_MEM_BUDGET_GB = 8.0` sits with `DEFAULT_SUBAGENT_MODEL` at the
top of `config_subagents.py`, `mem_budget_gb` cites it, and the number is nameable in the module
contract and in this record for the first time.

### The mentions: one number, two spellings, and the second one derived

The far side spells this number two ways and neither is a matter of taste. Docker parses the size
suffix, so `mem_limit` takes `8g` and refuses `8.0g`; the environment passthrough carries the float
the brain parses. Since the close of the decimal work (ADR-0029, 2026-08-19) a decimal reduces to
**the digits it is written with**, on purpose, so `8.0` and `8` are two values and one needle cannot
find both.

`Mention.spelling` is the answer, and its shape is chosen so that the textual comparison survives
it. `Spelling.WRITTEN` is the default and every existing mention keeps it. `Spelling.WHOLE` renders
the same value without a fractional part, and it is **derived from the declared value rather than
typed into the registry**: nobody writes `8` beside `8.0` and asks the gate to trust that they
match. A fraction that is not zero is refused rather than truncated, so a budget retuned to `8.5`
fails the scan naming the far side that cannot spell it, instead of quietly capping a container half
a gigabyte under what the scheduler admits.

The one thing a re-spelling cannot do is notice a site that drops its point, `8` and `8.0` being one
whole number and therefore one whole spelling. That is exactly the drift the decimal work made the
reducer textual to catch, so `values.spelling_fault` refuses any entry whose mentions all re-spell:
a second site or a mention rendering the value as written has to stand beside them. The registered
entry carries two of each, and the drift is caught by the written pair.

### What is registered, and what is deliberately not

One site (`DEFAULT_MEM_BUDGET_GB`) and four mentions, all in `docker-compose.subagents.yml`: the
environment passthrough, the two container limits as one counted set (memswap equal to memory is
what disables the container's swap, so one moving without the other re-enables it in silence), and
the two comments that restate the number, one claiming the twinning and one counting admissions
against it. Each template covers the whole of what it pins, including the quotes around a compose
scalar: a needle stopping at the substitution's own `}` is satisfied by the size limits and leaves
the passthrough free to drift, which is the prefix hole the port publish taught the registry to
close.

This record is not a far side and no decision record ever is: it says what was decided on a date and
must go on saying it after the number moves. The wider survey stays unasked here too. Around fifty
`${CORTEX_*:-default}` substitutions live under `docker/`, most naming a path, a model file or a
host-shaped number no Python constant declares, and the sibling knobs in this very file include one
pair that disagrees on purpose (`CORTEX_SUBAGENTS_MEMORY_GB` ships 3.0 where the field defaults to
2.0). The neighbouring CPU budget is the closest twin and is filed rather than folded in
([R-315](../refinements/tasks/315-subagent-cpu-budget-and-its-siblings.md)).

### Proved able to fail, seven times

Each drift was planted on the real tree, run through `crosscheck.py`, and reverted. The site alone at
`12.0` exits 1 naming all four spends. The environment passthrough alone at `9.0`, one container
limit alone at `9` (reported as found 1, pinned 2), the twinning comment alone at `9.0`, and the
admission sentence alone at `9 GB` each exit 1 naming that one place. The site retyped as `8`, the
same number in the other spelling, exits 1 on both written mentions and is the proof that the
re-spelling did not undo the textual comparison. The site at `8.5` exits 1 twice more, reporting a
number the size suffix cannot carry at all.

## Addendum (2026-08-20): the four knobs beside that budget, and the ask that disagreed on purpose

The addendum above tied the memory budget and named the four knobs in the same compose file it left
untied ([R-315](../refinements/tasks/315-subagent-cpu-budget-and-its-siblings.md)). They are tied
now, and one of them moved to get there. Every number this file ships for the subagent tier is a
module constant in `config_subagents.py` and every spelling of it in
`docker/docker-compose.subagents.yml` is held to that declaration by `scripts/crosscheck.py`.

### The CPU budget is the memory budget's twin, and cheaper by one spelling

`cpu_budget` had the same shape as `mem_budget_gb` and the same failure: the soft sum the admission
scheduler runs against, spelled again as the hard `cpus` cap on the container that runs what it
admits, and a third time in the comment claiming those two are twins. Retuning the field alone hands
that container fewer cores than the spawns it is serving were charged against, which nothing at
runtime reports; it reads as a tier that got slow.

What it does not need is the second spelling its neighbour required. Docker's `cpus` takes a float
where its size suffix will not, so all three places write the digits the field declares and the
entry is three `Mention`s at `Spelling.WRITTEN`. The passthrough and the cgroup limit render the
same needle and are pinned with `occurrences=2`, because they are one set: they are precisely the
twinning the comment beside them claims, so one moving without the other is the whole of what this
entry exists to report.

### The three asks, and the pair that had drifted

`vram_gb` and `cpus` already agreed between the field and the stack, so tying them cost a registry
entry each and changed no number. `memory_gb` did not: the stack shipped `3.0` and the field
defaulted to `2.0`, and the disagreement had been recorded twice as deliberate without a reason
being written for it.

**The field moves to the measured number.** The measurement is the same one the compose comment has
carried since the pick revision: about 2.5 GiB of RSS for the shipped CPU entry, rounded up so two
are admitted under the memory budget, which is what `--parallel` serves. Against that, a field
default of `2.0` under-charges every spawn by half a gigabyte, and the direction is the unsafe one:
the scheduler admits onto room the container's own `mem_limit` will then refuse, and a subagent that
swaps takes minutes per token. That is exactly the error the VRAM ask was corrected for in the
measured-ask addendum above, where a code default of 2.0 under a 3.5 GiB tier "admitted a spawn onto
room the tier would then overrun", and the fix there was the fix here: one number, declared once per
tree, with the two declarations tied rather than commented at each other.

**What changes for a deployment.** Only one that wires subagents without this compose file, which is
where the field default is what gets charged. It now charges what the shipped stack charges. Under
the shipped file nothing moves at all, the environment value having been `3.0` throughout, and under
either the CPU budget binds first anyway: two spawns at `cpus 2.0` exhaust `cpu_budget 4.0` before
`3.0` of memory each reaches `8.0`. `SubagentRosterEntry` defaults off the same three constants, so
an alternate that names no ask is charged the shipped entry's, which over-charges anything smaller
and therefore errs toward the CPU, as it did before.

### What is deliberately not registered

The runbook's worked examples are not far sides. `docs/runbooks/subagents-cpu.md` spells
`CPU_BUDGET=4.0` and `CPUS=2.0` inside a paragraph that reasons about how long a full batch queues,
and a number inside an argument is not the same as a number a document states as the shipped
default: the deadline entries pin table rows that say "default", and this rule keeps that line where
it is. The prose inside the compose file itself is pinned, because that file is where a retune
happens and its own sentences must move with it.

This record is not a far side either, and no decision record ever is. The wider survey stays unasked
here for the third time and is now filed rather than re-punted
([R-333](../refinements/tasks/333-compose-defaults-that-restate-a-declaration.md)).

### Proved able to fail, twelve times

Every drift was planted on the real tree, run through `crosscheck.py`, and reverted. For the CPU
budget: the environment passthrough alone and the cgroup `cpus` cap alone each exit 1 reporting
`found 1, pinned 2` over the counted pair; the twinning comment alone exits 1 naming that sentence;
the site alone exits 1 twice, reporting `found 0, pinned 2` and the comment it no longer matches.
For each of the three asks: the compose passthrough alone, the site alone, and, where the file
records the measurement in prose, that sentence alone. Each exits 1 naming its own entry and no
other, and the site drifts of the memory and VRAM asks each exit 1 twice, over the passthrough and
the measured sentence together.

## Addendum (2026-08-20): the NPU probe, and which of three findings it is

The Intel NPU has sat in this record as a third `PlacementTarget` behind two unknowns, the first of
them called the likely blocker: whether the NPU is reachable from the dockerized WSL2 brain at all,
since WSL2 paravirtualizes the dGPU but not the NPU. It was probed on this machine. It is not
reachable, the guess about why was right, and the probe is written down here because three
different findings wear the same sentence and only one of them was measured.

**Kept apart on purpose.** "This machine has no NPU" is a fact about the hardware. "The device is
not paravirtualized into WSL2" is a fact about the guest. "The NPU is not reachable from a
container" is a fact about the container. The middle one and the last one were measured. The first
was not, and this addendum does not claim it.

### What the guest is given

Only one device node exists: `ls /dev/dxg /dev/dri /dev/accel` finds `/dev/dxg` and reports that
the other two do not exist. `/dev/accel` is the node Linux's own NPU driver creates, so its absence
is the shape of the answer rather than an accident of naming.

The guest's PCI bus carries five devices and none of them is Intel silicon: two virtio devices, and
three Microsoft vPCI devices of display class 0x030200 (`1414:008e` twice and `1414:008a`), every
one of them bound to `dxgkrnl`. Whatever WSL2 projects, it projects through that one driver.

The kernel settles the Linux path independently of any device. `zcat /proc/config.gz | grep
DRM_ACCEL` answers `# CONFIG_DRM_ACCEL is not set`, and `intel_vpu`, the driver that would bind an
Intel NPU and create `/dev/accel/accel0`, lives under `drivers/accel` and depends on that symbol.
This kernel could not drive an NPU if one were handed to it.

### What the paravirtualization actually projects

`/dev/dxg` is not a GPU, it is an adapter channel, so the question is what enumerates on it. Driven
through `/usr/lib/wsl/lib/libdxcore.so`, the adapter list holds exactly two entries under each of
the four capability attributes, `D3D11_GRAPHICS`, `D3D12_GRAPHICS`, `D3D12_CORE_COMPUTE` and
`D3D12_GENERIC_ML`:

| adapter | hardware id | reads as |
| --- | --- | --- |
| NVIDIA GeForce RTX 5090 Laptop GPU | `10de:2c58` | discrete, 23.57 GiB |
| Intel(R) Graphics | `8086:7d67` | integrated |

`D3D12_GENERIC_ML` is the attribute a compute accelerator would have to carry to be worth a
placement target, and it lists the same two GPUs. Asked instead by hardware type, both adapters
answer to the GPU attribute and neither answers to the compute accelerator or the NPU one. That
last reading needs its control stated: an attribute GUID this build does not recognize also returns
an empty list, so an empty list alone proves nothing, and what makes it evidence is that the GPU
attribute from the same family returned both adapters and each adapter reported carrying it.

So the entry's parenthetical was right and is now narrower than it was: WSL2 projects display class
adapters, and it projected the integrated GPU as well as the discrete one. What it does not project
is anything of any other class.

### What a container gets, which is the question the entry actually asked

The probe that matters is not the guest's but the container's, and OpenVINO answers it from inside
one. The wheel ships `libopenvino_intel_npu_plugin.so`, and the plugin loads: an unsupported
property query comes back from the plugin's own property manager rather than from a missing
library. So the plugin path is reachable. It enumerates nothing. `Core().available_devices` is
`['CPU']` and `Core().get_property("NPU", "AVAILABLE_DEVICES")` is `[]`.

One finding reaches past today's kernel. Of the **1,038** Windows driver packages WSL maps into
`/usr/lib/wsl/drivers`, exactly three ship Linux user mode libraries: the Intel graphics package in
its two staged versions, and the NVIDIA one. Intel's NPU packages ship `npu_level_zero_umd.dll` and
`npu_d3d12_umd.dll` and no `.so` at all. A future WSL that projected the device would therefore
still leave nothing on the Linux side to drive it, so the condition that revives this work has two
halves and not one.

**The denominator is corrected here.** It was first written as 1,349, which is what the directory
holds rather than what it maps: 1,038 package directories plus 311 `.ini` sidecars beside some of
them. The ratio is the whole of the finding, so counting each sidecar as a package inflates its
denominator by 311.

### What was not measured, and why the entry's hardware line stands unrepeated

`/proc/cpuinfo` names the Intel Core Ultra 9 275HX this record already records, and the Windows
driver store carries Intel's NPU driver package in **two** staged versions (`npu.inf`, class
`ComputeAccelerator`, 32.0.100.4778 dated 2026-04-28 and 32.0.100.3104 dated 2024-10-25) plus a
separate `npu_extension.inf` at the older of the two. The newer package's hardware ids include the
Arrow Lake NPU at `8086:AD1D` beside Meteor Lake's `7D1D` and Lunar Lake's `643E`. (**The count is
corrected here**, this sentence having first said the store carries the package, singular, in the
same paragraph that is careful to say the graphics package is present in its two staged versions.)
A staged driver package is not a present device, and this guest cannot see Windows device state at
all: interop is off in `/etc/wsl.conf` and no Windows volume but
the model drive is mounted. So the hardware confirmation of 2026-07-01 is neither repeated nor
contradicted here, and nothing below rests on it.

### Decision: re-triggered rather than declined

Nothing measured is a fact about this repo's design. `PlacementTarget.NPU` and an OpenVINO
`InferenceBackend` adapter would land the same way on the day the device appears, and the second
unknown, whether NPU inference for a 2 to 4B model is fast and mature enough to be worth a target,
could not be measured at all because there is nothing to measure it on. Declining would file a
platform fact as a design verdict.

So the entry stays open with its trigger replaced, on the precedent of the ANN index entry, which
was measured and re-triggered rather than closed. The old trigger asked for the feasibility pass
this addendum is. The new one is the state of the world that would make the pass worth rerunning,
and it is one command: an NPU device enumerating from inside a container, meaning
`Core().get_property("NPU", "AVAILABLE_DEVICES")` answers with anything, which needs both halves,
WSL projecting the device and the vendor shipping a Linux user mode driver for it.

### Consequences

- **The likely blocker is confirmed as the blocker**, at the guest and at the container both, and
  the host side runtime this record worried it would force is not merely awkward: there is no
  Linux user mode driver to run there either.
- Nothing in the tree changes. The probe is a reading of the machine, not of the code.
- The entry keeps its area and its origin here, for the reason it kept them when the host backlog
  was extracted: the work is code even where only one machine can judge it.
