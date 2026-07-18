# Resource governance

Deferrals from the Slice 8.5 resource-governance work, whose origin decision is
[ADR-0012](../adr/ADR-0012-resource-governance.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the
historical record of what each deferral became, and the index at [index.md](index.md) carries the
recommended pickup order.

**Open items:** the Intel NPU as a third placement target, a bounded admission wait, a read
timeout on the subagent HTTP client, the drain bound against a fired task's lease, admission
reopening onto a tier that would not restart

**Resource governance in Slice 8.5 ([ADR-0012](../adr/ADR-0012-resource-governance.md)):** each behind
the unchanged `SubagentPlacer`/`SubagentScheduler`/`ModelManager` ports.
- **`SubagentScheduler.drain()` for a swap landed 2026-07-17 with the brain-handoff drain
  sub-slice ([ADR-0030](../adr/ADR-0030-brain-handoff.md) decision 4, recorded at the
  [ADR-0012 drain addendum](../adr/ADR-0012-resource-governance.md)).** The entry read: "Quiesce
  the subagent pool (evict → load brain → swap back). An additive method delivered in **Slice
  11**, composed with `release`/`acquire` at the swap orchestrator, never merging the ports."
  It landed exactly there: `drain(*, timeout_s) -> bool` plus its reversal `undrain()` on the
  port, implemented by `ResourceBudgetScheduler` and the new `AdmitAllScheduler` fake under one
  contract suite. The semantics the original one-liner could not carry: entering drain refuses
  every `admit` (typed `SubagentAdmissionError`, `POOL_DRAINING_MSG`) instead of queuing, since
  a brain-phase spawn queued against its own drain would deadlock the turn against its own swap;
  a spawn already waiting on a full budget is woken and refused, not left to sleep through the
  handoff; the wait for in-flight admissions is bounded by the conductor-passed timeout
  (`CORTEX_SWAP_DRAIN_TIMEOUT_S`, default 60 s, arriving with the conductor's wiring) and a
  timeout reports not-clean with nothing killed, so the swap aborts before anything is evicted;
  and the window holds until `undrain`, which the conductor owes in a `finally` on swap-back and
  abort alike. The swap conductor that calls it is the ADR-0030 conductor sub-slice, which
  consumes this verb as landed.
- **CUDA-OOM re-place on CPU landed 2026-07-18 with the model-host sub-slice
  ([ADR-0012 re-place addendum](../adr/ADR-0012-resource-governance.md)).** The entry read:
  "**CUDA-OOM → re-place on CPU.** `place` is optimistic; a real CUDA OOM surfaces as `ok=False`
  today. Auto-recovery (re-issue a CPU-forced request) needs a real GPU to exercise, so it lands in
  **Slice 11** / the host half, not the pure core (simulating it would be vacuous coverage)."
  It landed as one CPU re-run after a GPU-placed failure with the re-place recorded in the result's
  `detail`, which is what ADR-0030's mapping asked for, but **not** keyed on a CUDA OOM: measured on
  the dev GPU, a 14.4 GB model started with `-ngl 99` on the 8 GB card does not fail at all, it
  spills to shared system memory under WSL2 and serves 177 s later, so a branch keyed on an OOM
  would have been unfireable here. The trigger is any GPU-placed attempt whose backend did not
  answer, which is reachable and which also mitigates the sibling entry below (admission reopening
  onto a tier that would not restart: every spawn placed on that tier fails at its backend, and now
  re-runs on the CPU instead of only reporting). The retry does **not** fire on a malformed
  constrained reply (a property of the model, not of where it ran), releases the GPU reservation
  before the re-run so headroom is never misreported to a concurrent spawn, re-uses the same
  admission and dispatch budget so it buys no second charge, and unions the two attempts' taint.
  The entry's own worry about vacuous coverage held up and is answered: the branch is proven by
  behaviour (a failing GPU backend, an answering CPU one) rather than by a simulated OOM, and each
  of its properties reddens a named test under mutation.
- **The real GPU-placed runtime mechanism landed 2026-07-18 with the model-host sub-slice, in a
  different container than this entry expected ([ADR-0030 model-host addendum](../adr/ADR-0030-brain-handoff.md)).**
  The entry read: "**The real GPU-placed runtime mechanism.** Two live `llama-server` sidecars (GPU
  `-ngl 99` + CPU `-ngl 0`) in `docker/docker-compose.subagents.yml` + per-container
  `--cpus`/`--memory` cgroup caps + real GPU-placed-subagent validation lands with the **Slice 11**
  lifecycle behind the corrected ports." Two of the three landed as written and one moved.
  ADR-0030 decision 3 relocated the GPU sidecar into the `model-host` supervisor container (the one
  holding the GPU reservation and the models mount), so the GPU-placed subagent is a **hosted tier**
  on :8083 with `-ngl 99` that `CORTEX_SUBAGENTS_GPU_ENDPOINT` points at, opt-in behind
  `CORTEX_MODEL_FILE_SUBAGENT_GPU`, rather than a second service in the subagents override; the CPU
  `-ngl 0` sidecar stays its own container as described. The caps landed on both containers
  (`cpus`/`mem_limit`/`memswap_limit`, verified applied by the runtime as `NanoCpus`/`Memory`/
  `MemorySwap`), with the CPU one's defaults set to the hard twin of the brain's soft admission
  budgets, which is what makes those budgets more than an honour system. **The granularity this
  costs is the interpretation to know about:** the cortex, the deep model and the GPU subagent are
  now processes in ONE cgroup, so no per-model CPU or RAM cap exists, only one cap set covering all
  three. ADR-0030 wins as the later and more specific decision, and its security argument is what
  buys it (a per-model cap would want a container per model, which is a controller that can start
  containers, which is the docker-socket shape decision 3 rejected). The numbers themselves are
  user-tunable placeholders: the 8 GB dev GPU cannot hold a real tier pair, so what was validated
  here is the mechanism, not the arithmetic. Real GPU-placed-**subagent** validation is the one
  piece still owed, and it is host-side for the same reason: a GPU-placed subagent only happens
  when `CORTEX_SUBAGENTS_VRAM_GB` fits under the soft cap minus the resident cortex, which needs a
  card that holds the cortex first.
- **Placement-aware CPU charging closed 2026-07-16 as declined, wrong premise and no gain
  ([ADR-0012 admission-wall addendum](../adr/ADR-0012-resource-governance.md)).** The entry read:
  "`admit` charges every spawn its full `cpus`/`memory_gb` regardless of placement (conservative);
  charging GPU-placed subagents less is a tweak behind the same port." It is not behind that port.
  `admit(request)` takes a `PlacementRequest`, which carries no placement, and `SubagentRunner.run`
  enters admission *before* it places, by ADR-0012 decision 5, so the charge cannot know the target.
  Making it placement-aware needs a port change (a target argument, or an `admit` yielding a
  re-chargeable handle) or the admit/place inversion decision 5 exists to prevent, where a
  GPU-placed spawn queuing for a CPU slot holds reserved VRAM while it waits. The discount would
  also buy nothing: each roster entry holds one `LlamaCppBackend` per target and a backend holds its
  model lease for the whole stream, so same-entry spawns serialize there whatever the budget admits
  (measured live on the Qwen-2B override: two concurrent spawns took 4.8 s through two backend
  objects, 10.0 s through one, a ratio of 2.08). And there is nothing to discount today, since
  `CORTEX_SUBAGENTS_VRAM_GB=5.5` sits deliberately above the GPU headroom, so every spawn overflows
  to CPU. **Reopens** with a second GPU-capable executor, as a port change rather than a tweak.
  **The GPU-placed runtime arrived on 2026-07-18 and did not reopen it**, which is worth stating
  because this entry used to name that runtime as the condition. One hosted GPU subagent tier is
  still one `LlamaCppBackend` per target per roster entry, so the measured serialization above is
  unchanged and the discount would still buy nothing; and the shipped `CORTEX_SUBAGENTS_VRAM_GB=5.5`
  still sits above the headroom, so there is still nothing to discount. What would reopen it is what
  ADR-0030 decision 8's addendum already says: a **second** GPU-capable executor, so that two
  GPU-placed spawns can actually run at once and a placement-aware charge changes how many are
  admitted.
- **The Intel NPU as a third placement target.** A future OpenVINO `InferenceBackend` adapter + a
  `PlacementTarget.NPU`, pending a feasibility pass (reachability from the dockerized WSL2 brain).
- **A hard budget wall closed 2026-07-16: the wall existed and now refuses as a value
  ([ADR-0012 admission-wall addendum](../adr/ADR-0012-resource-governance.md)).** The entry read:
  "The CPU/RAM budget bounds only what the scheduler *admits* (soft, admission-only, a deliberate
  tradeoff per ADR-0012 risks); hard enforcement remains a refinement behind the same
  `SubagentScheduler` port." Two corrections. **That reading is impossible behind that port:** hard
  enforcement over processes the scheduler never admitted is a cgroup/`.wslconfig` capability the
  user's ADR-0012 constraint rules out, and a port that only sees admissions cannot supply it.
  **At ADR-0012 decision 4's own reading** (refuse instead of queue) a wall already existed: a
  charge larger than the whole budget raised rather than waiting forever. Its *boundary behaviour*
  was the defect. The bare `ValueError` escaped `SubagentRunner.run`, `SpawnSubagentsTool`'s
  `gather` (discarding every sibling's answer), and `ToolDispatcher`, which catches only
  `ToolError`, reaching `converse.py`'s broad turn handler, which failed the turn with
  `ERROR_CODE_INTERNAL` and left the whole `Converse` stream refusing further turns; and
  `SubagentsConfig` never checked an ask against the budget, so env alone could reach that state.
  What landed: the typed `SubagentAdmissionError` on the port, caught by the runner and
  degraded to an `ok=False` "refused before running" `SubagentResult`, plus a boot-time config
  check that no roster entry asks more than the whole budget. A transient full budget still
  **queues**, deliberately: the work runs seconds later, depth-1 drains the queue, and a waiting
  spawn holds none of the budget, so refusing it saves nothing. Also noted: with respect to what it
  charges the budget was already hard; "soft" only ever meant that it binds nothing it did not
  admit. Behind it, two new entries below.
- **A bounded admission wait.** *Fix when it bites.* Admission waits with no timeout and no
  queue-depth bound. Depth-1 guarantees the queue drains while admitted runs terminate, and
  `MAX_SPAWN_BATCH` bounds one call, so nothing is unbounded in practice today. The trigger is a
  real deployment showing a turn stalled in admission long enough to matter; the fix is a timeout
  design over a `Clock`, refusing with the same typed error, not a policy flip.
- **The drain bound is shorter than a fired task's lease, so a task in flight aborts a handoff.**
  *Fix when it bites.* Opened 2026-07-17 by the brain-handoff conductor sub-slice, which wired
  `CORTEX_SWAP_DRAIN_TIMEOUT_S` (default 60 s) as the bound on quiescing the pool before anything
  is evicted. A ticker-fired task holds its admission for up to the schedule lease
  (`CORTEX_SCHEDULE_LEASE_S`, default 300 s), so a handoff requested while one is running drains
  to a timeout and correctly aborts before evicting anything: the user is told, the cortex keeps
  serving, and nothing is lost. That is the designed direction, but with the shipped defaults it
  makes an escalation during a scheduled task systematically impossible rather than occasionally
  unlucky. The knobs already exist (raise the drain bound above the lease, or lower the lease), so
  the fix is a defaults decision informed by real usage, not a design change; the trigger is a
  deployment where scheduled work and escalation collide often enough to notice. Killing a
  subagent mid-stream to make the drain succeed stays refused (v1 never does).
- **Admission reopens even onto a tier the swap back could not restart.** *Fix when it bites.*
  Opened 2026-07-18 by the pass that made the drain window wait for the standing residency, and
  recorded at the [ADR-0030 reopening addendum](../adr/ADR-0030-brain-handoff.md), that ADR owning
  both halves that create it (the best-effort tier restart and the reopening that follows the
  restore) while this port stays unchanged. The
  window now lifts only after the residency scope has restored the cortex and restarted every
  `evict_models` tier, and every reopening is witnessed against what was actually running. But
  the tier restart is deliberately best effort ([ADR-0030](../adr/ADR-0030-brain-handoff.md)
  decision 4: a tier that will not come back must not be reported as the cortex being gone), so a
  `ModelHostError` on that start is logged and swallowed, and `undrain` then reopens admission
  onto a subagent server that is not running. The next delegated run fails at its backend and
  degrades to an `ok=False` result, which is honest but wasteful, and nothing retries the tier
  until the next handoff or a restart. **Reachable by configuration since 2026-07-18**, which
  replaces this entry's original "nothing is at stake today, `CORTEX_SWAP_EVICT_MODELS` is empty
  until the real lifecycle sub-slice, so no tier is ever evicted": that sub-slice has landed, so a
  deployment that names a GPU subagent artifact and lists that tier in `CORTEX_SWAP_EVICT_MODELS`
  now really does evict it and can really see it refuse to come back. It stays unreachable in the
  **shipped defaults** (both of those are empty), and its cost fell in the same sub-slice: a spawn
  placed on a tier that did not restart now re-runs once on the CPU rather than only reporting, so
  what is left is a wasted GPU attempt per spawn instead of a lost one. Still recorded rather than
  built, for the same reason. The fix wants the residency
  state the honesty-surfaces sub-slice introduces (a tier known to be down, so the placer skips it
  and something retries the start) rather than a scheduler change, which is why it is recorded
  here and not built: keeping the pool drained instead would be worse, since it would trade every
  delegated run for the ones that would have been placed on that one tier.
- **A read timeout on the subagent HTTP client.** *Fix when it bites.* The actual unbounded-wait
  hazard under the admission budget: `build_subagents` builds
  `httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)`, so one wedged `llama-server` stream holds
  its admission forever and every queued peer waits behind it. `read=None` is deliberate (a
  generation may legitimately stream for minutes on CPU), so the fix is a generous per-stream
  ceiling, not a short one, and it belongs to the inference adapter (ADR-0005), not the scheduler.
