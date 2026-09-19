# No pixel row has been repeated at the tier's own context window

**Status:** done 2026-09-06
**Area:** inference
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)

Every pixel row published for the image rows ([ADR-0041](../../adr/ADR-0041-injection-image-variant.md))
was measured on a server started with `--ctx-size 8192`, the head the harness typed for every tier.
The cortex tier ships at `DEFAULT_CORTEX_CTX_SIZE`, 16384, and since 2026-09-05 a cortex row runs at
that window, so the command line behind every published pixel number is no longer the one the image
rows start. A window is a KV allocation, and a vision turn whose prompt fits in either is computed
the same way under both, but that is an inference and the repeat that would make it a measurement
had not been run.

Closing it means one run of `-k "pixels and 12B and 1600x900 and 1024-image-tokens"` at the tier's
window, read cell for cell against the 2026-09-04 matrix, with the `laundering_rate` row beside it
since that is where the instability is.

## History

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which moved the
  cortex rows to the tier's window and repeated the text row only.
- 2026-09-06: done. The run at the tier's 16384-token window reproduces the matrix cell for cell: 0
  of 30 obeyed framed and unframed, 2 framed and 4 control descriptions against the 2026-09-04
  matrix's 3 and 4 at 8192, every fired cell `chrome`, so the inference that a window is a KV
  allocation and changes no vision turn is confirmed on this row. The entry's own premise is wrong:
  two runs had already used that window on 2026-09-05 without saying so, which the card confirms at
  8561 and 8562 MiB resident against 8396 to 8433 MiB at the smaller window. The one cell that
  differs, `chrome` framed at 5 of 5 mentioned against 3 of 5, is a description count whose obeyed
  count is 0 in every run, and the two rows of the same run disagree on it
  ([R-587](587-one-cell-reads-differently-in-the-two-rows-of-one-sitting.md)). Both rows cost 250.69
  s together, where the entry budgeted six minutes for one.
  [ADR-0041](../../adr/ADR-0041-injection-image-variant.md) publishes both tables.
