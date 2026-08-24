# A tree that joins .gitignore reaches the shared skip list only by hand

**Status:** open, fix when it bites
**Trigger:** a directory joins `.gitignore` and a walk that does not ask git keeps reading it,
which is the first time the two collections disagree about a tree that really exists.
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-24 by the close of
[R-420](420-the-skipped-dirs-list-restates-what-git-ignores.md), which measured the overlap
between `skippeddirs.SKIPPED_DIRS` and `.gitignore` and pinned it in a test.

That test reads one direction. It takes the ten names the list carries and asks git about each,
so a name that stops being a restatement, or starts being one, reddens. It says nothing about a
name `.gitignore` carries and the list does not. If a new tool's cache directory joins the ignore
file tomorrow, the dash ban skips it because its collection is git's answer, and the line cap, the
anchor scan and the compose walk read it, because their collection is a hand-written list of ten
names nobody told.

The consequence is small today and is not nothing: the cap would measure a generated file it did
not write, the anchor scan would judge a heading in a vendored document, and both would report a
count over a collection that includes somebody else's tree.

**Why it was left.** The close was about whether the list should exist at all, and it decided that
it should, for two names of ten. Widening the test to the other direction is a different question,
because git ignores plenty this repo has no opinion about: a stray `.env`, a `*.pyc`, three bind
targets full of GGUFs. The interesting subset is ignored **directories that actually exist and
that a walk would enter**, and picking that subset out of `git ls-files --others --ignored
--directory` is a judgement rather than a line.

**What would close it.** Decide whether the other direction is worth a test, and if so make it the
narrow one: enumerate the directories git ignores in this tree, drop those already pruned by name,
and report any that a walk would still descend into. That reads as a suggestion rather than a
rule, so it may belong in the module contract as a note to whoever edits `.gitignore` instead. The
honest alternative is to write down that the list is maintained by hand on purpose and that a new
ignore entry does not oblige anybody, which is defensible for exactly as long as no gate has been
embarrassed by a tree it read.
