# Boot recovery does not ask whether the deep tier can be started

**Status:** done 2026-11-23
**Area:** inference-model-manager
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)

A swap asks the model host for the deep tier's `start_gap` before its first stop
(`_refuse_a_start_the_host_would_refuse` in
[residency_moves.py](../../../brain/packages/core/src/cortex_core/residency_moves.py)), so a
deployment whose `CORTEX_MODEL_FILE_BRAIN` or `CORTEX_MODEL_FILE_BRAIN_DRAFT` names no file
learns it at its first handoff, with every model still running. Boot recovery compares the
host's roster with the evict list (`warn_of_unlisted_models` in
[residency_roster.py](../../../brain/packages/core/src/cortex_core/residency_roster.py)) and does
not ask this question, so the brain's boot log has no line for an absent deep-tier file.

What would close it: where boot recovery compares the roster it also asks `start_gap` for
`plan.brain_model` and logs one warning with the reason the host names, and a host that cannot
be asked logs that the question went unasked. A test fails when the warning is absent.

## History

- 2026-11-18: filed from a reading of boot recovery beside the swap's question about the deep
  tier.
- 2026-11-23: done as written; the premise held. `converge_residency` now ends with
  `warn_of_an_unstartable_deep_model`, which asks the deep tier's `start_gap` and logs the host's
  reason, or that it could not be asked. A deep tier the host does not serve adds no second line.
