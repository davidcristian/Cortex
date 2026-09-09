# The floor under a walk is one file, so a collapsed scan still clears it

**Status:** open, fix when it bites
**Trigger:** a printed count comes in below the reading this entry's trail records, with no commit
between the two runs that changed an exclusion, a root or a suffix. An exclusion changing and a
count dropping is not by itself the trigger: that happened two and a half hours after this entry
was opened, in a commit whose own subject was the exclusion.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-09

Opened 2026-08-24 by the close of
[R-409](409-a-gates-success-line-names-no-collection.md), which gave the four remaining cross-tree
scans a success line naming what they read and put a floor of one file under the two that had none.

`linecap.MIN_FILES` and `dashcheck.MIN_FILES` are both 1, and `composefiles.py` raises on a walk that
found no compose file. All three answer one question: did this scan enter the tree at all. None of
them answers the question a reader of the printed count actually has, which is whether it read as
much as it read yesterday. A line cap that measured 3 of 422 files, because a directory name
joined `SKIPPED_DIRS` or a suffix left `SOURCE_SUFFIXES`, clears the floor, prints 3, and exits 0.

**Why it was left.** The close decided that nothing may assert these counts, because prose or a
test quoting a gate's own data goes stale on the next file added to the repo. A floor of one is
the largest assertion that escapes that objection: it is a fact about the walk rather than about
the tree. Anything higher is a number somebody has to maintain.

**What would close it.** Decide whether the gap is worth closing at all, and the honest answer may
be no. The shapes worth weighing: a floor per gate set well under the real count and revisited
never (cheap, stale by construction, and it would have to be argued against the same objection);
a relative check against a recorded previous reading, which is a second file to maintain and a
merge conflict on every branch; or nothing at all, on the ground that a collapse of that size
comes from an edit to the gate itself, and an edit to the gate is reviewed. Note that `bindcheck`
and `defaultcheck` already carry the shape of the middle option in their suites, as guards on the
guard (`len(defaults) >= 6`, `len(repeated) >= 6`), which is a floor over the tree written where a
stale one fails the suite rather than passing unnoticed. Whether that pattern belongs in the other two suites
is the concrete first question, and it does not transplant as one line: both of those suites run
their gate over the repo root and can put a floor beside that run, while `test_linecap.py` and
`test_dashcheck.py` never read this repo at all, every test in both building a temporary tree
instead. A floor over the cap's or the dash ban's real count would be the first assertion either
suite makes about the tree it ships in.

## Trail

- 2026-09-08: the clause was narrowed, because the event the old one named had already happened.
  This entry was opened at 01:58 on 2026-08-24, and at 04:32 the same day the dash ban's walk
  gained a second exclusion, the paths git ignores. On today's tree that exclusion drops 28 files
  and 10991 lines from the printed count, measured by running `dashcheck.scan` twice with
  `ignored_paths` returning the empty set for the second run. So an exclusion changed, the count
  dropped, and the floor of one reported nothing, exactly as the entry predicted. Nobody was misled,
  because the change was deliberate and was the whole subject of its own commit, and the old clause
  could not tell those two apart. The narrowed clause names the falsifiable event instead, a count
  below the recorded reading with no commit accounting for it.
- 2026-09-08: the readings the clause is now against, from `just check-linecap` and
  `just check-dashcheck` at the repo root. `linecap OK: 422 non-test source file(s) under .. are
  within 300 lines, over 60321 line(s) counted`. `dashcheck OK: 1534 text file(s) under .. use no
  banned dash, over 292137 line(s) read`. The compose walk under the other two gates found 10
  compose files, reported by `just check-bindcheck` as `11 bind mount(s) ... over 10 compose
  file(s) and 22 landing(s) checked` and by `just check-defaultcheck` as `8 variable(s) spelled
  twice or more ... over 10 compose file(s) and 59 variable(s) read`. The cap read 379 files when
  this entry was written and reads 422 now, so no count has fallen.
- 2026-09-08: one reading against the middle option, which this entry cites as the shape already
  in the tree. `test_bindcheck.py`'s floor is `len(defaults) >= 6` and the tree carries exactly 6
  bind mounts with a substitution in the source, so that floor has no headroom left and would
  report the next removal. `test_defaultcheck.py`'s floor is `len(repeated) >= 6` against 8
  variables spelled more than once, so it would absorb two removals in silence. The two 6s were
  written two weeks apart against two different collections and neither has been revisited since,
  which is what a floor set well under the real count and never maintained looks like after a
  while.
- 2026-09-09: the readings again, the clause being written against the last one recorded here.
  `linecap OK: 426 non-test source file(s) under .. are within 300 lines, over 60859 line(s)
  counted`. `dashcheck OK: 1551 text file(s) under .. use no banned dash, over 296960 line(s)
  read`. Both compose gates still walk 10 files, at 11 bind mounts and 8 variables spelled twice
  or more. Every count is at or above the reading above it, so the trigger has not fired, and the
  two `MIN_FILES = 1` floors, the raising compose walk and the two suite floors of 6 all still
  stand as this entry describes them.
