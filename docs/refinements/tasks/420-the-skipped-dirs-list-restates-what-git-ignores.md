# The hand-written skip list restates what git ignores, for every entry but one

**Status:** done 2026-08-24
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

`dashcheck.SKIPPED_DIRS` names ten directory components. Measured on the day the dash ban started
asking git what it ignores, git ignores nine of them wherever they appear in this tree, and the
tenth is `.git`, which git does not report as ignored because it is not part of the work tree. So
the list is one real entry and nine restatements of `.gitignore`, and nothing compares the two.

The list is read in three places, which is why it did not simply go away: `linecap.py` has its own
copy plus `tests` and `_generated`, compared with this one by
`test_skipped_dirs_match_dashcheck_plus_tests_and_generated`, and `backloganchors.py` imports this
one directly. Two of those three walks ask git nothing, so the list cannot shrink to `.git` without
either making them ask or accepting that they walk more than the dash ban does.

## History

- 2026-08-24: opened by the close of
  [R-411](411-the-dash-ban-reads-a-working-tree-not-a-commit.md), which made the dash ban ask git
  what it ignores and left the hand-written list beside the answer.
- 2026-08-24: closed as the second of the two options this entry offered, the collapse declined.
  Two of the three measurements above had moved. The overlap is eight of ten and not nine:
  `coverage` is ignored only under `body/app/`, by that tree's own `.gitignore`, so a `coverage/`
  at the root or under `brain/` is ignored by nothing and skipping it is this list's doing. And
  `backloganchors.py` did not import the dash ban's list, as this entry and the change that opened
  it both said; it had a hand-written twin of the same ten names that nothing compared with
  anything. There were four walks and four lists, `composefiles.py` keeping a shorter one of its
  own. The collapse was declined on the two real names and on the cost: the line cap, the anchor
  scan and the compose walk have no rule that mentions the repository, so making them fail on a
  root git cannot answer about would stop `just check` running outside a git working tree, which is
  a large narrowing to remove eight cheap names. What was added instead is the other option:
  `scripts/skippeddirs.py` holds the list and the argument, all four walks read it, the cap
  composes its two extra names in code so the relationship a test used to check cannot come apart,
  and the overlap with `.gitignore` is now measured against git's own answer in both directions.
  Six planted mutations; one of them replays the historical defect, a correct copy that no
  behaviour test in the tree can see. Two residues:
  [R-422](422-a-newly-ignored-tree-reaches-the-list-by-hand.md) and
  [R-423](423-the-two-obligation-tests-recognize-a-caller-by-how-it-is-written.md).
