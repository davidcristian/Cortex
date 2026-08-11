# A geometric policy cannot decline

**Status:** declined 2026-08-08
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The refusal that landed is
the judge's alone. `RawRecallPolicy` (the default) and the three heuristic policies always return
their nearest `k`, so on a question memory cannot answer, every deployment that has not opted into
`CORTEX_MEMORY_RECALL=judge` still receives three nearest misses, which is the same turn the
closed entry described and a different cause. **The premise inverted on 2026-08-08 without the
entry closing**, when the default moved to `judge` (the turn-cost addendum): the shipped stack can
decline now, and what cannot is a deployment that sets `CORTEX_MEMORY_RECALL` to `raw` or to one
of the heuristics, which is an opt-out rather than the path of least resistance. That makes the
entry smaller and not moot, since the reasons the floor was declined are about the floor and not
about how many deployments meet the gap. The geometric analogue is a **relevance floor**: a
policy that drops a candidate below some similarity and may therefore return nothing, which the
`Ranking` the port now returns can express and no policy computes. It was considered during the
close and declined on two counts that would have to be answered first. A cosine threshold is not
portable across embedding models, since the absolute values a floor is calibrated against belong
to whichever `Embedder` produced them and mean something else behind another one. And a floor on
`RawRecallPolicy` changes the founding behavior, the one policy whose promise is that recall is
byte-for-byte v1, so the floor belongs on a fifth policy rather than on the default. **Trigger:**
a deployment that wants recall to stay geometric and still be able to say nothing, which is also
the shape the first complaint about irrelevant recalled memories under the shipped default would
take, or a calibration run that gives the floor a defensible number.
**Closed 2026-08-08 as declined on measurement, the second arm of its own trigger having been run**
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) relevance-floor addendum). **The consumer was bigger
than the entry's own framing**, which is the first thing the re-derivation turned up and the reason
this was measured rather than shrugged at: `recall_policy_from_config` (`memory_builders.py`)
builds `JudgeRecallPolicy` with no `fallback` argument, so the shipped default carries
`RAW_RECALL_POLICY` and hands it the pool on an `InferenceError`, on a reply outside the envelope,
and on an order that parses to nothing usable. The cosine therefore ranks inside the **default**
deployment every time the model cannot be reached or believed, which is exactly the moment nothing
else is watching, so a floor would have been a default-path guard and not the opt-out nicety this
entry describes. **The design was settled before the measurement could bias it, and it is not the
fifth policy this entry proposes:** a fifth `MemoryRecallName` is a policy a deployment runs
*instead of* the judge, which leaves that fallback exactly as unfloored as it is today, and it
multiplies the matrix because a floor is orthogonal to how you rank. The shape that composes is a
decorator over an inner `RecallPolicy` (the shape the judge's own fallback already is) plus one
knob defaulting to `0.0`, which protects the founding byte-for-byte promise by the default rather
than by a separate name, thresholds `hit.score` because `SPREAD` and `SWEEP` keys are measured
against the kept set and do not compare, pre-filters the pool so no new `RankBasis` is needed, and
never wraps the judge itself, since the vocabulary trap is precisely where the answering note's
cosine is low. **None of it survives the calibration.** Measured on the real embedder over this
area's own 41-note corpus at the shipped pool width, with a third population added for the
purpose (8 questions about subjects no note mentions), the answerable and unanswerable bands
overlap: gold notes score 0.4742 to 0.9063 while the four adjacent unanswerable questions top out
at 0.5112 to 0.6325, a separation of **0.1582 negative**, and even the wholly unrelated questions
reach 0.4994 against a lowest answerable gold of 0.4742. The tightest floor that silences all four
unanswerable questions, 0.6325 and derived from the data rather than picked off a grid, costs
**6 of 22 answerable ones outright**, takes MRR from 0.902 to 0.659, and drops the `TRAP` category
from 0.81 to **0.17**, which is the vocabulary trap the model rank exists for. That is the cheapest
the promise ever gets. Behind the alternative embedder the conclusion holds (separation 0.1933
negative, the tightest floor 0.4485 at 7 of 22 and `TRAP` 0.00) while
every number moves, so the entry's portability objection is now measured rather than asserted. The
safe range and the useful range do not even overlap behind the shipped embedder: a floor costs
nothing only at or below the lowest answerable gold, 0.4742, while catching even the easiest
population needs 0.4995, so they cross by 0.0253. Behind the alternative embedder they do overlap,
by 0.0068, which is a knob whose whole safe and useful range is seven thousandths wide, read off
the sample minimum of 22 hand-built questions rather than off a bound, and narrowing on a real
store where more notes mean a closer nearest neighbour for every question. **What the run establishes instead is why the shipped default is what
it is:** an abstention is a property of reading and not of ranking, since a question memory cannot
answer has the same geometry as a question whose answer is worded unlike it, so
`CORTEX_MEMORY_RECALL=raw` is an opt-out of exactly that capability and the runbook now says so.
The calibration ships as `packages/inference/tests/test_recall_floor_live.py` rather than staying
in a scratchpad, needing only the CPU embedder, and its instrument was proved able to fail before
its result was believed: an operator that drops a hit reddens the floor-of-zero identity, one that
ignores its floor reddens the absurd end, and the finding assertion itself fails with **+0.2104**
on a corpus restricted to the categories whose populations do separate, which is the reopening
condition wired as a test. **Reopens** behind an embedder whose populations separate, or on a
signal that is not an absolute cosine; the already-filed **cross-encoder** rank is the candidate,
since it reads the pair rather than measuring the distance. Nothing opened in its place.

## Trail

- 2026-08-07: Opened by the abstention close as the half that close does not reach, the refusal that
  landed being the judge's alone.
- 2026-08-08: The premise inverted without the entry closing when the default moved to `judge`,
  which makes what cannot decline an opt-out rather than the path of least resistance, and makes the
  entry smaller rather than moot.
- 2026-08-08: Closed as declined on measurement, the second arm of its own trigger having been run,
  taking the area from 9 to 8 with nothing opening in its place. No threshold separates the
  answerable from the unanswerable populations behind either embedder the repo ships a path for, so
  the floor fails before portability is reached. The re-derivation also found the consumer bigger
  than the entry's own framing, the shipped default's own fallback being the cosine, which is why
  this was measured rather than shrugged at.
