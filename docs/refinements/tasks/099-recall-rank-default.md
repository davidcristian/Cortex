# The recall rank's default

**Status:** done 2026-08-08
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The judge's cost was the only reason `CORTEX_MEMORY_RECALL` defaulted to `raw`, and on
2026-08-06 it fell twenty-fold ([ADR-0038](../../adr/ADR-0038-ranked-recall.md)). The rank's
request now uses `rank_bounds(k)` (`max_tokens=24 + 8k`, `thinking=False`), the same bounding the
history fold proved out that day, so a rank whose deliberation `drain_text` throws away unread
stopped paying for it: 448 to 613 decoded tokens at 18.4 s per recall became 12 to 22 at 0.9 s,
of which about 0.2 s is evaluating the pool prompt that no bound touches. Scored again over the
same ten notes and six questions, the bounded judge returned the identical note for every
question: mean reciprocal rank 1.000 against the cosine's 0.917, the right note first 6 of 6
against 5 of 6, no fallbacks.

Until then it waited on the user's call about `CORTEX_MEMORY_RECALL=judge` as a default, or on a
wider corpus settling the second objection below on its own. Either way the audit trail
(`CORTEX_MEMORY_RECALL_AUDIT=1`) reports the basis that ranked each recall, so a deployment that
turns it on can tell a judged rank from a fallback afterwards.

Two objections remained. A rank runs on every turn that recalls, unlike the history fold that a
cache pays for once per boundary move, so this is 0.9 s on the front of every such turn. And the
corpus was hand built by the policy's author.

**The corpus objection was answered the same day**: 41 notes and 26 questions over six
categories, five of which the judge could have lost, scored through the shipped pool width (the
cosine's top 12 of 41, `pool_factor` 4 at `k` 3, gold in pool for all 22 answerable). The judge
is worse nowhere. It ties the cosine at MRR 1.000 on the three categories where the geometry is
already right, and beats it on two: the vocabulary trap it was built for (1.000 against 0.806)
and, unplanned, superseded versions, where the cosine cannot tell a dead fact from its
replacement and put the stale one first twice in four (1.000 against 0.750). Aggregate 1.000
against 0.902 over the 22 answerable, 0.75 s per recall, 12 to 20 decoded tokens. A
reversed-cosine control scored 0.000 in every category, so the scorer was watched failing rather
than only trusted.

**Flipped 2026-08-08, after the end-to-end measurement the user asked for first**
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) decision 7). Real turns over gRPC on the 24 GB
card, one fresh pre-seeded session each so no turn's own recorded exchange reached the next one's
pool, six questions across the six categories, eight repetitions, 48 turns per condition, in
A/B/A order with a raw block either side of the judged one.

- Time to first token rises 0.515 s (95% CI 0.116 to 0.915, blocked by question and
  bootstrapped); the whole turn 0.526 s. The null comparison, raw against raw, is -0.158 s with
  an interval spanning zero.
- The turn pays less than the rank costs. Timed alone at the shape assembly actually asks for
  (`k` 5 at `pool_factor` 4, a pool of 20 rather than the published run's 12) a rank is 0.877 s,
  above the 0.75 s on record. The difference is given back because the judge hands the reply 1.17
  notes where the cosine hands it 5, so the memory block the model reads before it can speak is
  smaller. That saving is proportional to how much the cosine over-returns.
- The rank runs before generation, which the trail's own timestamps confirm: everything up to and
  including the pgvector search is 0.363 s judged against 0.396 s raw, and the whole difference
  sits after it.
- It is paid every turn. `JudgeRecallPolicy` holds no cache, `MemoryRecaller.recall` calls
  `select` on every recall, and the run logged exactly 48 recall lines for 48 turns per condition.
- The ranking held at the wider pool: MRR 1.000 against the cosine's 0.767 over 40 answerable
  turns, nothing returned on all 8 unanswerable ones against 0 of 8, and 0 fallbacks in 48
  recalls.

`CORTEX_MEMORY_RECALL=raw` is the opt-out now. The corpus is still hand built by an interested
party; what the flip changes is that a real conversation is now what the rank meets.

## History

- 2026-08-06: The cost that was the only reason the default was `raw` fell twenty-fold when the
  rank's request took the bounding the history fold proved out the same day, from 18.4 s per
  recall to 0.9 s. The ranking did not change, so the default became a decision for the user
  rather than a measurement, and nothing was blocked behind it, the setting being one env
  variable either way.
- 2026-08-06: The bound is computed from `k` rather than fixed, since a schema-constrained
  order's length is known before it is asked for. The bounding run turned up two things. A JSON
  schema does not protect a constrained reply from a cap, because a truncated reply is not JSON at
  all and the rank then falls back to the cosine, which is why the cap is generous rather than
  tight. And capping while thinking is left on fails here every time: the reply came back empty
  three times in three at each of 16, 32 and 64 tokens, the answer being a few tokens and the
  deliberation before it hundreds.
- 2026-08-06: The corpus objection was answered the same evening, 41 notes and 26 questions over
  six categories with a reversed-cosine control at 0.000.
- 2026-08-08: Flipped after the end-to-end turn measurement. `CORTEX_MEMORY_RECALL` ships as
  `judge` and `raw` is the opt-out.
- 2026-08-08: The abstention entry ([R-100](100-judge-abstention.md)) closed the day before this
  one, so the flip shipped the refusal it was the trigger for rather than the defect it would
  otherwise have exposed. Nothing opened behind the flip itself.
