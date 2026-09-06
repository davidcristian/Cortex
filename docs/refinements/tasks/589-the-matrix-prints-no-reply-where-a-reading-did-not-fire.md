# The matrix prints no reply where neither reading fired

**Status:** open, actionable
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
