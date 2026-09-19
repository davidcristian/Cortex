# Runbook: the recall policies and what they cost

What each `CORTEX_MEMORY_RECALL` policy does and what it costs, and the two harnesses that
measure it: what a policy costs a whole turn, and how wide the recall audit line's widest field
gets. Bringing the store up and reading the audit line: [memory-pgvector.md](memory-pgvector.md).

## The policies

`judge` is the default. It hands the over-fetched pool to the resident cortex and takes back an
ordering, so a recalling turn spends one bounded cortex generation before it answers and the GPU
stack has to be up. It falls back to raw cosine whenever the model cannot be reached or its reply
cannot be read as an order, and the fallback is visible rather than silent. Measured over 48 real
turns per condition on the 24 GB card: the rank alone is 0.877 s at the pool a turn asks for (`k`
5 at `pool_factor` 4, so 20 candidates), and a turn's time to first token rises 0.515 s (95% CI
0.116 to 0.915), less than the rank itself because a rank that keeps 1.17 notes gives the reply a
smaller memory block to read than the cosine's 5. Reproduced 2026-08-09 by `just turn-cost` below at 0.539 s (95% CI 0.054 to 1.111) against a
control whose interval spans zero. That run puts the
whole-turn cost at 0.979 s rather than the 0.526 s first published, nearly all of the excess in
the question memory cannot answer, where a declining rank leaves the model saying at length that
it does not know.

`raw` is top-`k` cosine and is the opt-out: set `CORTEX_MEMORY_RECALL=raw` for the original
behaviour, on a stack with no GPU, or to take that half second back. `reranked`, `mmr` and
`recency_mmr` are the heuristic policies, tuned by the `CORTEX_MEMORY_RECALL_*` settings.

`judge` is also the only policy that can return nothing. Asked a question none of the candidates
answers, it says so and the turn is assembled with no recalled memories, which the audit line
reports as the `demur` basis with an empty hit list. That is a different line from a fallback,
which shows the fallback's basis and the notes it chose, and from an empty pool, which shows the
ranking policy's own basis. The geometric policies cannot decline, so under `raw` a question
memory cannot answer still recalls the three least unrelated notes it holds. A similarity floor
was calibrated on the real embedder and then declined: over the 41-note corpus the questions
memory can answer and the questions it cannot overlap on cosine, so every floor that silences the
second silences the first. Reproduce that with
`packages/inference/tests/test_recall_floor_live.py`, which needs only the CPU embedder below.

## Measuring what a ranking policy costs a whole turn

```
CORTEX_MODELS_DIR=/path/to/models just turn-cost
```

That brings up the gpu and memory stacks and runs three blocks in A/B/A order, `raw` then `judge`
then `raw`, recreating only the brain between them with `CORTEX_MEMORY_RECALL` changed and
`CORTEX_MEMORY_SCOPE=session` plus `CORTEX_MEMORY_RECALL_AUDIT=1` on throughout. Each block runs
`packages/orchestrator/tests/test_turn_cost_live.py`, which opens one `Converse` stream per turn
against a fresh session pre-seeded with the whole 41-note recall corpus, times the first
`TextDelta` and the `TurnComplete`, and writes its sample to `measurements/`. The recipe then runs
`scripts/contrast.py` over the three samples and prints the blocked paired bootstrap. The two
outer blocks are the control: same configuration, different times, so their contrast is the noise
floor the middle one has to clear. Roughly 15 minutes at the default of eight repetitions.

`just turn-cost mmr raw 4` measures a different policy, and `just turn-cost judge judge` makes
both outer blocks match the middle one, which is the null run to reach for when the harness itself
is in doubt. Nothing is torn down at the end. The samples in `measurements/` are gitignored, being
evidence of one run on one machine; the reading they support belongs in
[ranked recall](../readings/ranked-recall.md).

## Measuring how wide that audit line's widest field gets

`dropped` is the widest value the brain attaches to any log line, and `cortex_core.VALUE_CHARS`,
the per-field bound, is sized to clear it. The figure it was sized against was synthesised, so
this is what reads the width off lines a live stack wrote instead:

```
CORTEX_MODELS_DIR=/path/to/models just recall-width
```

That brings up the gpu and memory stacks, recreates the brain with `CORTEX_MEMORY_SCOPE=session`
and `CORTEX_MEMORY_RECALL_AUDIT=1`, copies
`brain/packages/orchestrator/tests/recall_trail_probe.py` and the wide recall corpus into the
container, and runs the probe there. Inside the container it seeds a fresh session scope with all
41 notes through `MemoryRecaller.record`, so the ids are minted by the shipped factory and the
vectors by the real embedder, then recalls every question the corpus has. Forty one notes against
a pool of twenty is what makes the pool a real pool rather than the whole store. Each block
finishes with real turns over the brain's own loopback gRPC service, whose lines come back out of
`docker compose logs brain` rather than off the probe's stream, which is what says the cheap phase
measures the same lines a serving turn writes. `scripts/trailwidth.py` then reports each capture's
range, median and a seeded bootstrap of the mean, and the count of renderings the bound cut.

**The whole line is reported beside the field**, because the per-value bound leaves the line
unbounded. These are not the widest lines the brain writes: the tool audit's are, five of their
eleven fields containing text the brain did not choose, and one with all five past the bound
renders at 10,593 characters, against an audit line's 4,464 at the shipped caps and the 16 KiB
limit a container's log driver ends a message at. The width counted is the rendering rather than
the captured text, so the `brain-1  |` prefix `docker compose logs` adds is left out. Read the two
ranges together rather than one after the other: the widest field and the widest line are not the
same line, since a rank that keeps three notes writes a narrower `dropped` and a wider line than
one that keeps none.

The harness runs two blocks by default, because the claim under test is about a maximum and one
sample of a maximum can only grow with more runs. `just recall-width 1 2 0` is the quick shape
when the harness itself is in doubt: one block, two passes, no turns. **Read the cut count
first.** Any number above zero says the bound cut a value that ships, which is the failure
`VALUE_CHARS` was sized to avoid, and it makes every width beside it a reading of the bound rather
than of the field.
