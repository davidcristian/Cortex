# ADR-0012: Resource governance: GPU-first subagents, a VRAM-budget placer and a soft CPU/RAM budget

**Status:** Accepted (2026-09-08)

**Revises:** [ADR-0007](ADR-0007-model-manager-inference.md) (Model Manager v1) and
[ADR-0010](ADR-0010-subagents.md) decisions 6 and 7 (subagents on the CPU only).

## Context

Two directions from the user drive this record. **Subagents are GPU-first with CPU overflow**: a
spawn goes on the GPU when the VRAM soft cap has headroom beside the resident cortex and on the CPU
when it does not, which makes `CORTEX_VRAM_SOFT_CAP_GB` an enforced budget rather than a note.
**Resource caps keep the machine usable**: a soft budget limits how much CPU and RAM admitted
subagents may commit, so a spawn burst never starves the user's foreground.

The decisive constraint is that **this stack has no per-process GPU compute cap**. MIG is absent on
consumer and laptop GPUs, MPS is unusable under WSL2, and the `nvidia-smi` clock and power settings
are host-only and cover the whole GPU. So GPU use is governed by a VRAM fit test, which limits GPU
concurrency, and nothing else. The user's fixed choices: per-subagent CPU through the container's
`--cpus`, a global CPU and RAM ceiling enforced **softly** by the scheduler's admission budget (no
`.wslconfig`, no parent cgroup, no hard WSL limits), and no host-side GPU clock clamp.

The one hard rule, 100% coverage without a GPU, and ports before adapters all hold: real
`llama-server` processes, `-ngl` flags and cgroup caps sit behind the ports below, never in them.

## Decision

1. **Placement is its own port; `ModelManager` is unchanged.** The GPU lease, the subagent pool's
   admission and VRAM placement are three contracts, composed at the orchestrator and never merged.
   `SubagentPlacer` (`cortex_core/ports_placement.py`, re-exported from `ports.py`) has `place`,
   `release`, the residency pair `charge_handoff(resident_gb=)` and `charge_baseline()`, and the
   outage pair `close_gpu()` and `open_gpu()` (decision 13). An implementation with no GPU target
   of its own may make both pairs no-ops.

2. **`VramBudgetPlacer` fit-tests each spawn against the policy cap.** It keeps a live record of
   GPU-placed VRAM: `headroom = soft_cap − resident − placed`; a request whose `vram_gb` fits is
   placed on the GPU (`-ngl 99`) and reserves it, and anything else goes to the CPU (`-ngl 0`) and
   reserves nothing. `resident` is the cortex reservation except during a brain handoff (decision
   13). llama.cpp's own `--fit` is not used, because it sizes to free VRAM and not to the cap. The
   whole model goes to one target, since a 2 to 4B model split across both runs worst of both.
   `place` and `release` are synchronous with no `await`, so concurrent spawns in one batch compete
   for the headroom correctly on one event loop with no lock. The fit test **is** the GPU
   concurrency limit, so there is no `max_gpu_subagents` setting; the user moves the cap to change
   it.

3. **Placement values** (`cortex_core/placement.py`): `PlacementTarget` (GPU or CPU, with `ngl`
   derived from it), a frozen `PlacementRequest(model, vram_gb, cpus, memory_gb)` whose fields must
   be positive, and `Placement(target, reserved_gb)`, which includes its reservation so `release`
   is exact. The endpoint is not on `Placement`: the runner routes by target (decision 6).

4. **`ResourceBudgetScheduler` admits against a two-dimensional soft budget.**
   `admit(request) -> AbstractAsyncContextManager[None]` reserves the request's `cpus` and
   `memory_gb` against summed targets (`CORTEX_SUBAGENTS_CPU_BUDGET`,
   `CORTEX_SUBAGENTS_MEM_BUDGET_GB`). Over budget a spawn **waits** on an `asyncio.Condition`; a
   waiting spawn holds nothing, and one-level delegation means no spawn waits on another, so it
   cannot deadlock. The charge is static per model in the list, read from config, and independent
   of the target, because admission happens before placement. "Soft" means the budget limits
   nothing it did not admit (the cortex, the brain container); what it admitted it limits exactly.

