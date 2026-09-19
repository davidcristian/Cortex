# The line cap did not cover the overlay

**Status:** done 2026-08-03
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

`scripts/linecap.py` had `SOURCE_SUFFIXES = {".py", ".rs"}` from the day it was written, which was
correct then: [ADR-0001](../../adr/ADR-0001-architecture.md) open question 6 scoped both the
coverage rule and the 300-line cap to `.py` and `.rs` while the overlay was kept minimal. ADR-0011
decision 6 reversed that for coverage and said so; nothing reversed it for the cap, and nothing
reported the gap, because the scan kept passing.

It lasted thirty-three days, from the overlay's first covered component to 2026-08-03, over a tree
that reached 107 TypeScript files, 65 of them non-test sources the cap should have been measuring.
Two backlog entries tracked cap violations by eye over that window and both went stale.
`bridge/demoBridge.ts` was recorded at 326 lines on a day it already stood at 351, and was still
351 fourteen days later. `overlay/panelPlacement.ts` crossed the cap the day after the entry that
called `demoBridge.ts` the only file over it, reached 371, and stayed there for thirteen days
until an unrelated ResizeObserver change brought it to 295 by accident.

Fixed the day it was found, so this is a record rather than waiting work. The scan now covers
`.ts` and `.tsx`, using Vitest's own definition of a test file as its exclusion, and
`demoBridge.ts` was split rather than exempted. The whole decision, including what stays outside
the cap, is in ADR-0011 decision 12. Each new suffix was checked with a planted file before being
relied on.

## History

- 2026-08-03: Found while reviewing a recent change and fixed the same day. For thirty-three days
  AGENTS.md stated a line cap over a 65-module tree that nothing measured. The cap now covers
  `.ts` and `.tsx`, and `demoBridge.ts` was split rather than exempted. `proto/body.proto`, 314
  lines when this was recorded, is the other file deliberately outside the cap, since capping it
  would conflict with defining the body and brain interface once.
