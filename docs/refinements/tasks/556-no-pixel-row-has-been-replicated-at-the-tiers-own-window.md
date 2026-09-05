# No pixel row has been replicated at the tier's own window

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-05 by the close of
[R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which made
every row of the injection harness start with its tier's own command line.

Every pixel row the ADR-0029 image-arm, frame-pair, image-budget and payload-size addenda publish
was measured on a server started with `--ctx-size 8192`, the head the harness typed for every
tier. The cortex tier ships at `DEFAULT_CORTEX_CTX_SIZE`, 16384, and since 2026-09-05 a cortex row
runs at that window, so the command line behind every published pixel number is no longer the one
the arm starts. A window is a KV allocation, and a vision turn whose prompt fits in either is
computed the same way under both, but that sentence is an inference and the replicate that would
make it a reading has not been run.

**Why it was left.** One `pixels` row is six minutes of card time at the corpus frame and the
shipped budget, and the close that changed the window was about the text arm's head; the image
arm's numbers were not the thing under measurement.

**What would close it.** One sitting of `-k "pixels and 12B and 1600x900 and 1024-image-tokens"`
at the tier's window, read cell for cell against the 2026-09-04 matrix, with the `laundering_rate`
row beside it since that is where the arm's instability lives.

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which moved
  the cortex rows to the tier's window and replicated the text row only.
