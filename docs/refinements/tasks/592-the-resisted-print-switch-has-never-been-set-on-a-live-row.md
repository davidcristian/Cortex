# The resisted-print switch has never been set on a live row

**Status:** done 2026-09-07
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`CORTEX_INJECTION_SHOW_RESISTED` is read by `shows_resisted` and used at three call sites in
`brain/packages/inference/tests/test_injection_defense_live.py`: `score`, which both matrix rows
call, `test_the_laundering_rate_at_each_frame`, and the payload-size row. Only the first is inside
something a CI test reaches, so the mutation table proved the switch at `score` and at
`shows_resisted` and could not fail a mutant that removes it from the rate row. A wrong argument at
either of the other two prints nothing where a reader expects a cell's misses, and the reader finds
out in the middle of the session that needed them.

## History

- 2026-09-06: opened by the close of
  [589](589-the-matrix-prints-no-reply-where-a-reading-did-not-fire.md), which added the switch with
  CI evidence at `score` and none at the two rate rows.
- 2026-09-07: done on the rate row's call site, in both directions on one row. Three rate rows ran
  on the card with `CORTEX_INJECTION_SHOW_RESISTED=chrome,plain`, which names two of the three cells
  a rate row can print. Every row printed all ten replies of `plain` and all ten of `chrome`, fired
  and resisted alike, and none of `app`'s ten, so the argument is right in both directions. What the
  misses said was the point of the switch: at `4800x2700` all five `plain` control replies name the
  formatting rule and none contains the token, so a cell reading 0 of 5 is the model reading the
  payload and not applying it. The matrix at `chrome/output-laundering` was not drawn, since that
  call site is the one the mutation table already proved and a matrix row is four minutes of card
  time for a print this session had already read. The payload-size row's call site is still
  unexercised and is opened as [596](596-the-payload-size-rows-resisted-print-argument-is-still-unrun.md).
  The runbook now says how each row writes its cell names, and the rows are
  [ADR-0041 decision 4](../../adr/ADR-0041-injection-image-variant.md).
