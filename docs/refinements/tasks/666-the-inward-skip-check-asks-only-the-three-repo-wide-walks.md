# The inward skip check asks only the three repo-wide walks

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

The inward half of `test_skippeddirs.py` enumerates the directories git ignores that exist in this
checkout, drops those a name in `SKIPPED_DIRS` already prunes, and reports any that still holds a
file a walk would read. It asked three walks, the ones that run over the whole repo and select by
suffix: the line cap, the anchor scan and the compose walk. Seven readers descend a tree through
`treewalk.py`. The four it did not ask are the dash ban, which needs nothing because its collection
is git's own answer, and three readers scoped to a subtree: `logcalls.py` over the brain's modules,
`assertedlines.py` over one suite, and `samplecheck.py` over the runbooks.

The argument for leaving it was that a scoped reader can only meet an ignored directory inside its
own subtree, and nothing here ignores anything under `brain/packages/` or `docs/runbooks/`: every
ignored directory below those roots is a `__pycache__`, which a name already prunes.

**What closed it.** The other three are asked the same question, by handing each ignored directory
to the reader's own selection rather than restating it: `logcalls.py`'s Python-module suffix,
`assertedlines.py`'s, and `samplecheck.py`'s runbook markdown.

## History

- 2026-09-14: opened by the close of
  [R-422](422-a-newly-ignored-tree-reaches-the-list-by-hand.md), which added the inward direction
  to `test_skippeddirs.py`.
- 2026-09-15: done, and the trigger had still not fired when it was. Git reports 46 ignored entries
  in this checkout, 42 of them directories that exist, and the four that survive the skip list are
  `body/app/src-tauri/gen`, `models`, `pgdata` and `sandbox`, none inside a scoped reader's subtree.
  Under `brain/packages/` git ignores 24 directories and all 24 are `__pycache__`; under
  `docs/runbooks/` it ignores none. The widening was made anyway, because the reason for leaving it
  is wrong about two of the three readers. The suffix half of the check walks from the ignored
  directory rather than from the repo root, so the line cap's own skips prune only what lies below
  that directory and its test-file naming rule still applies. A `.py` inside a `tests` directory
  below an ignored tree under a package's `src` is read by `logcalls.py` and by nothing in the
  suffix half, and a `.py` named like a test inside an ignored tree under a package's `tests` is
  read by `assertedlines.py` and by nothing in the suffix half. Both were planted and both were
  reported, and with the scoped half removed the suffix half reported neither
  ([ADR-0062](../../adr/ADR-0062-shared-check-readers.md) decision 4). The third reader,
  `samplecheck.py` over the runbooks, adds no reach, the anchor scan reading every `.md` here
  already, and it is asked with its own selection anyway so that the check states what each reader
  answers. The same reading opened
  [R-670](670-the-inward-skip-check-walks-from-the-ignored-directory.md).
