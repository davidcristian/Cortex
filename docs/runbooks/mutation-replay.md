# Runbook: replaying the mutation tables in the commit history

A mutation table is how a change here proves its check can fail: it names the edits that make the
suite fail and how many cases each edit takes down. Every one is a self report until somebody
other than its author re-runs it, which is what a replay pass is for. The decision behind the
numbers below is
[ADR-0002](../adr/ADR-0002-toolchain-checks.md#mutation-tables-and-the-replay-pass); this file is
how a pass is run and where its result goes.

Nothing schedules this. A replay needs the judgement to rebuild an edit from a sentence, so it is
an agent's or a maintainer's job rather than a workflow, and the ledger at the bottom is the only
record that one happened.

## Is a pass due

The cadence is counted in candidate commit messages rather than in days, because the history grows
in bursts: one overnight session produces more of them than a quiet fortnight does. **A pass is
due once twenty five candidate messages have been committed since the last pass in the ledger.** A
candidate message is one containing the replay vocabulary, and not every one has a table: some
name the practice rather than measuring anything. Telling the two apart takes reading the message
and its diff, which the recipe cannot do, so the count stays in messages and a pass comes due
after fewer tables than that. The recipe answers the question on its own, with no date typed in:

```
just replay
```

Its first line counts the candidate messages committed since the last pass and states that count
against the cadence. Under twenty five there is nothing to do. At or over it, the same run has
already drawn a sample out of the current window.

**The count runs from the commit in the ledger's "Drawn from" column**, as the range
`<commit>..HEAD`, so it covers exactly the work committed after the pass took its sample. The
recipe reads every commit the column holds and anchors on the one nearest HEAD, which is the last
pass whatever order the rows were typed in and whatever their date cells say. The line names the
row it read and the commit it counted from.

When no row's "Drawn from" cell holds a commit this clone resolves, the count runs from midnight
of the last dated row instead. That reading is coarser in two ways: it counts from the start of
the pass's own day rather than from the sample, and it takes the last row that has an ISO date
rather than the last pass. The line says which of the two readings it gave. While any row's commit
resolves, a row without one takes no part in the count, so a pass that writes its row with no
commit is passed over and the count runs from the pass before it, which the line then names.

A rewrite of this repo's history is what makes a recorded commit stop resolving. One that moves
every recorded commit leaves the coarse reading; one that moves only the newest, as a rewrite of
work not yet pushed can, leaves the pass before it as the anchor. Either lasts until somebody
recomputes the moved commit, and the next pass records one that resolves.

Once the count is well past the cadence, the current window and the gap since the last pass are no
longer the same set, and the gap is the one to sample, being what went unsampled. Hand the recipe
the ledger's date to count and draw over that range instead:

```
just replay "" 2026-08-25
```

A ledger with neither a commit nor a dated row leaves the count unavailable, which that first line
says in place of a number, and the draw still runs. A missing ledger file fails the recipe
outright: this document is the procedure a pass is run from, so its absence is a fault rather than
one number going unreported.

## Drawing the sample

```
just replay          # five messages out of the twenty five most recent, at a fresh printed seed
just replay 4021     # the five that seed draws at this commit, on any machine
```

**Five is the sample and the draw is blind.** The first pass this practice had chose its five by
hand, and hand-choosing is the weak half of sampling here: an agent picks what it already
understands, while the tables most worth replaying are the ones whose wording nobody can
reconstruct. The recipe keys each candidate on a digest of the seed and the commit and takes the
five smallest, so the sample is a function of the seed and of the commits in the window, and it
reproduces on another machine at the same tip. The recipe prints that tip beside the seed.

**A drawn message with no table of its own is replaced by the next message in the same seed's
order.** `just replay <seed> "" <n>` prints the first `n` messages of that order at the same
commit, the first five unchanged, and `just replay <seed> <date> <n>` does the same for a late
pass. Walk it until five messages have a table or the window runs out, and record each message
passed over and why. A message has no table when its own commit measured none, in the message or
in the diff it commits: a backlog review that talks about the practice, a live reading published
without one, or a message that restates or points at a table another commit measured. A pointer is
passed over rather than counted as the table it names, because that table's own commit can be in
the window too, which would give it two chances, or outside the window altogether; the named table
may still be replayed beside the sample and recorded as outside it. A table whose wording defeats
reconstruction is not tableless. It stays in the sample and is recorded as unreplayable under the
rule below, because passing over the hard tables is the hand choice the blind draw exists to
prevent. That is also why the replacement keeps the draw blind: whether a message has a table is
settled by reading it and not by the seed, so skipping those messages in a seeded order leaves the
first five of the rest a uniform draw over the window's tables.

**A recorded seed reproduces its draw only while the commits under it stay where they were.** The
window moves as tables are committed, so `just replay <seed>` at a later HEAD draws over a
different pool, and reproducing a ledger row's draw means running the recipe on a checkout of its
"Drawn from" commit. A rewrite of the history under that commit changes every hash in the pool,
and after one no checkout reproduces the draw. The ledger records the seed and the tip rather
than the five, because nothing in this practice re-runs a recorded pass's exact sample: a pass
draws fresh.

## Replaying one row

For each drawn commit, read its message and its diff (`git show <sha>`). **The table is in the
message.** A mutation table is written in the message of the commit that makes it, in a code
fence, naming the suite its counts are over, which is why this pass draws messages. A message that
describes its mutations without a table still has its diff read before it is called tableless: a
table written into a document the commit changed is still that commit's table, and the ledger row
notes that it was not in the message. Then, per row:

1. **Find the line the mutation perturbs.** A mutation is nearly always a perturbation of a line
   the change itself touched, so the file and the edit come off the commit's own diff even when
   the sentence names neither. The exception is a change that proves a rule it relies on without
   editing it: two rows of a table replayed on 2026-09-19 perturbed `scripts/backlogindex.py`,
   which that commit left alone, and the table named the file. The suite is the one fact the diff
   does not give, which is why AGENTS.md requires a table to name it.
2. **Cut a scratch worktree at the drawn commit**, `git worktree add --detach <path> <sha>`, and
   not at master. The collection a table names is a historical fact, and a worktree at the commit
   reproduces it: the three tables replayed on 2026-08-25 baselined at exactly the 852, 119 and
   2,878 cases they claim. A brain row run with the main checkout's `brain/.venv` interpreter
   needs `PYTHONPATH` set to the worktree's `brain/packages/*/src`. That venv installs every
   package as an editable path into the main checkout, so without it a mutant planted under a
   worktree's `packages/*/src` is never imported and the suite reports a zero; a plant in a test
   module is imported off the worktree either way.
3. **Ask whether the line still exists at master.** If it does not, the row is expired. Replaying
   it at its own commit still checks the history, and it says nothing about the suite that runs
   today, so spend the budget on the rows that say both.
4. **Plant the mutation**, confirm it is really on disk, run the suite the table names, then
   revert with `git checkout` or a copy taken before the first plant and compare byte for byte
   before planting the next one. Clear `__pycache__` between plants, for the reason the next
   section gives.
5. **Compare the count** with what the row claims.

## When a row does not reproduce

The first answer is to distrust the replay rather than the history, because a replay harness has
its own failure modes and one of them has already been observed here: a mutation planted in
`scripts/` and reverted within the same second leaves a stale `scripts/__pycache__` behind, since
source mtime has one-second granularity and the reverted file is the same size, so the interpreter
goes on running the mutation off bytecode. Three runs of one pass reported a count from a mutation
that was no longer on disk. **Re-run a non-reproducing row from a clean state, clearing
`__pycache__` and confirming the plant is really on disk, before it counts as non-reproducing at
all.** The other harness failure, measured on the pass of 2026-08-25, is an incomplete
reconstruction: a row reading "a git that cannot answer treated as nothing ignored" claimed two
cases, the plant mutated the one refusal the sentence seems to name, and the suite reported one.
The record was right and the plant was half of it, the module having two refusal sites. **A count
that comes back lower than claimed is a partial plant until proven otherwise**, and the expected
column, "both refusals fail", is what says so. Only then does it fall into one of three kinds,
which take three different answers.

**A wrong count.** The line is there, the edit applies, the suite runs, and the number differs. A
commit message is not edited after it is made, so the correction goes in the pass's ledger row:
the commit, the row, the count it claims and the count observed, with the date. Two of these are
worse than a bookkeeping error and are handled as defects rather than corrections.

- **A count of zero**, meaning the mutant survives the suite. The row claimed the suite would have
  caught something and it does not, so the answer is a new assertion rather than an edit to the
  number. That has already happened: a boundary case was added here in August because a pass's
  second row came back zero and showed that the strictness a rule declares was enforced by
  nothing.
- **A count of zero that is unreachable by construction**, meaning the mutated line lives behind a
  `pragma: no cover` adapter that only a live run touches. That row is out of a replay pass's
  reach for a legitimate reason: the table should say the row was killed live, and the pass
  records it as live-only rather than as a hole. One table in this history has exactly that shape,
  seven mutants killed by the suite and an eighth killed by the live run.

**A wording nobody can replay.** The message plus the diff do not identify the edit, and
rebuilding it would mean inventing one. **Stop rather than invent.** An invented edit that
produces a different number manufactures a false correction to a claim that may be perfectly true,
which is strictly worse than an unreplayed row. Give reconstruction the budget the cheap tables
cost, about five minutes, then record the row as unreplayable and name the wording that defeated
you. That is a defect in the message, and the rule it feeds is the AGENTS.md one about naming the
suite.

**A tree that moved under the claim.** The file, the line or the suite the row names no longer
exists. Record it as expired and correct nothing: the claim was true of a tree that is gone, and
rewriting it to match today's tree would be a fabrication about what was measured. Expired rows
are the reason the draw takes the twenty five most recent messages rather than the whole history.

## Where a pass's result goes

Two places, and both are required for the next pass to work.

- **The ledger below** gets a row: the date, the commit the sample was drawn from, the seed, the
  window, how many rows were replayed and what came of them. It is what the next pass counts from,
  so a pass that finds nothing still writes one. Take the commit with `git rev-parse HEAD` before
  the draw, not after the row is written: the count runs from it, and a pass's own record commits
  come after the sample was taken, so they are unsampled work like any other.
- **Anything a row turned up** is recorded where the next reader of that claim will look: a wrong
  count in the ledger row, beside the commit it corrects; a zero count as a new assertion plus its
  own task file; an unreplayable wording as a task file.

## Ledger of passes

| Date | Drawn from | Seed | Window | Rows | Result |
| --- | --- | --- | --- | --- | --- |
| 2026-08-21 | not recorded | none, chosen by hand | one week of the record, five tables | 32 rows over 49 runs | every row reproduced; cost four minutes per table where the file, the edit and the suite were named and fifteen where none of the three was |
| 2026-08-25 | 2712a6aa1fd7c1c274a2f2c03b24fb0bf20872f2 | 19269061 | the 25 most recent bodies, five drawn | 10 rows over 16 runs, out of the 16 those tables state | every replayed row reproduced, one of them only after the plant was corrected; three of the five drawn bodies were opened and the pass was bounded by the session rather than by the record |
| 2026-09-19 | 5809fde53493a54534b9974f85292fa3e56f177c | 26747890 | the 25 most recent bodies, eleven opened in drawn order to reach five that have a table | 23 rows over 23 runs, out of the 23 those tables state, and the same 23 again over the suite at the drawn-from commit | every row reproduced at its own commit and every mutant still fails at the drawn-from commit; six of the eleven messages have no table of their own and were passed over, the two that publish readings instead reproduce at their parents, and the four-row table one of them points at was replayed outside the sample, its live-only zero included |
