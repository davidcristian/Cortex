# The Purpose paragraph describes the scans by eye

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0003](../../adr/ADR-0003-seam-codegen.md)
**Trigger:** The Purpose paragraph of `docs/modules/repo-gates.md` is found describing a set of
cross-tree scans other than the one `scripts/scanrecipes.py` reads out of the justfile and the
workflow.

Opened 2026-09-11 by the close of
[R-452](452-a-roster-written-in-descriptions-is-held-by-nobody.md), which decided that a
description is not a roster and removed the one descriptive copy of the scan list that had
drifted, the workflow header. This is the other descriptive copy, and it is left as prose on
purpose.

The paragraph runs through the fourteen gates as phrases, the cross-tree line cap, the
punctuating-dash ban and so on, and names no module. The roster scan compares names, so it cannot
hold this passage, and holding it as descriptions would put a phrase per gate into
`scripts/rosters.py`, a hand-written copy of the sentence's wording that fails the gate whenever
the sentence is reworded. The paragraph has never been found short: it picked up the flag check on
the day that scan landed, while the workflow header did not, because it sits in the document every
scan addition already edits twice, for the module bullet and for the two held rosters.

**What would close it.** If the trigger fires, the paragraph has shown that being in the edited
file is not enough, and the choice reopens: rewrite it to name each gate beside its description so
the existing spelled shape holds it, or drop the run of phrases and let the held paragraph below it
carry the list. If it never fires, this stays a written record that one description of a held set is
checked by eye, which is what the origin decision's addendum of 2026-09-11 says it is.

## Trail

- 2026-09-11: opened by the close of
  [R-452](452-a-roster-written-in-descriptions-is-held-by-nobody.md). Recorded in the ADR-0003
  addendum of the same day on why a description is not a roster.
