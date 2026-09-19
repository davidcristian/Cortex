# The inward skip check walks from the ignored directory

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-checks.md)
**Verified:** 2026-09-19
**Trigger:** a directory git ignores that `SKIPPED_DIRS` does not prune is itself named `tests` or
`_generated`, the two names only the line cap skips, or sits below one, and holds a file the cap
selects by suffix and name. The check then reports a file the line cap would never have read.

Opened 2026-09-15 by the close of
[R-666](666-the-inward-skip-check-asks-only-the-three-repo-wide-walks.md), which measured the
imprecision while proving the widened check can fail.

The inward half of `test_skippeddirs.py` asks each reader what it would read **under the ignored
directory**, by walking from that directory. A walk that starts there cannot see the names above
it, so the line cap's two extra skips are applied to the wrong part of the path. The other two
repo-wide readers, the anchor scan and the compose walk, add no skip of their own, so a walk from
the directory gives exactly their answer. A `.py` directly inside `brain/packages/tools/tests/vendored/` is reported as a
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
and the check would hold one shape instead of two. Two of them can be asked today,
`backloganchors.markdown_files` and `composefiles.compose_files`; the line cap cannot, because
`linecap.scan` counts and returns only the files over the cap, so this means splitting the
selection out of `scan` into a function both it and the check call. The smaller alternative keeps
the walk and drops the cap's half for a directory whose own path from the root already carries a
name in `EXTRA_SKIPS`.

## Trail

- 2026-09-15: opened by the close of
  [R-666](666-the-inward-skip-check-asks-only-the-three-repo-wide-walks.md).
- 2026-09-19: re-derived and left open, the trigger unfired. Git still reports four ignored
  directories that `SKIPPED_DIRS` does not prune, `body/app/src-tauri/gen`, `models`, `pgdata` and
  `sandbox`, none of them named or below `tests` or `_generated`. Three things were repaired. The
  trigger named the line cap's two names twice over, once by spelling and once as "the two names
  only the line cap skips", and missed an ignored directory itself named `tests`, which the walk
  enters because `walk_files` never skips its own root; it now names both placements once. The
  paragraph above claimed the anchor scan's reach is misapplied too, and it is not:
  `backloganchors.markdown_files` walks with no skip beyond the shared list, so only the cap's
  half is imprecise. The remedy assumed each repo-wide reader could be asked for its files, and
  the line cap cannot yet, which the remedy now says.
