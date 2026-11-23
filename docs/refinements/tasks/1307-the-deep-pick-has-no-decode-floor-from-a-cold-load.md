# The deep pick has no decode floor from a cold load

**Status:** open, actionable
**Area:** resource-governance
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)
**Verified:** 2026-11-23

`CORTEX_SWAP_BRAIN_DECODE_TPS` is the spill watch's minimum: a deep reply decoding below it is
reported as a spill. For gemma-4-31B it was set from a cold load onto a clear card
([co-residency](../../readings/co-residency.md)). The deep pick, `Qwen3.8-27B-UD-Q4_K_M` at
16384 and `q8_0`, has its fit figure since 2026-11-23 (16924 MiB free plain, 17965 with its
draft layer, in the [model-swap](../../runbooks/model-swap.md) runbook) but no decode floor:
one reply each was decoded on a clear card on 2026-11-21, which is no floor.

The floor is a rate, so it is drawn only on a night whose card power limit matches the
baseline's, and it is drawn twice: plain, and drafting with the layer inside the file, on a
tool-call turn, as the runbook asks of a deployment that names the drafter.

What would close it: `brain/packages/inference/tests/test_decode_cadence_live.py` (or the cold variant's
driver) on the pick at the deep tier's argv as the model host starts it, from a cold load onto a
clear card, with the floor's rule written before the draw, and the two figures in the runbook.

## History

- 2026-11-23: filed when
  [R-741](741-a-qwen38-27b-deep-tier-has-no-measured-fit-figure-or-decode-floor.md) closed with
  the fit figure and the prompt cache row drawn; the night's power limit read above the
  baseline's, so no rate was drawn.
