# Readings: ranked recall

What the recall judge buys and costs, what a relevance floor would cost, and what counting the
candidate set costs. Cited by [ADR-0038](../adr/ADR-0038-ranked-recall.md), decisions 7, 11, 12,
14 and 22. Every quality reading here is over notes written for the measurement by the author of
the policy, so it shows the mechanism and is not a benchmark of real memories.

## Rank quality over the wide corpus

**2026-08-07.** 41 notes and 26 questions in six categories (`recall_corpus.py`), at `k` 3 over a
pool of 12 (the default `pool_factor` of 4), against the resident cortex (gemma-4-12B). Each
category is built so the judge could lose: `LEXICAL` answers in the question's own words, `TWIN`
holds two near-duplicates, `STALE` a superseded version, `CLAUSE` an answer in a subordinate clause,
`ABSENT` a question nothing answers. The gold note was inside the pool for all 22 answerable
questions. Mean reciprocal rank:

| category (n) | cosine | judge | reversed cosine (control) |
| --- | --- | --- | --- |
| `TRAP`, no shared words (6) | 0.806 | 1.000 | 0.000 |
| `LEXICAL` (4) | 1.000 | 1.000 | 0.000 |
| `TWIN` (4) | 1.000 | 1.000 | 0.000 |
| `STALE` (4) | 0.750 | 1.000 | 0.000 |
| `CLAUSE` (4) | 1.000 | 1.000 | 0.000 |
| `ABSENT`, returned nothing (4) | 0 of 4 | 4 of 4 | 0 of 4 |
| aggregate over the 22 answerable | 0.902 | 1.000 | 0.000 |

No recall fell back (0 of 26); the judge kept one note on 21 of the 22 answerable questions, with
the gold first every time. A refusal costs what a rank does, since the pool prompt is evaluated
either way. Method: `packages/inference/tests/test_rerank_judge_wide_live.py`, integration-marked.

**2026-08-06, the bounds.** The same judge before and after `rank_bounds(k)` on ten notes and six
questions: identical picks (MRR 1.000 both), decoded tokens per rank from 448 to 613 down to 12 to
22, cost per recall from 18.4 s to 0.9 s. A title under `TITLE_BOUNDS` decoded 4 tokens where the
unbounded request decoded 235 to 303, the same title each run. Method:
`test_rerank_judge_live.py` and `test_session_title_live.py`, with llama-server's `eval time`
lines.

**2026-09-24, the deep model.** The same corpus and shape against gemma-4-31B (QAT q4_0), the model
the deep phase of a handoff asks, with every layer on the card at `--ctx-size 8192 --parallel 1` and
each rank request sending thinking off: every MRR and `ABSENT` count equals the cortex's above, and
no recall fell back (0 of 26). The judge kept one note on 18 of the 22 answerable questions and two
or three on the four `STALE` ones, the current version first each time. A recall cost 0.89 s (23.3
s over 26); the server's own time per rank was 0.74 to 1.08 s, about 290 prompt tokens and 12 to 22
decoded, after a first request of 1.75 s. The SM clock sat at a median 0.66 of the card's maximum
(0.61 to 0.69). One recap of the same history (`test_history_recap_live.py`) stored a 428-character
account in a 3.8 s cold pass, and the recapped reply kept the booking reference the shipped window
lost. Method: the two live tests against the served model, from a frozen copy of the tree
(`measurements/sitting2-2026-09-24/`).

## Whole turns, judge against raw

**2026-08-09.** Three blocks in A/B/A order (`raw`, `judge`, `raw`) through `just turn-cost`: six
questions (the first of each category), eight repetitions, 48 measured turns a block, `k` 5 over a
pool of 20, gemma-4-12B resident on a 24 GB card. Blocked by question, 20,000 seeded resamples.

