# The resisted-print switch has never been set on a live row

**Status:** landed 2026-09-07
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

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
- 2026-09-07: **landed on the rate row's call site, in both directions on one row.** Re-derived
  first and the entry describes the tree as it is: the switch is read at `score`, at the rate row
  and in the payload sweep, and only the first is inside a row a CI test reaches. Three rate rows
  ran on the card with `CORTEX_INJECTION_SHOW_RESISTED=chrome,plain`, which names two of the three
  cells a rate row can print. Every row printed all ten replies of `plain` and all ten of `chrome`,
  fired and resisted alike, and none of `app`'s ten, so the argument is right in both directions:
  a wrong one would have printed the unnamed rendering too or none of the named ones. What the
  misses said was the point of the switch: at `4800x2700` all five `plain` control replies name the
  formatting rule and none carries the token, so a cell reading 0 of 5 is the model reading the
  payload and not applying it. The entry's other half, the matrix at `chrome/output-laundering`,
  was not drawn, since that call site is the one the mutation table already proved and a matrix row
  is four minutes of card time for a print this sitting had already read. The sweep's call site is
  still unexercised and is opened as
  [596](596-the-payload-sweeps-resisted-print-argument-is-unrun.md). The runbook now says how each
  row spells its cell names, and the rows are the
  [ADR-0029 third-frame addendum](../../adr/ADR-0029-vision-screen-capture.md).
