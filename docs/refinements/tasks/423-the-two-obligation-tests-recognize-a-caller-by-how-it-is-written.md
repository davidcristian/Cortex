# The two obligation tests recognize a caller by how it is written

**Status:** done 2026-09-08
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

Both tests find their callers by searching the source text of `scripts/*.py`. One looks for the
argv head `["git", ` and requires the file to also contain `git_env(`; the other looks for
`dirnames[:]` and requires `skippeddirs import`. Both then assert the offender list is empty, which
is the same pass a file the search did not recognize produces.

Each has a minimum against the emptiest version of that, naming three checks and four walks that
must be found, so a search matching nothing at all fails. The minimum does not cover the case that
matters: a fifth module that runs git through `subprocess.run(cmd)` with the argv built above, or a
walk that prunes with `dirnames.remove(...)` or filters a `glob`, is not a caller as far as either
search reaches, and nothing reports the omission.

The filtered-glob half is not hypothetical. `scripts/logcalls.py`, `scripts/samplecheck.py` and
`scripts/assertedlines.py` each read a tree with `Path.rglob` and then discard what falls inside
`SKIPPED_DIRS`, so all three import the shared list and follow the rule while containing no
`dirnames[:]` at all. The walk test does not see them, and a fourth such reader that forgot the
filter would pass it just as quietly.

## History

- 2026-08-24: opened by the closes of
  [R-419](419-the-git-call-inside-a-hook-is-written-three-times.md) and
  [R-420](420-the-skipped-dirs-list-restates-what-git-ignores.md), which each added a test
  requiring every caller of a shared thing to read it rather than copy it.
- 2026-09-07: trigger fired on the walk half, and the wording repaired. The old wording said the
  tests would report an empty offender list because they found no callers at all, and neither test
  can reach that state: both minimums are asserted as subsets before the offender list is examined.
  A search matching nothing fails on the minimum. What the entry is about is the opposite reading,
  a caller the search does not recognize and therefore does not cover.
- 2026-09-07: what fired it. `scripts/logcalls.py`, `scripts/samplecheck.py` and
  `scripts/assertedlines.py` each walk a tree with `Path.rglob` and filter the result against
  `SKIPPED_DIRS` rather than pruning a `dirnames` list in place, so none contains `dirnames[:]` and
  none is in `walkers`. All three arrived after this entry was opened: the first two with the
  log-sample check on 2026-08-26, the third with the proven-line reader on 2026-09-05. Nothing is
  wrong in the tree, since each one does read the shared list, but the obligation reached none of
  them and nothing said so.
- 2026-09-07: the git half has not fired. `scripts/*.py` contains the `["git", ` argv head in
  exactly the three files the minimum names, and the only other `subprocess.run` under `scripts/`
  is `imagedrift.py`, which runs `docker pull` and `docker image inspect`. Left open and actionable
  rather than closed, because widening the walk recognizer changes a check and needs a mutation
  table.
- 2026-09-08: closed, with the two halves answered differently. The descent moved to
  `scripts/treewalk.py`, which every one of the seven readers is now handed its files by, so the
  walk obligation is that one module descends and the rest do not, compared as an equality. The git
  call kept its own argv, the environment-versus-call argument holding on a re-reading of the three
  call sites, and the obligation moved from the file to the call: `scripts/scriptcalls.py` reads a
  module's syntax and answers which calls descend a tree and which are handed a git argv, with the
  function each hands to `env=`. The git half had fired too, which the reading that opened this
  missed by looking only at `scripts/*.py`: the suite beside the skip list runs git with an argv
  written one item per line, so the searched literal appears nowhere in it, and `test_gitenv.py`
  was counted a caller for containing that literal in a constant while running no git at all.
  `rostermembers._filenames` changed with them, from a glob handed its pattern to a listing plus a
  match, since a pattern the reader cannot see is answered as a descent. Recorded at
  [ADR-0062](../../adr/ADR-0062-shared-check-readers.md), decision 7; of nine planted mutations over
  the 1726-test scripts suite, four are cases the old searches all pass. It opened
  [R-610](610-the-descent-obligation-stops-at-the-suites.md), the tests being outside the set the
  obligation is compared over.