| contrast | time to first token | whole turn |
| --- | --- | --- |
| judge against raw | +0.539 s (95% CI +0.054 to +1.111) | +0.979 s (95% CI +0.098 to +2.313) |
| raw against raw (null) | +0.066 s (95% CI -0.287 to +0.410) | +0.144 s (95% CI -0.197 to +0.471) |

The baseline time to first token was 3.518 s, so the judge adds about 15% to it. The whole-turn cost
sits mostly in one cell: the unanswerable question costs +4.13 s under the judge (+1.76 s to first
token), because a demurred turn has no memory block and the reply explains at length that it does
not know (675 characters against 84). That cell accounts for 70% of the whole-turn mean. An earlier
run of the same protocol on 2026-08-08 measured +0.515 s to first token.

**2026-08-08, same shape.** A rank alone at `k` 5 over a pool of 20 costs 0.877 s (median 0.859, n
30), more than the turn pays, because the judge hands the reply 1.17 notes where the cosine hands it
5. Up to the pgvector search a turn takes the same time under both variants; the whole difference is
after it, before the first token. Read off the audit trail at that width: MRR 0.767 (raw) against
1.000 (judge), unanswerable questions returning nothing 0 of 8 against 8 of 8, fallbacks 0 of 48.

Method: `just turn-cost`, the driver `brain/packages/orchestrator/tests/test_turn_cost_live.py`,
the report `scripts/contrast.py` over the committed samples.

## A relevance floor

**2026-08-08.** The store's cosine for three populations at the shipped pool width (`k` 3,
`pool_factor` 4): the 22 answerable questions, the 4 `ABSENT` ones (unanswerable, adjacent to
notes the corpus holds) and 8 `UNRELATED` ones about subjects no note mentions.

| population | nomic-embed-text-v1.5 (ships) | nomic-embed-text-v2-moe |
| --- | --- | --- |
| answerable, gold note's own score | 0.4742 to 0.9063 | 0.2552 to 0.8176 |
| unanswerable and adjacent, best hit | 0.5112 to 0.6325 | 0.2939 to 0.4485 |
| unanswerable and unrelated, best hit | 0.4057 to 0.4994 | 0.1650 to 0.2484 |
| lowest gold less highest adjacent | -0.1582 | -0.1933 |

The cheapest floor that silences all four adjacent questions behind the shipped embedder is
0.6325; it silences 6 of the 22 answerable questions and takes MRR from 0.902 to 0.659, and `TRAP`
from 0.81 to 0.17. Behind v2-moe it is 0.4485, costing 7 of 22 and MRR 0.841 to 0.591. The range
that is both safe (at or below the lowest gold) and useful (above every unrelated question) is empty
behind the shipped embedder, crossing by 0.0253, and 0.0068 wide behind the other. Over `LEXICAL`
plus `ABSENT` alone the populations do separate, by +0.2104, which is the reopening condition the
test asserts. Method: `packages/inference/tests/test_recall_floor_live.py`, CPU embedder only.

## Counting the candidate set

**2026-08-10.** Postgres 16 with pgvector, the shipped `memories` schema, 768-dimension vectors,
`k` 20, six repetitions a shape.

| shape | 20k rows | 100k rows |
| --- | --- | --- |
| ranked `SELECT`, unscoped | 290 ms | 520 ms |
| ranked `SELECT`, 3 of 50 scopes | 19 ms | 88 ms |
| `count(*)`, unscoped | 0.45 ms | 2.0 ms |
| `count(*)`, scoped | 0.12 ms | 0.18 ms |
| ranked `SELECT` plus `count(*) OVER ()` | 293 ms | 1480 ms |

The count is an index-only scan over `memories_scope_idx` with no heap fetches, so it stays under 1%
of the search as the table grows; with 5,000 unvacuumed inserts it rose to under 6%. Method:
`EXPLAIN (ANALYZE, BUFFERS)` over a seeded table; the contract check
`check_count_candidates_sizes_the_set_a_search_ranked` runs against real pgvector.
