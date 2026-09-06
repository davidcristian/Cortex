# The resisted-print switch has never been set on a live row

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** the next sitting that draws a pixel matrix or a laundering rate row on the GPU.

Opened 2026-09-06 by the close of
[589](589-the-matrix-prints-no-reply-where-a-reading-did-not-fire.md), whose mutation table has a
row measuring zero.

`CORTEX_INJECTION_SHOW_RESISTED` is read by `shows_resisted` and honoured at three call sites in
`brain/packages/inference/tests/test_injection_defense_live.py`: `score`, which both matrix rows
call, `test_the_laundering_rate_at_each_frame`, and the payload-size sweep. Only the first is
inside something a CI test reaches, so the mutation table proved the switch at `score` and at
`shows_resisted` and could not fail a mutant that removes it from the rate row. The two rate rows
carry it unrun.

The risk is small and specific: a wrong argument at one of those two call sites prints nothing
where a reader expects a cell's misses, and the reader learns it in the middle of the sitting that
needed them.

**What would close it.** One row drawn with the variable naming a cell, on the GPU, with the
printed replies read: the matrix at `chrome/output-laundering`, since that is the cell whose
misses were read by hand, and the rate row at `chrome`, which is the call site no test reaches.
Then a line in the ADR saying both were exercised, or a fix if either printed nothing.

## Trail

- 2026-09-06: opened by the close of
  [589](589-the-matrix-prints-no-reply-where-a-reading-did-not-fire.md), which landed the switch
  with CI evidence at `score` and none at the two rate rows.
