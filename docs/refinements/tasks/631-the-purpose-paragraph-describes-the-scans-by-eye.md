# The Purpose paragraph describes the scans by eye

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)
**Trigger:** The Purpose paragraph of `docs/modules/repo-checks.md` is found describing a set of
cross-tree scans other than the one `scripts/scanrecipes.py` reads out of the justfile and the
workflow.
**Verified:** 2026-09-19

The paragraph runs through the fifteen checks as phrases, the cross-tree line cap, the
punctuating-dash ban and so on, and names no module. The roster scan compares names, so it cannot
check this passage, and checking it as descriptions would put a phrase per check into
`scripts/rosters.py`, a hand-written copy of the sentence's wording that fails whenever the sentence
is reworded. The paragraph has never been found short: it picked up the flag check on the day that
scan was added, while the workflow header did not, and the compose settings check in the commit that
added it, because it sits in the document that every new scan already edits twice, for the module
bullet and for the two checked rosters.

**What would close it.** If the trigger fires, the paragraph has shown that being in the edited file
is not enough, and there are two ways out: rewrite it to name each check beside its description so
the existing name-comparing scan covers it, or drop the run of phrases and let the checked paragraph
below it hold the list. If it never fires, this stays a record that one description of a checked set
is verified by eye, which is what [ADR-0044](../../adr/ADR-0044-document-rosters.md) decision 12
says it is.

## History

- 2026-09-11: opened by the close of
  [R-452](452-a-roster-written-in-descriptions-is-held-by-nobody.md), which decided that a
  description is not a roster and removed the one descriptive copy of the scan list that had gone
  out of date, the workflow header. This is the other descriptive copy, left as prose on purpose.
- 2026-09-13: checked again, and the trigger has not fired. `scripts/scanrecipes.py` reads eleven
  scans out of the justfile and the workflow, and the paragraph describes those same eleven before
  naming the three checks that are not cross-tree scans. Two sets moved under the paragraph since
  it was opened and neither was one of these: a fourteenth part joined the constant registry, and a
  third requirement joined the subagent flag rule. Both sit inside one scan rather than being a
  scan. The second did reach another description verified by eye, the engineering contract's
  sentence for that rule, which still named two requirements on the day a third was added; that
  sentence is completed in this change. It is the paragraph's own argument holding rather than
  failing: a description that lives in the file every addition already edits stays current, and one
  that does not goes out of date, a new requirement inside a scan editing only `scripts/`.
- 2026-09-19: checked again, and the trigger has not fired. `scan_modules` in
  `scripts/scanrecipes.py` now reads twelve scans out of the justfile and the workflow, the compose
  settings check having joined them on 2026-09-17, and the paragraph describes the same twelve
  before naming the three checks that are not cross-tree scans, fifteen in all. The scan that
  raised the count edited the paragraph in the commit that added it, so the argument above held a
  second time on a real addition. This entry's own body did not move with it and still counted
  fourteen checks; that count is repaired above.
