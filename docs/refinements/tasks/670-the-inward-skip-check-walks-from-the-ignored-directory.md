# The inward skip check walks from the ignored directory

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-15
**Trigger:** a directory git ignores that `SKIPPED_DIRS` does not prune appears below a `tests` or
`_generated` directory, or below one of the two names only the line cap skips, and holds a source
file. The check then reports a file the line cap would never have read.

Opened 2026-09-15 by the close of
[R-666](666-the-inward-skip-check-asks-only-the-three-repo-wide-walks.md), which measured the
imprecision while proving the widened check can fail.

The inward half of `test_skippeddirs.py` asks each reader what it would read **under the ignored
directory**, by walking from that directory. A walk that starts there cannot see the names above
it, so the line cap's two extra skips and the anchor scan's own reach are applied to the wrong
part of the path. A `.py` directly inside `brain/packages/tools/tests/vendored/` is reported as a
file the cap reads, and the cap reads no such file: it never enters `tests` at all. The fault
would name a real file and a real ignored tree, and the remedy it suggests, a name in
`SKIPPED_DIRS`, would be the right remedy for the wrong reason.

**Why it was left.** It reports too much rather than too little, so it cannot hide a tree a gate
is really reading, and the direction it errs in is the safe one for a gate. It also cannot fire
today: the four ignored directories that survive the list sit at the repo root or under
`body/app/`, none of them below a name the cap skips.

**What would close it.** Ask each reader over the whole repo once and intersect its answer with
the ignored directories, which is what the scoped half already does, rather than walking from each
directory. The three repo-wide readers would then be asked the same way as the three scoped ones
and the check would hold one shape instead of two.
