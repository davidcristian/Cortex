# The recall rank's default

**Status:** landed 2026-08-08
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The judge's cost, which is the only reason its default is `raw`, fell twenty-fold on 2026-08-06
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) bounded-side-calls addendum). The rank's request now
carries `rank_bounds(k)` (`max_tokens=24 + 8k, thinking=False`), the lever the history fold proved
out the same day, and a rank whose deliberation `drain_text` throws away unread stopped paying for
it: 448 to 613 decoded tokens at 18.4 s per recall became 12 to 22 at **0.9 s**, of which about
0.2 s is evaluating the pool prompt that no bound touches. **The ranking did not change.** Scored
again over the same ten notes and six questions, the bounded judge returned the identical note
for every question, mean reciprocal rank 1.000 against the cosine's 0.917, the right note first 6
of 6 against 5 of 6, no fallbacks, and it still returns *fewer* hits than `k` because it drops
the notes that do not help. So the premise the default rested on is gone, and two things a
default still has to answer for are not: a rank runs on **every** turn that recalls, unlike the
history fold that a cache pays for once per boundary move, so this is 0.9 s on the front of every
such turn rather than an amortized cost; and the corpus is still hand built by the policy's
author, ten notes and six questions, which shows the mechanism works and is not a benchmark.
**Trigger:** the user's call on `CORTEX_MEMORY_RECALL=judge` as a default, or a wider corpus that
settles the second point on its own. Whichever way it goes, the audit trail
(`CORTEX_MEMORY_RECALL_AUDIT=1`) reports the basis that actually ranked each recall, so a
deployment that turns it on can tell a judged rank from a fallback after the fact.
**The corpus half of that trigger was answered the same day** ([ADR-0038](../../adr/ADR-0038-ranked-recall.md)
widened-corpus section): 41 notes and 26 questions over six categories, five of which the judge
could have lost, scored through the shipped pool width (the cosine's top 12 of 41, `pool_factor`
4 at `k` 3, gold in pool for all 22 answerable). The judge is **not worse anywhere**. It ties the
cosine at MRR 1.000 on the three categories where the geometry is already right (an answer worded
in the question's own words, two near-duplicate notes, an answer buried in a clause), and beats it
on two: the vocabulary trap it was bought for (1.000 against 0.806) and, unplanned, superseded
versions, where the cosine cannot tell a dead fact from its replacement and put the stale one
first twice in four (1.000 against 0.750). Aggregate 1.000 against 0.902 over the 22 answerable,
0.75 s per recall, 12 to 20 decoded tokens. A **reversed-cosine control arm scored 0.000 in every
category**, so the scorer has been watched failing rather than merely trusted. **The default is
still the user's call and is still not flipped**; what changed is that the recommendation no
longer rests on a corpus cut to produce it.
**Called and flipped 2026-08-08, after the measurement the user asked for first**
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) turn-cost addendum). The one thing every earlier run
had priced was a rank, and this entry's own remaining objection was that a rank is not a turn, so
the turn was measured before the flag moved. Real turns through the seam on the 24 GB card, one
fresh pre-seeded session each so no turn's own recorded exchange reached the next one's pool, six
questions across the six categories, eight repetitions, 48 turns an arm, in **A/B/A order** with a
raw block either side of the judged one. **Time to first token rises 0.515 s** (95% CI 0.116 to
0.915, blocked by question and bootstrapped), the whole turn 0.526 s, while the **null arm, raw
against raw, is -0.158 s with an interval spanning zero**: the harness separates the arms it
should and not the arms it should not. **The turn pays less than the rank costs.** Timed alone at
the shape assembly actually asks for (`k` 5 at `pool_factor` 4, a pool of 20 rather than the
published run's 12) a rank is 0.877 s, above the 0.75 s on record, and the difference is given
back because the judge hands the reply 1.17 notes where the cosine hands it 5, so the memory block
the model reads before it can speak is smaller. That saving is proportional to how much the cosine
over-returns and a deployment whose questions are mostly answerable will see less of it. **The
rank runs before generation and lands on the first token**, which the trail's own timestamps
confirm from the other side: everything up to and including the pgvector search is 0.363 s judged
against 0.396 s raw, the same number, and the whole difference sits after it. **It is paid every
turn.** `JudgeRecallPolicy` holds no cache, `MemoryRecaller.recall` calls `select` on every
recall, and the run logged exactly 48 recall lines for 48 turns per arm, so the asymmetry with the
fold that this entry kept naming is confirmed rather than softened; only its size changed. The
ranking was re-read at the wider pool off the same trail and did not suffer for it: **MRR 1.000
against the cosine's 0.767 over 40 answerable turns, nothing returned on all 8 unanswerable ones
against 0 of 8, and 0 fallbacks in 48 recalls.** `CORTEX_MEMORY_RECALL=raw` is the opt-out now.
What no run of this repo's own can settle is unchanged: the corpus is hand built by an interested
party, and what the flip changes is that a real conversation is now what the rank meets.

## Trail

- 2026-08-06: The cost that was the only reason the default was `raw` fell twenty-fold when the
  rank's request took the bounding lever the history fold proved out the same day, from 18.4 s per
  recall to 0.9 s by the entry's own numbers, which the index ledger records instead as about 12
  seconds per recall. The ranking did not change, so the default became a decision in front of the
  user rather than a measurement, and the index recorded that nothing was blocked behind that
  decision, the setting being one env variable either way.
- 2026-08-06: The bound is computed from `k` rather than fixed, a schema-constrained order's length
  being known before it is asked for, and the bounding run turned up two things its predecessor had
  not predicted. A JSON schema does not protect a constrained reply from a cap, since a truncated
  reply is not JSON at all and the rank then falls back to the cosine exactly as it does for a model
  it cannot reach, which is why the cap is generous rather than snug. And the trap of capping while
  thinking is left on, which went either way on the history fold, is a certainty here: the reply came back
  empty three times in three at each of 16, 32 and 64 tokens, the answer being a few tokens and the
  deliberation before it hundreds.
- 2026-08-06: The corpus half of the trigger was answered the same evening, 41 notes and 26
  questions over six categories with a reversed-cosine control arm at 0.000 to prove the scorer
  could fail. The judge is worse nowhere, ties at 1.000 wherever the geometry was already right, and
  beats the cosine on the vocabulary trap (1.000 against 0.806) and on superseded facts (1.000
  against 0.750).
- 2026-08-08: Called and flipped, after the end-to-end turn measurement the user asked for first.
  Time to first token rises 0.515 s (95% CI 0.116 to 0.915) over 48 real turns an arm through the
  seam in A/B/A order, while the null arm of raw against raw is -0.158 s with an interval spanning
  zero. `CORTEX_MEMORY_RECALL` ships as `judge` and `raw` is the opt-out.
- 2026-08-08: The abstention entry closed the day before this one, so the flip shipped the refusal
  it was the trigger for rather than the defect it would otherwise have exposed. Nothing opened
  behind the flip itself.
