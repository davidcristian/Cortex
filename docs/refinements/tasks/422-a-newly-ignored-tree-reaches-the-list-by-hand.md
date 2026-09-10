# A tree that joins .gitignore reaches the shared skip list only by hand

**Status:** open, fix when it bites
**Trigger:** a file one of the three walks reads appears inside a directory git ignores that
`SKIPPED_DIRS` does not name: a `.py`, `.rs`, `.ts` or `.tsx` for the cap, a `.md` for the anchor
scan, a `docker-compose*` or `compose*` `.yml` or `.yaml` for the compose walk. The bare
disagreement is not the trigger, because the two collections already disagree about five
directories that exist today.
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-10

Opened 2026-08-24 by the close of
[R-420](420-the-skipped-dirs-list-restates-what-git-ignores.md), which measured the overlap
between `skippeddirs.SKIPPED_DIRS` and `.gitignore` and pinned it in a test.

That test reads one direction. It takes the ten names the list carries and asks git about each,
so a name that stops being a restatement, or starts being one, makes the test fail. It says nothing about a
name `.gitignore` carries and the list does not. For such a name the dash ban skips the tree
because its collection is git's answer, while the line cap, the anchor scan and the compose walk
descend into it, because their collection is a hand-written list of ten names that nothing
updates.

The consequence is small today and is not nothing: the cap would measure a generated file it did
not write, the anchor scan would check a heading in a vendored document, and both would report a
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
ignore entry does not oblige anybody, which is defensible for exactly as long as no gate reports a
fault over a tree it should not have read.

## Trail

- 2026-09-07: trigger checked and not fired, and the clause narrowed because its old form
  described the standing state. `git ls-files --others --ignored --directory --exclude-standard`
  reports 44 ignored directories that exist in this tree. Pruning them by name against
  `SKIPPED_DIRS` leaves five the shared list does not cover, so a walk descends into every one of
  them: `body/app/src-tauri/gen/`, `measurements/`, `models/`, `pgdata/` and `sandbox/`. Every
  `__pycache__`, `.venv`, `.pytest_cache`, `.ruff_cache`, `target`, `dist`, `node_modules` and
  `.claude`, and `body/app/coverage/` under its own name, is already pruned. So the old clause's
  last half, that the two collections disagree about a tree that really exists, was true when the
  entry was written and no `.gitignore` line has changed since (`git log --since=2026-08-24 --
  .gitignore` is empty). It could not come out false and could not fire.
- 2026-09-07: the harm has not happened, which is what the narrowed clause now watches for. The
  three walks that do not ask git select by suffix: `linecap.scan` takes `SOURCE_SUFFIXES`,
  `backloganchors.markdown_files` takes `.md`, and `composefiles.compose_files` takes a
  `docker-compose*` or `compose*` `.yml` or `.yaml`. The five directories hold `gen/schemas`
  (JSON), `measurements/*.json`, nothing at all under `models/`, two `.dump` files under
  `pgdata/`, and `sandbox/hello.txt`. None of them holds a file any of the three reads, so no gate
  has yet counted or reported over a tree it should not have read. The entry stays open with the
  same two branches, and the narrowed clause is checkable in one command rather than being true
  already.
- 2026-09-10: still not fired, and the tree is where the last reading left it.
  `git ls-files --others --ignored --directory --exclude-standard` now reports 45 entries, three of
  which are files rather than directories (`body/coverage.json`, `brain/.coverage`,
  `scripts/.coverage`), so the directory set is the same five the last reading named:
  `body/app/src-tauri/gen/`, `measurements/`, `models/`, `pgdata/` and `sandbox/`. None of them
  holds a `.py`, `.rs`, `.ts`, `.tsx`, `.md` or compose file, so none of the three walks has a file
  to read there. `.gitignore` itself has not been edited since 2026-08-09.
