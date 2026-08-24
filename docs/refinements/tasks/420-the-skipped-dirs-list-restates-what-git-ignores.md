# The hand-written skip list restates what git ignores, for every entry but one

**Status:** open, fix when it bites
**Trigger:** a directory is added to `.gitignore` and a walk keeps reading it, or one is removed
and a walk keeps skipping it, which is the first time the two lists disagreeing changes what a gate
sees.
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
