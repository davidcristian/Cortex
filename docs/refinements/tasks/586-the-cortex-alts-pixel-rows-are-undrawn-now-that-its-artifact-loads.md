# The cortex alt's pixel rows are undrawn now that its artifact loads

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-06 by the close of
[R-580](580-the-cortex-alts-artifact-is-not-on-the-mount-and-the-row-reads-as-a-health-timeout.md),
which pointed the alt at the quant the mount holds.

`VISION_MODELS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
carries two entries and every published pixel number is the pick's. The alt's eight image rows, the
matrix and the rate at both frames and both budgets, have never been drawn, and until 2026-09-06
they could not be: the artifact they named was not on the mount. They can be now. The ADR-0029
image-arm addendum already says this row has a lineup entry and no matrix.

**Why it was left.** The alt's F32 projector puts roughly 1900 prompt tokens of picture in front of
the model against the pick's 450, so one matrix row is about an hour of card time and the eight
together are a night's, where the close that unblocked them was a decision about an artifact.

**What would close it.** One sitting of `-k "pixels and 9B and 1600x900 and 1024-image-tokens"`,
the alt at the corpus frame and the budget the stack ships, read against the pick's matrix at the
same frame and budget. The remaining seven rows are a separate night and can be filed from that
sitting's result.

## Trail

- 2026-09-06: opened by the close of
  [R-580](580-the-cortex-alts-artifact-is-not-on-the-mount-and-the-row-reads-as-a-health-timeout.md),
  whose [ADR-0004 alt-artifact addendum](../../adr/ADR-0004-model-lineup.md) names the artifact the
  rows now load.
