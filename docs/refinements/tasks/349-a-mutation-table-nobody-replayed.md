# No mutation table has been replayed by anyone but its author

**Status:** done 2026-08-21
**Area:** cross-cutting
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

Most commit bodies here end in a mutation table: this edit makes five cases fail, that one makes 27
fail. The tables are this repo's answer to distrusting a suite that passes. Not one had been re-run
by anybody other than the agent that wrote it.

A mutation count is a claim that the suite would have caught this, and the evidence is a run nobody
else observed, on a working tree nobody else has. The tree that survives is the unmutated one, so
the claim cannot be checked after the fact without redoing the work: reconstructing the mutation
from the sentence describing it, applying it, and running the suite. Where the sentence is precise
that is minutes; where it says "reverting the way out makes six fail" it is a reading exercise
first.

The measurements have the same shape. The Docker-dependent figures in the same group of changes,
the log driver's 16 KiB limit and the character counts on the recall trail, were produced by one
agent against containers that no longer exist.

Nothing here argues for less of the practice. The gap is that it has no second reader, so it has
the weakness of every self report. What would close it is a mutation table written so it can be
replayed without judgement, naming the file, the exact edit and the expected count, plus a pass
that replays a sample of them. The decision to take is whether replayability is a requirement of
the table's wording or a practice of whoever reviews, because the first can be enforced and the
second cannot.

## History

- 2026-08-20: Opened by a review of fourteen commits, which found every mutation count and every
  container measurement in them resting on a single unrepeated observation by the agent that
  authored the change.
- 2026-08-21: Replayed, then decided. Five tables were replayed out of the commit history, thirty
  two stated rows over forty nine runs, each mutation applied in a scratch worktree and reverted
  with a byte for byte comparison against the pre-mutation file. Every row reproduced. The deadline
  clamp table (three constants over seven cases, claiming 4, 4, 4) gave 4, 4, 4. The credential
  withholding table (five rows claiming one, the same one, six, one, six) gave 1, 1, 6, 1, 6, each
  named case being the one named. The named turn table (5, 5, 3, 27, 1) gave 5, 5, 3, 27, 1 over
  the whole brain suite at 2,786 cases. The heading table (fourteen mutations against both the
  suite it replaced and the suite it added) gave 41 passed on all fourteen before and, after,
  twelve making one case fail and the two on the shared remedy making six fail. The compose default
  survey's twenty six planted differences and its suite guard were sampled five ways, and all five
  behaved exactly as written. What varied was cost rather than correctness: four minutes where the
  table names the file, the edit and the suite, fifteen where it names none of the three. The file
  and the edit came off the commit's own diff in every case, because a mutation is always a change
  to a line the commit itself touched; the suite is the one fact the diff does not give, so that is
  what AGENTS.md now requires a table to name, as a rule no machine checks. The enforceable form
  was refused on a measurement: over 561 commits, 100 bodies use the vocabulary and 88 name no
  tracked path, only 54 use `reddens` at all, and one of the 100 is a change whose body correctly
  says it has no table. The script over the messages was refused with it, the census being thirty
  lines against forty minutes of replay. Both doubted measurements were re-taken: the log driver's
  limit holds exactly on Docker 29.1.3 with `json-file`, and the recall trail's 1,458 to 1,475 came
  back 1,458 to 1,476 on a fresh 200 draws. This entry was wrong about the second one's cost: it
  needs no container, being a computation over drawn ids and scores, which is why it took two
  minutes. Opened by this close: [R-357](357-a-replay-pass-has-no-cadence.md),
  [R-358](358-the-widest-value-was-never-a-real-line.md) and
  [R-359](359-the-table-detector-is-refused-not-impossible.md).
