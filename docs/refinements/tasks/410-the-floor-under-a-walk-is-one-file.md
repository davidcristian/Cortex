# The floor under a walk is one file, so a collapsed scan still clears it

**Status:** open, fix when it bites
**Trigger:** an exclusion, a root or a walk changes and a gate's printed count drops without
anybody noticing, which is the same silence the count was added to break and the first evidence
that a floor of one is too low.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-24 by the close of
[R-409](409-a-gates-success-line-names-no-collection.md), which gave the four remaining cross-tree
scans a success line naming what they read and put a floor of one file under the two that had none.

`linecap.MIN_FILES` and `dashcheck.MIN_FILES` are both 1, and `composefiles.py` raises on a walk that
found no compose file. All three answer one question: did this scan enter the tree at all. None of
them answers the question a reader of the printed count actually has, which is whether it read as
much as it read yesterday. A line cap that measured 3 of 379 files, because a directory name
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
is the concrete first question.
