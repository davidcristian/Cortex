# The matrix prints no reply where neither reading fired

**Status:** landed 2026-09-06
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-06 by the close of
[R-587](587-one-cell-reads-differently-in-the-two-rows-of-one-sitting.md), whose twenty draws showed
what an unfired reply says.

`score` prints a cell's reply only where a reading fired, so a matrix cell marked `ok` is a blank:
nothing separates a model that ignored the screen from one that described it without quoting the
canary. The close measured that the difference is real. All twenty framed draws of
`chrome/output-laundering` described the dialog, and the five the mention reading did not fire on
named the formatting rule and stopped before quoting it, so five `ok` marks would have stood for
five descriptions. Every published pixel matrix reads its resisted cells as resistance, and on this
cell that reading is wrong.

The two five-per-arm rate rows have the same gap: `_print_fired` takes a `resisted` flag and the
matrix's caller passes nothing, `test_the_laundering_rate_at_each_frame` passes nothing, and only
the deep row and the payload-size sweep pass it.

**Why it was left.** A matrix prints 60 arms per row and printing every reply would make the row's
own marks hard to find, which is the reason the printing was written to fire on a reading in the
first place. What is wanted is a way to read a chosen cell's misses rather than all of them.

**What would close it.** Decide what a matrix prints for a resisted cell and land it: a reply
truncated to its first clause on every resisted arm, an unconditional print behind a flag the
harness reads from the environment, or the resisted replies of one named cell. Then say in the
runbook which cells a reader may treat as resistance and which need their reply read.

## Trail

- 2026-09-06: opened by the close of
  [R-587](587-one-cell-reads-differently-in-the-two-rows-of-one-sitting.md), whose
  [ADR-0029 one-rate addendum](../../adr/ADR-0029-vision-screen-capture.md) reads the five misses
  it printed.
- 2026-09-06: landed as the third of the three closes it offered, the resisted replies of named
  cells. Truncation was rejected on the file's own reasoning: a resisted reply is printed whole
  when it is printed at all, because the structural reading is on the tail. An unconditional print
  was rejected on the row's size, sixty arms. `CORTEX_INJECTION_SHOW_RESISTED` names cells as the
  marks column spells them, or `all`, and is read on each call by `shows_resisted`; unset, nothing
  is printed, so no published matrix is re-read differently. It is wired at `score`, at
  `test_the_laundering_rate_at_each_frame` and into the payload sweep's existing condition. The
  runbook's matrix section says which marks a reader may take as resistance and how to read a
  cell's misses. The ADR-0029 addendum of that date carries the mutation table, whose fourth row
  measures zero: the rate row's call site is inside a row that needs a GPU, so no CI test reaches
  it. The switch is proven at `score` and `shows_resisted`, and no live sitting has yet been drawn
  with the variable set.
