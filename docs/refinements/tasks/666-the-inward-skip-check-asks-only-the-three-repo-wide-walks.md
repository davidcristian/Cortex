# The inward skip check asks only the three repo-wide walks

**Status:** landed 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-09-14 by the close of
[R-422](422-a-newly-ignored-tree-reaches-the-list-by-hand.md), which added the inward direction to
`test_skippeddirs.py`: it enumerates the directories git ignores that exist in this checkout,
drops those a name in `SKIPPED_DIRS` already prunes, and reports any that still holds a file a
walk would read.

The three walks it asks are the ones that run over the whole repo and select by suffix: the line
cap, the anchor scan and the compose walk. Seven readers descend a tree through `treewalk.py`, and
the four it does not ask are the dash ban, which needs nothing because its collection is git's own
answer, and three readers scoped to a subtree: `logcalls.py` over the brain's modules,
`assertedlines.py` over one suite, and `samplecheck.py` over the runbooks. For those three the new
test says nothing at all.

**Why it was left.** The close was about the tree that had actually been read, `measurements/` at
the repo root, and the three repo-wide walks are the ones that reach a root-level ignore. A scoped
reader can only meet an ignored directory inside its own subtree, and nothing in this tree ignores
anything under `brain/packages/` or `docs/runbooks/` today: every ignored directory below those
roots is a `__pycache__`, which a name already prunes. Widening the check is a handful of lines,
and writing it now would add three selections to a test whose failure could not be produced.

**What would close it.** Ask the other three the same question, by handing each ignored directory
to the reader's own selection rather than restating it: `logcalls.py`'s Python-module suffix,
`assertedlines.py`'s, and `samplecheck.py`'s runbook markdown. The alternative is to say in the
module contract that the inward check covers repo-wide walks only, which is honest as long as no
scoped reader has ever met an ignored tree.

## Trail

- 2026-09-15: landed, and the trigger had still not fired when it did. Git reports 46 ignored
  entries in this checkout, 42 of them directories that exist, and the four that survive the skip
  list are `body/app/src-tauri/gen`, `models`, `pgdata` and `sandbox`, none of them inside a
  scoped reader's subtree. Under `brain/packages/` git ignores 24 directories and all 24 are
  `__pycache__`; under `docs/runbooks/` it ignores none.

  The widening landed regardless, because the reason this entry gave for leaving it is wrong about
  two of the three readers. The suffix half of the check walks from the ignored directory rather
  than from the repo root, so the line cap's own skips prune only what lies below that directory
  and its test-file naming rule still applies. A `.py` inside a `tests` directory below an ignored
  tree under a package's `src` is therefore read by `logcalls.py` and by nothing in the suffix
  half, and a `.py` named like a test inside an ignored tree under a package's `tests` is read by
  `assertedlines.py` and by nothing in the suffix half. Both were planted and both were reported,
  and with the scoped arm removed the suffix half reported neither: the table is in the
  [ADR-0026 scoped-reader addendum](../../adr/ADR-0026-prose-style-gates.md). The third reader,
  `samplecheck.py` over the runbooks, adds no reach, the anchor scan reading every `.md` here
  already, and it is asked with its own selection anyway so that the check states what each reader
  answers. The same reading opened
  [R-670](670-the-inward-skip-check-walks-from-the-ignored-directory.md): walking from the ignored
  directory is how the suffix half came to report a file the line cap would never have read.
