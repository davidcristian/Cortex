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
  `PlacementTarget` (ROADMAP deferred option).

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
([docs/refinements/resource-governance.md](../refinements/resource-governance.md)): **a hard budget
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
[docs/refinements/resource-governance.md](../refinements/resource-governance.md) and its
[index](../refinements/index.md) until 2026-07-19, when host-side work was extracted into its own
directory; both this validation and the placeholder cap numbers now live in
[docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md), with the sentences above kept verbatim
there and pointer stubs left behind.
