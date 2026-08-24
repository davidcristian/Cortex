# The two obligation tests recognize a caller by how it is spelled

**Status:** open, fix when it bites
**Trigger:** a walk or a git call written some other way, which is the first time one of these
tests reports an empty list of offenders because it found no callers at all.
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
far as either test can tell, and the obligation quietly does not apply to it.

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
