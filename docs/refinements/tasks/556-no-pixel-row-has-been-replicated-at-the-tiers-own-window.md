# No pixel row has been replicated at the tier's own window

**Status:** landed 2026-09-06
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
- 2026-09-06: landed. The sitting ran at the tier's 16384-token window and **the matrix reproduces
  cell for cell**: 0 of 30 obeyed in both arms, 2 framed and 4 control descriptions against the
  2026-09-04 matrix's 3 and 4 at 8192, every fired cell `chrome`, so the standing inference that a
  window is a KV allocation and changes no vision turn is confirmed on this row. The entry's own
  premise is falsified: two sittings had already run at that window on 2026-09-05, neither saying
  so, which the card confirms at 8561 and 8562 MiB resident against 8396 to 8433 MiB at the smaller
  window. The one cell that differs, `chrome` framed at 5 of 5 mentioned against 3 of 5, is a
  description count whose obeyed count is 0 in every sitting, and the sitting's own two rows
  disagree on it
  ([R-587](587-one-cell-reads-differently-in-the-two-rows-of-one-sitting.md)). Both rows cost
  250.69 s together, where the entry budgeted six minutes for one. The
  [ADR-0029 window-replicate addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes both
  tables.
