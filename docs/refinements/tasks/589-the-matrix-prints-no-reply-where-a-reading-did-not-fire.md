# The matrix prints no reply where neither reading fired

**Status:** done 2026-09-06
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`score` printed a cell's reply only where a reading fired, so a matrix cell marked `ok` was blank:
nothing separated a model that ignored the screen from one that described it without quoting the
canary. The difference is real. All twenty framed draws of `chrome/output-laundering` described the
dialog, and the five the mention reading did not fire on named the formatting rule and stopped
before quoting it, so five `ok` marks would have stood for five descriptions. Every published pixel
matrix reads its resisted cells as resistance, and on this cell that reading is wrong. The two
five-draw rate rows had the same gap: `_print_fired` takes a `resisted` flag, and the matrix's
caller and `test_the_laundering_rate_at_each_frame` passed nothing.

## History

- 2026-09-06: opened by the close of
  [R-587](587-one-cell-reads-differently-in-the-two-rows-of-one-sitting.md), whose
  [ADR-0041](../../adr/ADR-0041-injection-image-variant.md) reads the five misses it printed.
- 2026-09-06: done, by printing the resisted replies of named cells. Cutting a reply short was
  rejected on the file's own reasoning, since the structural reading is at the reply's end, and
  printing everything was rejected on the row's size, sixty replies.
  `CORTEX_INJECTION_SHOW_RESISTED` names cells as the marks column writes them, or `all`, and is
  read on each call by `shows_resisted`; unset, nothing is printed, so no published matrix reads
  differently. It is wired at `score`, at `test_the_laundering_rate_at_each_frame` and into the
  payload-size row's existing condition. The runbook's matrix section says which marks a reader may
  take as resistance and how to read a cell's misses. The mutation table has a fourth row that
  measures zero, because the rate row's call site is inside a row that needs a GPU and no CI test
  reaches it, which is filed as
  [592](592-the-resisted-print-switch-has-never-been-set-on-a-live-row.md).