5. **The runner admits first, places second, releases in `finally`.** `SubagentRunner.run` orders
   admit (may wait) outside place (instant) outside the attempt, so no VRAM is ever held while a
   spawn waits for a CPU slot, and no rollback path exists. The ordering between the run deadline,
   the stall timeout and the admission wait is decided in
   [ADR-0047](ADR-0047-delegated-run-bound-ordering.md).

6. **Two backends selected by target; `InferenceBackend` and the proto are untouched.** The runner
   holds `backends: Mapping[PlacementTarget, InferenceBackend]` over a GPU server and a CPU server,
   each with its own model lease, and picks `backends[placement.target]`.

7. **The records of held resources are live state, not the durable state the hard rule governs.**
   `placed_gb`, `cpu_used` and `mem_used_gb` count what is held now, like a lock. A swap physically
   frees what they count, so the correct value after one is zero and persisting it would claim
   resources no process holds. Tasks and conversations stay in the stores.

8. **Opt-in.** `CORTEX_SUBAGENTS_BACKEND` defaults to `none`, so no placer or scheduler is built
   and CI runs as before; the pure placer and scheduler are covered by core unit tests.

9. **An impossible or refused admission is a value, and it is logged.** A charge above the whole
   budget, a spawn during a drain (decision 10) and a wait past its limit (decision 11) all raise
   the typed `SubagentAdmissionError`, whose message names the cause. The runner degrades it to an
   `ok=False` `SubagentResult` saying the spawn was refused before it ran, so one refused member no
   longer takes its batch or the turn down, and logs `cortex_core.runner` at `WARNING`, "a spawn
   was refused before it ran", with `task_id`, the resolved `model` and the scheduler's `reason`.
   The log sits in that `except` rather than in `_failed`, whose other refusals (an unknown task or
   model) are call faults an operator tunes nothing for. `SubagentsConfig` refuses at startup any
   model in the list whose `cpus` or `memory_gb` exceeds its budget (equality is allowed). A
   temporarily full budget still queues: the work runs seconds later.

10. **`drain(*, timeout_s) -> bool` and `undrain()` empty the pool for a model handoff.** From
    `drain` until `undrain` every `admit` is refused with `POOL_DRAINING_MSG` instead of queued,
    because a brain-phase spawn queued against its own drain would deadlock the turn; a spawn
    already waiting is woken and refused. `drain` waits for an integer in-flight count (never the
    float totals) to reach zero under `asyncio.timeout` (the conductor passes
    `CORTEX_SWAP_DRAIN_TIMEOUT_S`, default 60 s) and on timeout returns `False` with nothing
    killed. `undrain` is synchronous and idempotent, and belongs in the conductor's `finally`.
    `AdmitAllScheduler` and `ResourceBudgetScheduler` pass one shared drain contract suite.

