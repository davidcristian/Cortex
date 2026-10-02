# Readings: the mutation replay

What the record of mutation tables looks like to a replay pass, and what a pass costs. Cited by
[ADR-0002](../adr/ADR-0002-toolchain-checks.md#mutation-tables-and-the-replay-pass), decision 20
and the rejected `commitlint.py` rule. The result of each pass is the ledger in
[docs/runbooks/mutation-replay.md](../runbooks/mutation-replay.md).

## Matching commit bodies hold a table and name a test file

**2026-10-02.** Of 1,175 commits, 94 messages match the `replay` recipe's four patterns. Each of
the 77 committed since 2026-09-20 holds a fenced table, and none of the 17 before them does: those
name the practice, and the tables of that period for the repository's own checks are in
[check-mutations.md](check-mutations.md). Of the 50 most recent, committed from 2026-09-24, all 50
contain the word suite, a test command or a test file name. As for a tracked path, 21 write one as
`git ls-files` lists it, 5 write one relative to a package root, such as
`packages/inference/tests/test_joined_rows.py`, 22 name a tracked file by its name alone, and 2
name no file, giving their suite as `cargo test -p os-linux --test x11`.

Method: `git log -i -E --grep=redden --grep=mutant --grep=mutation --grep='prove[a-z]* able to
fail'`, with each matching message checked for a fence and against `git ls-files` by a scratch
detector that is not committed.

## Candidate bodies appear unevenly

**2026-09-07 to 2026-09-19.** Candidate bodies written since the pass of 2026-08-25: 3 by
2026-09-07, 4 by 2026-09-10, 6 by 2026-09-12 and 9 by 2026-09-19, so 4 in the first thirteen days
and 5 in the next seven.

Method: `just replay`, whose first line gives the count since the last pass in the ledger; the
first three were read with `just replay "" 2026-08-25` before the recipe read the ledger itself.

## What a pass costs

**2026-08-21.** Five tables, 32 rows over 49 runs, took about 55 minutes including setup. A table
that named its file, its edit and its suite took 4 to 6 minutes to replay; one naming none of the
three took 10 to 15, the file and the edit being recovered from the diff. One row claiming 27
failures reproduced only over the whole brain suite, 2,786 cases, so a replay over one package
would have reported a different number.

**2026-10-02.** Five tables, 18 rows, each replayed twice: at its own commit, from a `git archive`
export run with `PYTHONPATH` set to the export's `packages/*/src`, and at the drawn-from commit.
That is 36 runs, 34 of them plants and two the roles table's own unmutated row, plus 7 baseline
runs. Every table named its suite and every row's line came off its commit's diff, so no row needed
the five-minute reconstruction budget and no plant needed a second attempt. One plant was rebuilt
for the drawn-from commit, where its line had been rewritten. The pass's wall time is not
published, because it ran on cores 0 to 11 beside a GPU run that held the card.

Method: the procedure in [docs/runbooks/mutation-replay.md](../runbooks/mutation-replay.md),
timed per table on 2026-08-21 and counted per run on 2026-10-02.
