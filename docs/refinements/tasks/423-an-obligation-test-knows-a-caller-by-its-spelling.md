# The two obligation tests recognize a caller by how it is spelled

**Status:** open, actionable
**Trigger:** fired on 2026-09-07. A module under `scripts/` reads a directory tree or runs git in
a shape neither test's search recognizes, so the obligation passes over it and nothing reports the
omission. Three such tree readers exist, all of them filtered recursive globs.
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-24 by the closes of
[R-419](419-the-git-call-inside-a-hook-is-written-three-times.md) and
[R-420](420-the-skipped-dirs-list-restates-what-git-ignores.md), which each landed a test holding
every caller of a shared thing to reading it rather than copying it.

Both find their callers by searching the source text of `scripts/*.py`. One looks for the argv
head `["git", ` and demands the file also spell `git_env(`; the other looks for `dirnames[:]` and
demands the file also spell `skippeddirs import`. Both then assert the offender list is empty,
which is a green a file the search did not recognize also produces.

Each carries a floor against the emptiest version of that, naming three gates and four walks that
must be found, so a search that matched nothing at all fails. The floor does not cover the case
that matters: a fifth module that runs git through `subprocess.run(cmd)` with the argv built
above, or a walk that prunes with `dirnames.remove(...)` or filters a `glob`, is not a caller as
far as either test's search reaches, and the obligation does not apply to it, with nothing
reporting the omission.

The filtered-glob half of that sentence is no longer hypothetical. `scripts/logcalls.py`,
`scripts/samplecheck.py` and `scripts/assertedlines.py` each read a tree with `Path.rglob` and
then discard what falls inside `SKIPPED_DIRS`, so all three import the shared list and honour the
rule while spelling no `dirnames[:]` at all. The walk test does not see them, and a fourth such
reader that forgot the filter would pass it just as quietly.

**Why it was left.** Both tests were written to hold a trigger that a shared module cannot hold by
existing, and they do hold the shapes this tree actually writes: every git call here is a fixed
argv list and every walk here is `root.walk()` with its directory list pruned in place. Widening
the recognizer means either a real parse of the module, which is a lot of machinery for a rule two
files obey, or a broader text match with false positives that would have to be excused one by one.

**What would close it.** Decide whether a source-text obligation is the right instrument at all.
The cheaper alternative is to move the question to the thing being shared: a git call could go
through a runner after all, and a walk could go through a shared iterator, so a caller that does
not use it is not a caller by construction rather than by search. The environment-versus-call
argument was already weighed and lost once, and the same argument does not obviously apply to a
tree walk, which is one shape with no per-caller policy in it. If instead the tests stay as they
are, an `ast` walk over each module would at least recognize a call whose argv is built one line
earlier, which is the near miss both of them share.

## Trail

- 2026-09-07: trigger fired, on the walk half, and the clause repaired. The old clause said the
  tests would report an empty list of offenders because they found no callers at all, and that is
  a state neither test can reach. Both floors are asserted as subsets before the offender list is
  ever examined: `{"bindcheck.py", "commitlint.py", "dashcheck.py"} <= callers` in
  `scripts/tests/test_gitenv.py`, and `{"backloganchors.py", "composefiles.py", "dashcheck.py",
  "linecap.py"} <= walkers` in `scripts/tests/test_skippeddirs.py`. A search matching nothing fails
  on the floor line, loudly. What the entry is actually about is the opposite reading, a caller the
  search does not recognize and therefore does not hold, and the clause now says that.
- 2026-09-07: what fired it. `scripts/logcalls.py`, `scripts/samplecheck.py` and
  `scripts/assertedlines.py` each walk a tree with `Path.rglob` and filter the result against
  `SKIPPED_DIRS` rather than pruning a `dirnames` list in place, so none of them spells
  `dirnames[:]` and none is in `walkers`. All three arrived after this entry was opened on
  2026-08-24: the first two with the log-sample gate on 2026-08-26, the third with the proven-line
  reader on 2026-09-05. Nothing is wrong in the tree, since each one does read the shared list, but
  the obligation reached none of them and nothing said so, which is exactly the omission the entry
  predicted.
- 2026-09-07: the git half has not fired. `scripts/*.py` spells the `["git", ` argv head in exactly
  the three files the floor names, and the only other `subprocess.run` under `scripts/` is
  `imagedrift.py`, which runs `docker pull` and `docker image inspect`. Left open and actionable
  rather than landed, because widening the walk recognizer changes a gate and needs a mutation
  table, which did not fit the slot that answered this. The `ast` option in **What would close
  it** above no longer covers the observed case on its own, since a filtered glob is a different
  call rather than an argv built one line earlier: the recognizer has to admit a recursive glob as
  a walk, or the shared iterator argument has to win.
