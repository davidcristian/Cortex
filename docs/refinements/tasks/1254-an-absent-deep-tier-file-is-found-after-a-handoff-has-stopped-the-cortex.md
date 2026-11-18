# An absent deep-tier file is found after a handoff has stopped the cortex

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md)
**Verified:** 2026-11-18

The model host checks a tier's model file, projector and drafter when a `start` arrives
(`ModelFiles.missing`, called by `ModelSupervisor._spawn`). A swap sends the deep tier's `start`
after it has stopped the cortex and every evict id (`swap_in` in
[residency_moves.py](../../../brain/packages/core/src/cortex_core/residency_moves.py)), and
`status` answers `stopped` both for a tier that was never started and for one whose file is
absent. So a deployment whose `CORTEX_MODEL_FILE_BRAIN` or `CORTEX_MODEL_FILE_BRAIN_DRAFT` names
no file learns it at its first handoff, and every handoff after that stops the cortex and the GPU
subagent servers, fails, and loads all of them again. Boot recovery does not ask either.

Reproduced in process on 2026-11-18 with the real `ModelSupervisor`, `build_app` and
`HttpModelHost` over fake child processes, and a file check that answers no for the deep file
only. Before the swap the deep tier's `status` was `stopped`. `swap_in` then made these calls in
order: `status subagent-gpu`, `status subagent-gpu-2`, `stop cortex`, `stop subagent-gpu`,
`stop subagent-gpu-2`, `start brain`. The last was refused with HTTP 503 and `could not start
'brain': CORTEX_MODEL_FILE_BRAIN names '/models/brain.gguf', which is not a file in the model
host's container, so the model was not loaded`, and all four tiers then answered `stopped`.

What would close it: the host reports a tier whose files are absent without a `start` (for
example a field beside `models` on `GET /health`, read through a `ModelHost` verb as `roster` is),
the swap asks before its first stop as it does for the evict ids, and boot recovery logs the gap
where it compares the roster. A test fails when the cortex is stopped before the refusal.

## History

- 2026-11-18: filed from a reading of the file check beside the order of a swap's calls.
