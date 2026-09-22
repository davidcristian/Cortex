# The mutation replay happened once, with no schedule and no sampling rule

**Status:** done 2026-08-25
**Area:** cross-cutting
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

[R-349](349-a-mutation-table-nobody-replayed.md) replayed five mutation tables out of one week of
commits and found all thirty two of their rows exact. That answered the question it asked, and it
did not create what the entry wanted, which is a second reader who comes back.

The one pass settled affordability: five tables, thirty two rows, forty nine test runs, about forty
minutes of replay on top of about fifteen of setup. Most of the forty was pytest rather than
judgement. The two cheap tables took four minutes each because they name the file, the edit and the
suite, and the expensive one took fifteen because five of its rows each needed a two minute run of
the whole brain suite. So a pass over a week of commits is under an hour.

What is not decided is how often a pass runs, what it draws from, and where its result goes. A
sample drawn by whoever happens to be replaying is a sample drawn from what that agent already
understands, and the tables most worth replaying are the ones whose wording nobody can reconstruct.
Closing it needs a cadence, a sample size, and a rule for what a pass does when a row does not
reproduce. The last has teeth and was never exercised, because nothing failed: a row that does not
reproduce is either a wrong count, a wording nobody can replay, or a tree that moved under the
claim, and those want different answers.

## History

- 2026-08-21: Opened by the close of [R-349](349-a-mutation-table-nobody-replayed.md), which
  replayed five tables and settled affordability without deciding when a second pass runs.
- 2026-08-25: Done, as [ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 20, a `replay`
  recipe in the `justfile`, and
  [docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md), which holds the procedure
  and the record a pass writes its result into. The three numbers: a pass is due once twenty five
  candidate bodies have arrived since the last recorded pass, it replays five of them, and the
  choice is a digest of a printed seed rather than anybody's judgement. One claim here did not
  survive: the census this entry proposed drawing from does not exist, the close that reported its
  numbers having declined the script that produced them, so it was thirty uncommitted lines.
  Re-taken over 624 commits, 138 bodies use the vocabulary and 115 of them name no tracked path,
  which matches the close's proportion. The cadence's unit had to be tables rather than days:
  candidates arrive in bursts, 1, 29, 1, 3, 24, 19 and 46 over consecutive weeks, and thirty nine
  had arrived in the four days since the pass that opened this. The rule for a non-reproducing row
  is written off this week's evidence, its first clause being to distrust the replay, since a stale
  `__pycache__` produced phantom failures in three runs of one review here. Opened by this close:
  [R-439](439-nothing-counts-the-record-between-passes.md) and
  [R-440](440-the-replay-sample-and-its-window-are-written-in-four-places.md).
- 2026-08-25: The procedure was run under its own rules later the same day, seed 19269061 over the
  twenty five most recent bodies, ten rows over sixteen runs, every replayed row reproducing. One
  row took two attempts and the second attempt was the planted edit's fault rather than the
  record's, which is the rule's first clause paying for itself immediately.
