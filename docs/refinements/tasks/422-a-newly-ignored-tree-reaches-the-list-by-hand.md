# A tree that joins .gitignore reaches the shared skip list only by hand

**Status:** done 2026-09-14
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

The test that compares `skippeddirs.SKIPPED_DIRS` with `.gitignore` reads one direction. It takes
the ten names the list has and asks git about each, so a name that stops being a restatement, or
starts being one, makes the test fail. It says nothing about a name `.gitignore` covers and the
list does not. For such a name the dash ban skips the tree, because its collection is git's answer,
while the line cap, the anchor scan and the compose walk descend into it, because their collection
is a hand-written list that nothing updates.

The consequence is small and is not nothing: the cap would measure a generated file it did not
write, the anchor scan would check a heading in a vendored document, and both would report a count
over a collection that includes somebody else's tree.

Widening the test is a different question, because git ignores plenty this repo has no opinion
about: a stray `.env`, a `*.pyc`, three bind targets full of GGUFs. The interesting subset is
ignored directories that exist and that a walk would enter, and picking that subset out of
`git ls-files --others --ignored --directory` is a judgement rather than a line.

## History

- 2026-08-24: opened by the close of
  [R-420](420-the-skipped-dirs-list-restates-what-git-ignores.md), which measured the overlap
  between the list and `.gitignore` and fixed it in a test.
- 2026-09-07: trigger checked and not fired, and narrowed because its old form described the
  current state. `git ls-files --others --ignored --directory --exclude-standard` reports 44
  ignored directories that exist in this tree. Removing those matched by name against
  `SKIPPED_DIRS` leaves five the shared list does not cover, so a walk descends into every one:
  `body/app/src-tauri/gen/`, `measurements/`, `models/`, `pgdata/` and `sandbox/`. The old
  trigger's last half, that the two collections disagree about a tree that really exists, was true
  when the entry was written and no `.gitignore` line has changed since, so it could not come out
  false and could not fire.
- 2026-09-07: the harm has not happened, which is what the narrowed trigger now watches for. The
  three walks that do not ask git select by suffix: `linecap.scan` takes `SOURCE_SUFFIXES`,
  `backloganchors.markdown_files` takes `.md`, and `composefiles.compose_files` takes a
  `docker-compose*` or `compose*` `.yml` or `.yaml`. The five directories hold `gen/schemas`
  (JSON), `measurements/*.json`, nothing at all under `models/`, two `.dump` files under
  `pgdata/`, and `sandbox/hello.txt`. None holds a file any of the three reads.
- 2026-09-10: still not fired. `git ls-files --others --ignored --directory --exclude-standard` now
  reports 45 entries, three of which are files rather than directories (`body/coverage.json`,
  `brain/.coverage`, `scripts/.coverage`), so the directory set is the same five. None holds a
  `.py`, `.rs`, `.ts`, `.tsx`, `.md` or compose file. `.gitignore` has not been edited since
  2026-08-09.
- 2026-09-14: the trigger has fired. `measurements/` now holds three `.py` files and the line cap
  measures all three: `measurements/cache-ram-2026-09-13/gpuarm.py`,
  `measurements/cache-ram-2026-09-13/load.py` and
  `measurements/cache-ram-tiers-2026-09-13/tierarm.py`, 300 lines between them, which arrived with
  the host-RAM cache measurement. `linecap.py --root ..` reports `433 non-test source file(s) ...
  over 61946 line(s) counted`, and 3 of those files and 300 of those lines are in a tree this repo
  does not track. No fault is reported yet, because all three are under the cap and the longest is
  130 lines. The other four directories are unchanged, and the anchor scan and the compose walk
  still have nothing to read in any of the five. This settles the entry's own fork: the alternative
  it offered, writing down that the list is maintained by hand and that a new ignore entry obliges
  nobody, was defensible only for as long as no check reported a fault over a tree it should not
  have read, and one is now reading one.
- 2026-09-14: closed. `measurements` is a name in `SKIPPED_DIRS`, which is now eleven names of
  which nine restate git, and the narrow test this entry describes sits beside the module: it lists
  the directories git ignores that exist here, removes those a name already covers, and reports any
  that still holds a file the line cap, the anchor scan or the compose walk would read, each of the
  three asked with its own selection imported from its own module. The test was written before the
  skip and failed on the real tree, naming the three files under `measurements/`, which is the
  proof it can fail. The line cap's success line moved from `433 non-test source file(s) ... over
  61946 line(s)` to `430 ... over 61653`. Both counts in the module docstring were recomputed, and
  a measurement archive is named there as the fifth kind of tree the list covers. The close opened
  [R-666](666-the-inward-skip-check-asks-only-the-three-repo-wide-walks.md): the inward test asks
  the three repo-wide walks and says nothing about the three readers scoped to a subtree.
