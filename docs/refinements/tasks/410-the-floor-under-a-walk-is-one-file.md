# The minimum under a walk is one file, so a collapsed scan still clears it

**Status:** open, waiting for its trigger
**Trigger:** a printed count comes in below the reading recorded in this entry's history, with no
commit between the two runs that changed an exclusion, a root or a suffix. An exclusion changing
and a count dropping is not by itself the trigger: that happened two and a half hours after this
entry was opened, in a commit whose own subject was the exclusion.
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)
**Verified:** 2026-09-19

`linecap.MIN_FILES` and `dashcheck.MIN_FILES` are both 1, `composefiles.py` raises on a walk that
found no compose file, and since 2026-09-17 `settingscheck.MIN_CLASSES` is 1, raising when no
composed service runs a module with settings. All four answer one question: did this scan enter the
tree at all. None answers the question a reader of the printed count actually has, which is whether
it read as much as it read yesterday. A line cap that measured 3 of 422 files, because a directory
name joined `SKIPPED_DIRS` or a suffix left `SOURCE_SUFFIXES`, clears the minimum, prints 3, and
exits 0.

A minimum of one is the largest assertion that escapes the rule that nothing may assert these
counts, because it is a fact about the walk rather than about the tree. Anything higher is a number
somebody has to maintain.

The shapes worth weighing: a minimum per check set well under the real count and never revisited
(cheap, stale immediately, and open to the same objection); a comparison against a recorded
previous reading, which is a second file to maintain and a merge conflict on every branch; or
nothing at all, on the ground that a collapse of that size comes from an edit to the check itself,
which is reviewed. Four compose checks already have the middle shape in their suites:
`bindcheck` (`len(defaults) >= 6`), `defaultcheck` (`len(repeated) >= 6`), `volumecheck`
(`scanned.declared >= 4`, `scanned.definitions >= 8`) and `flagcheck` (`scanned.servers >= 3`,
`artifacts >= 6`). Whether that pattern belongs in the cap's and the dash ban's suites is the first
concrete question, and it does not transplant as one line: both of those compose suites run their
check over the repo root, while `test_linecap.py` and `test_dashcheck.py` never read this repo at
all, every test in both building a temporary tree instead.

## History

- 2026-08-24: opened by the close of
  [R-409](409-a-gates-success-line-names-no-collection.md), which gave the four remaining
  cross-tree scans a success line naming what they read and put a minimum of one file under the two
  that had none.
- 2026-09-08: the trigger was narrowed, because the event the old one named had already happened.
  This entry was opened at 01:58 on 2026-08-24, and at 04:32 the same day the dash ban's walk
  gained a second exclusion, the paths git ignores. On that day's tree the exclusion drops 28 files
  and 10991 lines from the printed count, measured by running `dashcheck.scan` twice with
  `ignored_paths` returning the empty set for the second run. So an exclusion changed, the count
  dropped, and the minimum of one reported nothing, exactly as this entry predicted. Nobody was
  misled, because the change was deliberate and was the subject of its own commit, and the old
  trigger could not tell those two apart.
- 2026-09-08: the readings the trigger is now measured against, from `just check-linecap` and
  `just check-dashcheck` at the repo root. `linecap OK: 422 non-test source file(s) under .. are
  within 300 lines, over 60321 line(s) counted`. `dashcheck OK: 1534 text file(s) under .. use no
  banned dash, over 292137 line(s) read`. The compose walk under the other two checks found 10
  compose files, reported by `just check-bindcheck` as 11 bind mounts over 10 compose files and 22
  paths checked, and by `just check-defaultcheck` as 8 variables used more than once over 10
  compose files and 59 variables read. The cap read 379 files when this entry was written and reads
  422 now, so no count has fallen.
- 2026-09-08: one reading against the middle shape. `test_bindcheck.py`'s minimum is
  `len(defaults) >= 6` and the tree has exactly 6 bind mounts with a substitution in the source, so
  it has no headroom left and would report the next removal. `test_defaultcheck.py`'s minimum is
  `len(repeated) >= 6` against 8 variables used more than once, so it would absorb two removals
  without reporting them. The two 6s were written two weeks apart against two different
  collections and neither has been revisited.
