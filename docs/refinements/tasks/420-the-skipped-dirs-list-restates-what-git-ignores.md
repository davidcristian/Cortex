# The hand-written skip list restates what git ignores, for every entry but one

**Status:** landed 2026-08-24
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-24 by the close of
[R-411](411-the-dash-ban-reads-a-working-tree-not-a-commit.md), which taught the dash ban to ask
git what it ignores and left `SKIPPED_DIRS` beside the answer.

`dashcheck.SKIPPED_DIRS` names ten directory components. Measured on the day the ignore consult
landed, git ignores nine of them wherever they appear in this tree, and the tenth is `.git`, which
git does not report as ignored because it is not part of the work tree at all. So the list is one
real entry and nine restatements of `.gitignore`, and nothing compares the two.

The list is read in three places, which is why it did not simply go away: `linecap.py` carries its
own copy plus `tests` and `_generated`, held to this one by
`test_skipped_dirs_match_dashcheck_plus_tests_and_generated`, and `backloganchors.py` imports this
one directly. Two of those three walks do not ask git anything, so the list cannot shrink to `.git`
without either teaching them to ask or accepting that they walk more than the dash ban does.

**Why it was left.** The close was about the dash ban's collection, and shrinking a list two other
walks read is a change to theirs. Keeping the list also keeps the walk cheap in the ordinary case,
pruning before any question is asked.

**What would close it.** Decide whether the other two walks should ask git as well. If they should,
the list collapses to `.git` everywhere and `.gitignore` becomes the one place a skipped tree is
named, at the cost of making the line cap and the anchor scan refuse a root git cannot answer
about, which is a real narrowing of both. If they should not, the honest close is the opposite one:
say in the module contract that the list is deliberately independent of `.gitignore`, and consider
holding the overlap to it the way the two gates' lists are already held to each other.

## Trail

- 2026-08-24: opened by the close of
  [R-411](411-the-dash-ban-reads-a-working-tree-not-a-commit.md), which taught the dash ban to ask
  git what it ignores and left the hand-written list beside the answer.
- 2026-08-24: landed as the second of the two closes this entry offered, the collapse declined.
  **Two of the three measurements above had moved.** The overlap is **eight** of ten and not nine:
  `coverage` is ignored only under `body/app/`, by that tree's own `.gitignore`, so a `coverage/`
  at the root or under `brain/` is ignored by nothing and skipping it is this list's doing. And
  `backloganchors.py` did not import the dash ban's list, as this entry and the addendum that
  opened it both said; it carried a hand-written twin of the same ten names that nothing compared
  to anything, so the drift feared here was already in the tree. There were four walks and four
  lists, `composefiles.py` keeping a shorter one of its own. The collapse was declined on the two
  real names and on the cost: the line cap, the anchor scan and the compose walk have no rule that
  mentions the repository, so making them refuse a root git cannot answer about would stop
  `just check` running outside a git working tree, which is a large narrowing to remove eight
  cheap names. What landed instead is the opposite close this entry named: `scripts/skippeddirs.py`
  holds the list and the argument, all four walks read it, the cap composes its two extra names in
  code so the relationship a test used to hold cannot drift, and the overlap with `.gitignore` is
  now measured against git's own answer in both directions. Six planted mutations, tabled in the
  ADR-0026 skip-list addendum; one of them replays the historical defect, a correct copy that no
  behaviour test in the tree can see. Two residues:
  [R-422](422-a-newly-ignored-tree-reaches-the-list-by-hand.md) and
  [R-423](423-an-obligation-test-knows-a-caller-by-its-spelling.md).
