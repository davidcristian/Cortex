# Runbook: replaying the record's mutation tables

A mutation table is this repo's answer to distrusting green: a change states which edits it
reddens and how many cases each one takes down. Every one of them is a self report until somebody
other than its author re-runs it, which is what a replay pass is for. The decision behind the
numbers below is the [ADR-0002](../adr/ADR-0002-toolchain-gates.md) replay-cadence addendum; this
file is how a pass is run and where its result lands.

Nothing schedules this. A replay needs the judgement to rebuild an edit from a sentence, so it is
an agent's or a maintainer's pass rather than a workflow, and the ledger at the bottom is the only
record that one happened.

## Is a pass due

The cadence is counted in tables, not in days, because the record grows in bursts: one overnight
session lands more of them than a quiet fortnight does. **A pass is due once twenty five candidate
bodies have landed since the last pass in the ledger.** Ask the question with the recipe, handing
it the last pass's date:

```
just replay "" 2026-08-21
```

The header line reports how many candidates that range holds. Under twenty five, there is nothing
to do. At or over it, that same command has already drawn the sample, and it drew it out of the
whole range rather than the standing window: on a pass that is on time the two sets are the same,
and on a late one the wider set is the honest one to sample.

## Drawing the sample

```
just replay          # five bodies out of the twenty five most recent, at a fresh printed seed
just replay 4021     # the same five that seed drew before, on any machine
```

**Five is the sample and the draw is blind.** The one pass this practice has had chose its five by
hand, and hand-choosing is the weak half of sampling here: an agent picks what it already
understands, while the tables most worth replaying are the ones whose wording nobody can
reconstruct. The recipe keys each candidate on a digest of the seed and the commit and takes the
five smallest, so the sample is a function of the seed alone and reproduces off this machine.

## Replaying one row

For each drawn commit, read its body and its diff (`git show <sha>`). **The table is often not in
the message.** A body is drawn for carrying the vocabulary, and on this repo's larger changes the
table itself lives in the ADR addendum that same commit lands, so the diff is where to look for it;
one of the five bodies drawn on 2026-08-25 said only "reddens" in passing and carried a five row
table in the addendum it added. Then, per row:

1. **Find the line the mutation perturbs.** A mutation is always a perturbation of a line the
   change itself touched, so the file and the edit come off the commit's own diff even when the
   sentence names neither. The suite is the one fact the diff does not carry, which is why
   AGENTS.md requires a table to name it.
2. **Cut a scratch worktree at the drawn commit**, `git worktree add --detach <path> <sha>`, and
   not at master. The collection a table names is a historical fact, and a worktree at the commit
   reproduces it: the three tables replayed on 2026-08-25 baselined at exactly the 852, 119 and
   2,878 cases they claim.
3. **Ask whether the line still exists at master.** If it does not, the row is expired. Replaying
   it at its own commit still validates the record, and it says nothing about the suite that runs
   today, so spend the budget on the rows that say both.
4. **Plant the mutation**, confirm it is really on disk, run the suite the table names, then revert
   with `git checkout` or a copy taken before the first plant and compare byte for byte before
   planting the next one. Clear `__pycache__` between plants, for the reason the next section
   gives.
5. **Compare the count** with what the row claims.

## When a row does not reproduce

The first answer is to distrust the replay rather than the record, because a replay harness has
its own failure modes and one of them has already been observed here: a mutation planted in
`scripts/` and reverted within the same second leaves a stale `scripts/__pycache__` behind, since
source mtime has one-second granularity and the reverted file is the same size, so the interpreter
goes on running the mutation off bytecode. Three runs of one sweep reported a count from a
mutation that was no longer on disk. **Re-run a non-reproducing row from a clean state, clearing
`__pycache__` and confirming the plant is really on disk, before it counts as non-reproducing at
all.** The other harness failure, measured on the pass of 2026-08-25, is an incomplete
reconstruction: a row reading "a git that cannot answer treated as nothing ignored" claimed two
cases, the plant mutated the one refusal the sentence seems to name, and the suite reported one.
The record was right and the plant was half of it, the module having two refusal sites. **A count
that comes back lower than claimed is a partial plant until proven otherwise**, and the expected
column, "both refusals fail", is what says so. Only then does it fall into one of three kinds, which want three different answers.

**A wrong count.** The line is there, the edit applies, the suite runs, and the number differs.
Correct the record where the claim lives, which is the ADR addendum carrying the table, with a
dated note saying what was observed and when. Two of these are worse than a bookkeeping error and
are handled as defects rather than corrections:

- **A count of zero**, meaning the mutant survives the suite. The row claimed the suite would have
  caught something and it does not, so the answer is an assertion, not an edit to the number. This
  is not hypothetical: a boundary arm landed here in August because a sweep's second row came back
  zero and showed that the strictness a rule insists on was enforced by nothing.
- **A count of zero that is unreachable by construction**, meaning the mutated line lives behind a
  `pragma: no cover` adapter that only a live run touches. That row is out of a replay pass's
  reach, and it is out of it honestly; the table should say the row was killed live, and the pass
  records it as live-only rather than as a hole. One table in this record has exactly that shape,
  seven mutants killed by the suite and an eighth killed by the live run.

**A wording nobody can replay.** The body plus the diff do not identify the edit, and rebuilding
it would mean inventing one. **Stop rather than invent.** An invented edit that produces a
different number manufactures a false correction to a record that may be perfectly true, which is
strictly worse than an unreplayed row. Give reconstruction the budget the cheap tables cost, about
five minutes, then record the row as unreplayable and name the wording that defeated you. That is
a defect in the message, and the rule it feeds is the AGENTS.md one about naming the suite.

**A tree that moved under the claim.** The file, the line or the suite the row names no longer
exists. Record it as expired and correct nothing: the claim was true of a tree that is gone, and
rewriting it to match today's tree would be a fabrication about what was measured. Expired rows
are the reason the draw takes the twenty five most recent bodies rather than the whole record.

## Where a pass's result goes

Two places, and both are required for the next pass to work.

- **The ledger below** gets a row: the date, the seed, the window, how many rows were replayed and
  what came of them. It is what the next pass counts from, so a pass that finds nothing still
  writes one.
- **Anything a row turned up** goes where that row's claim lives: a correction as a dated note at
  the ADR addendum carrying the table, a zero count as a new assertion plus its own task file, an
  unreplayable wording as a task file.

## Ledger of passes

| Date | Seed | Window | Rows | Result |
| --- | --- | --- | --- | --- |
| 2026-08-21 | none, chosen by hand | one week of the record, five tables | 32 rows over 49 runs | every row reproduced; cost four minutes per table where the file, the edit and the suite were named and fifteen where none of the three was |
| 2026-08-25 | 19269061 | the 25 most recent bodies, five drawn | 10 rows over 16 runs, out of the 16 those tables state | every replayed row reproduced, one of them only after the plant was corrected; three of the five drawn bodies were opened and the pass was bounded by the session rather than by the record |
