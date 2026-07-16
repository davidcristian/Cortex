# Resource governance

Deferrals from the Slice 8.5 resource-governance work, whose origin decision is
[ADR-0012](../adr/ADR-0012-resource-governance.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the
historical record of what each deferral became, and the index at [index.md](index.md) carries the
recommended pickup order.

**Open items:** `SubagentScheduler.drain()` for a swap, CUDA-OOM re-place on CPU, the real
GPU-placed runtime mechanism, placement-aware CPU charging, the Intel NPU as a third placement
target, a hard budget wall

**Resource governance in Slice 8.5 ([ADR-0012](../adr/ADR-0012-resource-governance.md)):** each behind
the unchanged `SubagentPlacer`/`SubagentScheduler`/`ModelManager` ports.
- **`SubagentScheduler.drain()` for a swap.** Quiesce the subagent pool (evict → load brain → swap
  back). An additive method delivered in **Slice 11**, composed with `release`/`acquire` at the swap
  orchestrator, never merging the ports.
- **CUDA-OOM → re-place on CPU.** `place` is optimistic; a real CUDA OOM surfaces as `ok=False` today.
  Auto-recovery (re-issue a CPU-forced request) needs a real GPU to exercise, so it lands in **Slice
  11** / the host half, not the pure core (simulating it would be vacuous coverage).
- **The real GPU-placed runtime mechanism.** Two live `llama-server` sidecars (GPU `-ngl 99` + CPU
  `-ngl 0`) in `docker/docker-compose.subagents.yml` + per-container `--cpus`/`--memory` cgroup caps + real
  GPU-placed-subagent validation lands with the **Slice 11** lifecycle behind the corrected ports.
- **Placement-aware CPU charging.** `admit` charges every spawn its full `cpus`/`memory_gb` regardless
  of placement (conservative); charging GPU-placed subagents less is a tweak behind the same port.
- **The Intel NPU as a third placement target.** A future OpenVINO `InferenceBackend` adapter + a
  `PlacementTarget.NPU`, pending a feasibility pass (reachability from the dockerized WSL2 brain).
- **A hard budget wall.** The CPU/RAM budget bounds only what the scheduler *admits* (soft,
  admission-only, a deliberate tradeoff per ADR-0012 risks); hard enforcement remains a refinement
  behind the same `SubagentScheduler` port.
