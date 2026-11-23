# No test fails when the exception role leaves the keep reader

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-23

`may_keep` (`forget_inside.py`) keeps a row any word of `keeps` reads, and `keeps` holds the words
`beside` reads in the exception role (`roles[EXCEPTION]`). With that term removed, all 9,578 tests
of the brain core pass, and none of the 57,096 cases of the replay in
`~/.cache/cortex-run/2026-11-23/f3/` changes its listing (`f3_HEAD.json` against
`f3_m-no-exception.json` in `~/.cache/cortex-run/2026-11-23/a1/`). Either another term of `keeps`
already holds every word the exception role reads, or no test holds a form where only it keeps
the row.

## What to do

1. Find a message whose exception words neither `after_but`, a keep clause nor `after_value`
   reads, and write it as a test that fails without the term.
2. If none exists, show that the other terms hold every exception word and remove the term.

## History

- 2026-11-23: filed from a mutation pass over the keep readers.
