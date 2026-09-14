# The inward skip check asks only the three repo-wide walks

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-14
**Trigger:** a directory git ignores appears under one of the three subtrees a scoped reader
descends, `brain/packages/` for `logcalls.py`, the package suite `assertedlines.py` is pointed at,
or `docs/runbooks/` for `samplecheck.py`, and holds a file that reader would open.

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
