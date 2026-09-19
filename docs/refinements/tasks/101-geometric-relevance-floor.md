# A geometric policy cannot decline

**Status:** declined 2026-08-08
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The refusal that shipped with [R-100](100-judge-abstention.md) is the judge's alone.
`RawRecallPolicy` and the three heuristic policies always return their nearest `k`, so on a
question memory cannot answer they hand back three nearest misses. The geometric equivalent would
be a relevance floor: a policy that drops a candidate below some similarity and may therefore
return nothing, which the `Ranking` the port returns can express and no policy computes.

**Declined 2026-08-08 on measurement**
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) decision 12).

The consumer was larger than the entry assumed. `recall_policy_from_config` in
`memory_builders.py` builds `JudgeRecallPolicy` with no `fallback` argument, so the shipped
default uses `RAW_RECALL_POLICY` and hands it the pool on an `InferenceError`, on a reply outside
the envelope, and on an order that parses to nothing usable. The cosine therefore ranks inside the
default deployment every time the model cannot be reached or its answer accepted, so a floor would
have been a default-path protection rather than an opt-in nicety.

The design was settled before the measurement: not a fifth policy, which a deployment would run
instead of the judge and which would leave that fallback unfloored, but a decorator over an inner
`RecallPolicy` plus one setting defaulting to `0.0`. It would threshold `hit.score`, because
`SPREAD` and `SWEEP` keys are measured against the kept set and do not compare; pre-filter the
pool, so no new `RankBasis` is needed; and never wrap the judge itself, since the vocabulary trap
is exactly where the answering note's cosine is low.

The calibration then ruled it out. Measured on the real embedder over this area's 41-note corpus
at the shipped pool width, with 8 questions about subjects no note mentions added for the
purpose, the answerable and unanswerable bands overlap. Gold notes score 0.4742 to 0.9063 while
the four adjacent unanswerable questions top out at 0.5112 to 0.6325, a separation of -0.1582,
and even the wholly unrelated questions reach 0.4994 against a lowest answerable gold of 0.4742.
The tightest floor that silences all four unanswerable questions, 0.6325, costs 6 of 22
answerable ones outright, takes MRR from 0.902 to 0.659, and drops the `TRAP` category from 0.81
to 0.17, which is the vocabulary trap the model rank exists for. Behind the alternative embedder
the conclusion holds while every number moves (separation -0.1933, the tightest floor 0.4485 at 7
of 22, `TRAP` 0.00), so the portability objection is measured rather than asserted. Behind the
shipped embedder the safe range and the useful range do not overlap at all: a floor costs nothing
only at or below 0.4742, while catching even the easiest population needs 0.4995, so they cross by
0.0253. Behind the alternative embedder they overlap by 0.0068, a setting whose whole safe and
useful range is seven thousandths wide, read off the sample minimum of 22 hand-built questions and
narrowing on a real store, where more notes mean a closer nearest neighbour for every question.

What the run establishes instead is why the shipped default is what it is: declining is a property
of reading, not of ranking, since a question memory cannot answer has the same geometry as a
question whose answer is worded unlike it. `CORTEX_MEMORY_RECALL=raw` is an opt-out of exactly
that capability, and the runbook says so.

The calibration ships as `packages/inference/tests/test_recall_floor_live.py` and needs only the
CPU embedder. Its instrument was proved able to fail before its result was trusted: an operator
that drops a hit fails the floor-of-zero identity, one that ignores its floor fails the absurd
end, and the finding itself fails with +0.2104 on a corpus restricted to the categories whose
populations do separate, which is the reopening condition written as a test.

**Reopens** behind an embedder whose populations separate, or on a signal that is not an absolute
cosine. The cross-encoder rank ([R-097](097-cross-encoder-rank.md)) is the candidate, since it
reads the pair rather than measuring the distance.

## History

- 2026-08-07: Opened by the abstention close as the half that close does not reach.
- 2026-08-08: The premise inverted without the entry closing when the default moved to `judge`,
  which makes a deployment that cannot decline an opt-out rather than the path of least
  resistance, and makes the entry smaller rather than moot.
- 2026-08-08: Declined on measurement, taking the area from 9 to 8 with nothing opening in its
  place.