- 2026-09-09: the readings again. `linecap OK: 426 non-test source file(s) under .. are within 300
  lines, over 60859 line(s) counted`. `dashcheck OK: 1551 text file(s) under .. use no banned dash,
  over 296960 line(s) read`. Both compose checks still walk 10 files, at 11 bind mounts and 8
  variables used more than once. Every count is at or above the reading above it, so the trigger
  has not fired, and the two `MIN_FILES = 1` minimums, the raising compose walk and the two suite
  minimums of 6 all still stand as described.
- 2026-09-14: the readings again. `linecap OK: 432 non-test source file(s) under .. are within 300
  lines, over 61831 line(s) counted`. `dashcheck OK: 1597 text file(s) under .. use no banned dash,
  over 312920 line(s) read`. Both compose checks still walk 10 files, at 11 bind mounts and 8
  variables used more than once. Every count is at or above the reading above it, so the trigger
  has not fired, and the minimums are unchanged.
- 2026-09-15: the readings again. `linecap OK: 432 non-test source file(s) under .. are within 300
  lines, over 61948 line(s) counted`. `dashcheck OK: 1616 text file(s) under .. use no banned dash,
  over 317821 line(s) read`. Both compose checks still walk 10 files, at 11 bind mounts and 8
  variables used more than once. The cap reads the same 432 files over 117 more lines, and every
  other count is above the one above it, so the trigger has not fired. The minimums are where they
  were, and `test_bindcheck.py` and `test_defaultcheck.py` still have `>= 6` against 6 and 8, so
  the first has no headroom and the second would still absorb two removals unreported. The claim
  about where the middle shape can go was checked and holds: both of those suites open with
  `REPO_ROOT = Path(__file__).resolve().parents[2]` and run their check over it, while
  `test_linecap.py` and `test_dashcheck.py` name no repo root anywhere.
- 2026-09-19: the readings again. `linecap OK: 438 non-test source file(s) under .. are within 300
  lines, over 63011 line(s) counted`. `dashcheck OK: 1643 text file(s) under .. use no banned dash,
  over 326587 line(s) read`. Both compose checks still walk 10 files, at 11 bind mounts and 8
  variables used more than once. Every count is above the one before it, so the trigger has not
  fired. The settings scan added on 2026-09-17 is a fifth walk with a printed count, and this is
  its first recorded reading: `settingscheck OK: the 134 field(s) of 14 settings class(es) read by
  brain, mcp-email, model-host are each named in that service's environment by one of 10 compose
  file(s), or exempt with a reason`. It brought a fourth minimum of one,
  `settingscheck.MIN_CLASSES`, and its suite asserts the three service names in the success line,
  which fixes the set over the tree rather than putting a minimum under it: any of those three
  services dropping out of the walk fails `test_the_committed_tree_passes`. The account of the
  middle shape was also short. `test_volumecheck.py` and `test_flagcheck.py` have had the same
  guard as the two suites this entry named, since 2026-08-25 and 2026-08-28, which is before the
  correction of 2026-09-08 that described only two. Against today's tree `declared >= 4` stands at
  4 volume paths and `servers >= 3` at 3 servers, so both have no headroom, while
  `definitions >= 8` absorbs three removals of 11 and `artifacts >= 6` one of 7.
- 2026-09-19: the line cap gained a second rule, decision and readings records at 250 lines, with
  its own minimum of one record and its own success line, whose first reading at the repo root is
  `linecap OK: 99 decision or readings record(s) under .. are within 250 lines, over 13823 line(s)
  counted`. That minimum has the same limit this entry describes: it catches a record directory
  that moved, not one that lost most of its records. The source line is unchanged by it.
- 2026-09-19: that second rule now covers every markdown file, not decision and readings records
  alone, so the reading later runs are compared against is `linecap OK: 863 markdown file(s) under
  .. are within 250 lines, over 58683 line(s) counted`, and the record count of 99 is not.
