# The record was replayed once, by a pass nothing schedules and nothing samples

**Status:** landed 2026-08-25
**Area:** cross-cutting
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-21 by the close of [R-349](349-a-mutation-table-nobody-replayed.md), which replayed
five mutation tables out of one week of the record and found all thirty two of their rows exact.
That answered the question the entry asked. It did not create the thing the entry actually wanted,
which is a second reader who comes back.

**What the one pass proved about affordability.** Five tables, thirty two rows, forty nine test
runs, about forty minutes of replay on top of about fifteen of setup. Most of that forty was pytest
rather than judgement: the two cheap tables took four minutes each because they name the file, the
edit and the suite, and the expensive one took fifteen because five of its rows each needed a two
minute run of the whole brain suite. So a pass over a week of commits is under an hour, and a pass
that samples rather than exhausts is a fraction of that. Affordability is settled; nothing else is.

**What is not decided.** How often a pass runs, what it draws from, and where its result goes. A
sample drawn by whoever happens to be replaying is a sample drawn from what that agent already
understands, which is the weaker half of the sampling problem: the tables most worth replaying are
the ones whose wording nobody can reconstruct, and those are exactly the ones an agent picking by
hand skips. The census that supported the close is the raw material for a fair draw, since it
already sorts every body in the record by which vocabulary it uses and whether it names a path.

**What would close it.** A decision with a number in it: a cadence, a sample size, and a rule for
what a pass does when a row does not reproduce. The last of the three is the one with teeth and the
one this pass never had to exercise, because nothing failed. A row that does not reproduce is
either a wrong count, a wording nobody can replay, or a tree that moved under the claim, and those
three want different answers: the first corrects the record, the second is a wording defect the
close's own AGENTS.md clause now names, and the third is not a defect at all.

## Trail

- 2026-08-21: opened by the close of [R-349](349-a-mutation-table-nobody-replayed.md), which
  replayed five tables and settled affordability without deciding when a second pass runs.
- 2026-08-25: **landed**, as the [ADR-0002 replay-cadence
  addendum](../../adr/ADR-0002-toolchain-gates.md), a `replay` recipe in the `justfile`, and
  [docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md), which carries the
  procedure and the ledger a pass writes its result into. The three numbers: a pass is due once
  twenty five candidate bodies have landed since the last ledgered pass, it replays five of them,
  and the draw is a digest of a printed seed rather than anybody's choice. **One claim here did not
  survive re-derivation.** The census this entry proposed drawing from does not exist: the close
  that reported its numbers declined the script that produced them in the same addendum, so it was
  thirty uncommitted lines. Re-taken over 624 commits, 138 bodies carry the vocabulary and 115 of
  them name no tracked path, which holds the close's proportion. What the entry could not have
  known is that the cadence's unit had to be tables rather than days: candidates arrive in bursts,
  1, 29, 1, 3, 24, 19 and 46 over consecutive weeks, and thirty nine had landed in the four days
  since the pass that opened this. The rule for a non-reproducing row is written off this week's
  evidence rather than from first principles, its first clause being to distrust the replay, since
  a stale `__pycache__` produced phantom failures in three runs of one sweep here. Opened by this
  close: [R-439](439-nothing-counts-the-record-between-passes.md) and
  [R-440](440-the-replay-sample-is-spelled-in-three-places.md).
- 2026-08-25, later the same day: **the procedure was run under its own rules**, seed 19269061 over
  the twenty five most recent bodies, ten rows over sixteen runs, every replayed row reproducing.
  One row took two attempts and the second attempt was the plant's fault rather than the record's,
  which is the rule's first clause paying for itself immediately; the runbook and the ADR addendum
  carry what it taught, and the ledger carries the pass.

