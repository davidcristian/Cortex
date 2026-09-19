# Readings: the mutation replay

What the record of mutation tables looks like to a replay pass, and what a pass costs. Cited by
[ADR-0002](../adr/ADR-0002-toolchain-checks.md#mutation-tables-and-the-replay-pass), decision 20
and the rejected `commitlint.py` rule. The result of each pass is the ledger in
[docs/runbooks/mutation-replay.md](../runbooks/mutation-replay.md).

## Most matching commit bodies mention no tracked path

**2026-09-19.** Of 954 commits, 17 messages match the `replay` recipe's four patterns. Of the 17,
16 name no path or file name this repository tracks, and none names both a path and a suite.

Method: `git log -i -E --grep=redden --grep=mutant --grep=mutation --grep='prove[a-z]* able to
fail'`, with each matching message checked against `git ls-files` by a scratch detector that is
not committed.

## Candidate bodies appear unevenly

**2026-09-07 to 2026-09-19.** Candidate bodies written since the pass of 2026-08-25: 3 by
2026-09-07, 4 by 2026-09-10, 6 by 2026-09-12 and 9 by 2026-09-19, so 4 in the first thirteen days
and 5 in the next seven.

Method: `just replay`, whose first line gives the count since the last pass in the ledger; the
first three were read with `just replay "" 2026-08-25` before the recipe read the ledger itself.

## No candidate body holds a table of its own

**2026-09-19.** None of the 17 matching bodies contains a fenced table. The vocabulary is used to
say that a change was proved by mutation, and the table itself is written where the practice of
the day put it, which is why a detector keyed on the wording would draw bodies that have nothing
to replay. The tables for the repository's own checks are in
[check-mutations.md](check-mutations.md).

Method: `git show <sha>` on each matching body, reading the message and the diff.

## What a pass costs

**2026-08-21.** Five tables, 32 rows over 49 runs, took about 55 minutes including setup. A table
that named its file, its edit and its suite took 4 to 6 minutes to replay; one naming none of the
three took 10 to 15, the file and the edit being recovered from the diff. One row claiming 27
failures reproduced only over the whole brain suite, 2,786 cases, so a replay over one package
would have reported a different number.

Method: the procedure in [docs/runbooks/mutation-replay.md](../runbooks/mutation-replay.md),
timed per table.