11. **The admission wait is limited to 7200 s.** `admit` refuses after `wait_timeout_s`
    (`CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, `DEFAULT_ADMISSION_WAIT_S`, zero meaning never queue).
    The limit is the budget's policy, on the implementation's constructor, and the port's contract
    says an implementation that queues owes a limit and the same typed refusal. 7200 s is three run
    deadlines: a task holds its admission for up to `ATTEMPTS_PER_ADMISSION` (2) deadlines of 2400
    s, which is longer than the queue a full batch produces, and `SubagentsConfig` refuses a wait
    under that hold ([ADR-0047](ADR-0047-delegated-run-bound-ordering.md) decisions 4 and 5; the
    batch readings are [delegated run holds](../readings/delegated-run-holds.md)). It is enforced
    with `asyncio.timeout` rather than the `Clock` port: a duration belongs on the loop's monotonic
    clock, `Clock` exists for poll loops and this is a wait on an event, and `drain` already limits
    its wait the same way on the same condition.

12. **A GPU-placed attempt that fails on inference runs once more on the CPU.** The trigger is any
    `AttemptFailure.INFERENCE` from a GPU placement, not a CUDA out-of-memory: under WSL2 an
    over-committed model oversubscribes into shared memory and loads slowly rather than failing
    ([readings](../readings/subagent-budget.md#an-over-committed-load-serves)), and a restarted peer
    may simply not be serving. A malformed constrained reply does not run again, being a property
    of the prompt. The GPU reservation is released before the re-run, which reuses the same
    admission and `DispatchBudget`, and the two attempts' taint is combined. The attempt lives in
    `subagent_attempt.py` (`PlacedAttempt`, returning an `AttemptOutcome`).

13. **The placer knows which residency it fits against and whether the GPU tier is up.** During a
    handoff `charge_handoff(resident_gb=)` replaces the cortex term with the deep tier's declared
    cost and `charge_baseline()` restores it
    ([ADR-0055](ADR-0055-co-residency-and-spill-watch.md) decision 3). A GPU tier that did not come
    back after a swap is recorded and `close_gpu()` makes `place` answer CPU without consulting the
    headroom until `open_gpu()` ([ADR-0054](ADR-0054-baseline-residency.md) decision 3). Neither
    pair moves the placed total, and the two are independent: an outage is not a charge, because a
    charge would report "no room" where the truth is "no server", and `charge_baseline` after the
    next swap would silently reopen it. The placer keeps one bit because the brain has no mapping
    from a hosted tier to the endpoint a subagent connects to.

14. **The configured budget is measured, and each number is written once.** The soft cap is 14 GB,
    a user policy value that leaves the rest of the card to the desktop. The cortex reservation
    `CORTEX_VRAM_CORTEX_GB` is **8.6 GiB** and the subagent request `CORTEX_SUBAGENTS_VRAM_GB` is
    **3.5 GiB**, each a tier's own cost above the idle desktop baseline (the budget's unit; total
    used would count the desktop twice) plus a margin wider than the spread between samplers
    ([readings](../readings/subagent-budget.md)). The headroom is 5.4 GiB, so one spawn is
    GPU-placed and the next overflows, which is what one tier process serves. The CPU entry asks
    `cpus` 2.0 and `memory_gb` 3.0 (about 2.5 GiB RSS, rounded so two are admitted) against budgets
    of 4.0 and 8.0. Each number is a module constant in `config_subagents.py` (`DEFAULT_VRAM_GB`,
    `DEFAULT_CPUS`, `DEFAULT_MEMORY_GB`, `DEFAULT_CPU_BUDGET`, `DEFAULT_MEM_BUDGET_GB`) cited by
    the `Field` and by `SubagentRosterEntry`, and `scripts/crosscheck.py` compares it with every
    place it is written in `docker/docker-compose.subagents.yml`
    ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)); `mem_limit` equals `memswap_limit`,
    which is what keeps the container off swap. A deployment that changes the llama.cpp build, a
    tier's context, `--parallel` or the image token budget measures again the tier it changed.

15. **Where the processes run, and the caps they get.** The GPU-placed subagent tier is a hosted
    tier of the model-host supervisor on `:8083` with `-ngl 99`, opt-in through
    `CORTEX_MODEL_FILE_SUBAGENT_GPU` ([ADR-0053](ADR-0053-model-host-supervisor.md)); the CPU
    server is its own container. Routing is separate from hosting:
    `CORTEX_SUBAGENTS_GPU_ENDPOINT` defaults to the CPU server, so opting in is three settings
    together (the artifact, the endpoint, the tier's id in `CORTEX_SWAP_EVICT_MODELS`). Caps are
    per container (`cpus`, `mem_limit`, `memswap_limit`): on the CPU subagent container they are
    the hard twin of decision 4's soft budgets, and inside the supervisor the cortex, the deep
    model and the GPU subagent share one cgroup, so no per-model cap exists. llama.cpp maps the
    GGUF, so mapped pages count against the memory cap and a cap below the artifact makes a load
    thrash rather than fail.

16. **A task record may expire before its spawn is admitted.** `RedisTaskStore` keeps
    `cortex:task:{id}` and its result for 3600 s against a 7200 s wait. That is deliberate: `run`
    reads the task once, before `admit`, and keeps it through the wait; nothing reads a result
    back. The ordering is therefore not registered in `crosscheck.py`, and what the shorter life
    costs (an outcome in Redis with no record of what was asked) is what decision 9's log line
    covers.

## Consequences

- **What the placer does not model.** The record charges a tier's whole footprint per spawn
  although a resident tier allocates nothing for a second request, so refusing a second GPU spawn
  is a decode speed decision expressed as memory (backlog, inference and model manager area). An
  alternate model with no GPU executor still charges its `vram_gb`.
- **The soft budget is not a wall.** It limits only what it admitted; the per-container caps are
  the hard limit for the CPU server, and nothing caps GPU utilization: a GPU-placed subagent beside
  the cortex costs each 30 to 35 percent of its decode rate while both generate
  ([readings](../readings/subagent-budget.md#two-tiers-generating-at-once)).
- **A backend's lease serializes spawns sharing it.** One model in the list holds one backend per
  target, so its spawns overlap two ways at most, and only across targets.
- **Neither limit stops a subagent that keeps producing tokens**; the run deadline and the
  generation cap do ([ADR-0048](ADR-0048-generation-bounds.md)), and a stream that stops sending is
  cut by the stall timeout ([ADR-0005](ADR-0005-llamacpp-engine.md) decision 7).
- A spawn joining a hopeless queue still waits out the whole limit before it is refused (decision
  11 and the rejected queue-depth limit below).
- **The Intel NPU remains a possible third `PlacementTarget`.** Probed from this WSL2 guest, the
  NPU is projected as a compute-only adapter but no container can enumerate it, since the kernel
  lacks the accelerator subsystem and the vendor ships no Linux user mode driver
  ([readings](../readings/subagent-budget.md#the-npu-from-a-container)). The work reopens when
  `Core().get_property("NPU", "AVAILABLE_DEVICES")` answers anything inside a container.
- `brain/packages/orchestrator/tests/test_subagent_gpu_live.py` (integration-marked) drives both
  placements against live tiers from the deployment's own settings; the procedure is
  [subagents-cpu](../runbooks/subagents-cpu.md). Floating-point residue on the totals is limited by
  coarse config values, and drain completion counts an integer.

## Alternatives rejected

- **Placement-aware CPU charging.** `admit` runs before `place`, so charging a GPU spawn less needs
  a port change or the admit-after-place order that holds VRAM while waiting; and the discount buys
  nothing, since a model's overlap is capped at two by its backend locks, not by the budget.
- **A hard wall over what the scheduler never admitted**: that is a cgroup or `.wslconfig`, which
  the user ruled out, and no admission port can supply it.
- **Failing the turn on an impossible charge** (the old behaviour), **degrading it to the CPU**
  (a CPU placement costs more host CPU) or **refusing a temporarily full budget**.
- **A structured refusal kind on `SubagentResult`**: nothing would read it; the text distinguishes.
- **Keying the re-placement on llama-server's out-of-memory text**: untestable without the real
  message, and it would narrow the recovery to one cause.
- **A queue-depth limit.** The scheduler holds charges and no durations, and the hold is an upper
  bound where a depth rule needs a lower one: a depth of two would have refused six of the eight
  spawns in the measured batch. The waiters live only on the condition's deque, so it would also
  need a counter. It reopens with a deployment observed hitting the wait limit.
- **Raising the task TTL, or a `crosscheck.py` entry keeping it above the wait**: nothing re-reads a
  task after admission, so either would encode a relation nothing depends on.
- **A `max_gpu_subagents` setting**: a second dial for the constraint the fit test already is.

## Related

- Readings: [subagent budget](../readings/subagent-budget.md),
  [delegated run holds](../readings/delegated-run-holds.md),
  [co-residency](../readings/co-residency.md).
- Runbook: [subagents-cpu](../runbooks/subagents-cpu.md); host items in
  [docs/host/](../host/index.md#gpu-tier-scale).
- Modules: [brain-core](../modules/brain-core.md),
  [brain-orchestrator](../modules/brain-orchestrator.md).
- ADR-0010 (subagents), ADR-0030 (the brain handoff that drains the pool), ADR-0047, ADR-0048,
  ADR-0053, ADR-0054, ADR-0055.
