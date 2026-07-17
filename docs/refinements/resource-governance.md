# Resource governance

Deferrals from the Slice 8.5 resource-governance work, whose origin decision is
[ADR-0012](../adr/ADR-0012-resource-governance.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the
historical record of what each deferral became, and the index at [index.md](index.md) carries the
recommended pickup order.

**Open items:** CUDA-OOM re-place on CPU, the real GPU-placed runtime mechanism, the Intel NPU as
a third placement target, a bounded admission wait, a read timeout on the subagent HTTP client

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
- **CUDA-OOM → re-place on CPU.** `place` is optimistic; a real CUDA OOM surfaces as `ok=False` today.
  Auto-recovery (re-issue a CPU-forced request) needs a real GPU to exercise, so it lands in **Slice
  11** / the host half, not the pure core (simulating it would be vacuous coverage).
- **The real GPU-placed runtime mechanism.** Two live `llama-server` sidecars (GPU `-ngl 99` + CPU
  `-ngl 0`) in `docker/docker-compose.subagents.yml` + per-container `--cpus`/`--memory` cgroup caps + real
  GPU-placed-subagent validation lands with the **Slice 11** lifecycle behind the corrected ports.
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
  to CPU. **Reopens** with the Slice 11 GPU-placed runtime, as a port change rather than a tweak.
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
- **A read timeout on the subagent HTTP client.** *Fix when it bites.* The actual unbounded-wait
  hazard under the admission budget: `build_subagents` builds
  `httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)`, so one wedged `llama-server` stream holds
  its admission forever and every queued peer waits behind it. `read=None` is deliberate (a
  generation may legitimately stream for minutes on CPU), so the fix is a generous per-stream
  ceiling, not a short one, and it belongs to the inference adapter (ADR-0005), not the scheduler.
