# A power column with its unit only in the header is not searched

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-10-03
**Trigger:** a tracked document has a table column of power readings whose unit `W` is written
only in its header, such as `draw, W` or `(W)`, with bare numbers in the rows.

`scripts/prosecheck.py` reports a figure in watts or a clock unit through
`scripts/machinefigures.py`. A clock column is found from its header alone, because `MHz` and `GHz`
are never anything but units. A lone `W` is a letter as often as a unit, so the check reports it
only after a number, and a power column whose rows hold bare numbers under a header naming `W`
passes. That is the shape the history window record's memory clock column had before 2026-10-02,
with a power unit in place of the clock.

**Why it is not acted on now.** No tracked file has ever had such a column: `git log -G` over the
whole history finds no `(W)` or `(kW)`, and every wattage the rule rewrote had its number beside it.
Finding one needs the reader to know a table's header row from the separator row under it, which
the prose readers do not track today.

**What would close it.** Read a markdown table's header cells, the row above a separator of dashes,
and report a cell whose last word is `W` or `kW`, with a test over both header forms and a row that
is not a header.

## History

- 2026-10-03: filed by [R-663](663-a-figure-that-describes-only-this-machine-is-caught-by-eye.md),
  which added the figure search and named this as its one known miss.
