# The end-to-end turn-cost measurement

**Status:** done 2026-08-09
**Area:** repo-checks
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The run that set `CORTEX_MEMORY_RECALL` to `judge` published a time to first token of 0.515 s that
nobody could reproduce. Every other measurement in that ADR names an `integration`-marked test
(`packages/inference/tests/test_rerank_judge_wide_live.py`, `test_history_recap_live.py`,
`test_session_title_live.py`); the turn-cost numbers named none. They came from a host-side Python
client that opened one `Converse` stream per turn against the brain's `BrainService`, timed the
first `TextDelta` and the `TurnComplete`, and ran three blocks of 48 turns in A/B/A order with a
container restart between them. It lived in a scratchpad directory.

The open question was where a driver that crosses the body and brain boundary lives and how it is
run. Filed here rather than under memory because the recall question itself closed the same day.

Closed 2026-08-09 by splitting the work rather than writing one test that does everything. A
variant is a container configuration, so a restart is a deployment step and belongs in a recipe:
`just turn-cost` brings up the gpu and memory stacks and runs three blocks in A/B/A order,
recreating only the brain between them. A test that recreated its own subject would both measure
the stack and administer it, would repeat the whole compose file set inside a test file, and would
own a stack it neither started nor could restore. Because the variants then run in separate
processes, no single process holds the comparison: each block writes a JSON sample and the
interval is computed afterwards by `scripts/contrast.py`, which pairs the blocks question by
question, bootstraps the mean of the per-question differences over a printed seed, and marks an
interval that does not span zero. The block driver
(`packages/orchestrator/tests/test_turn_cost_live.py`) asserts only invariants. The A/B/A control
needed no separate answer: it is the recipe running its outer two blocks in one configuration and
its middle block in another.

Two claims in the entry did not survive. It said corpus seeding was settled by the fold-under-load
run, whose corpus is conversation history written through `RedisSessionStore` and removed with
`delete`; a turn-cost corpus is 41 memory notes written through `PgVectorMemoryStore`, each
needing the CPU embedder first and removed with `delete_scope`. What transferred was the practice
(test-owned ids, deletion in a `finally`), not the mechanism. And the measurement it described
could not have been written when it was filed, because no `CORTEX_MEMORY_*` setting reached the
dockerized brain at all: the memory override set the backend, the DSN and the embedder endpoint
and nothing else, so the runbook documented `CORTEX_MEMORY_RECALL=raw` and
`CORTEX_MEMORY_RECALL_AUDIT=1` to an operator who had no way to supply either. That was fixed
here: every remaining `MemoryConfig` field is a pass-through key on the override, set in the
container when the host sets it and absent otherwise, so no default is repeated in YAML.

## History

- 2026-08-08: Opened by the run that set `CORTEX_MEMORY_RECALL` to `judge`, and filed under
  test-runner mechanics because what was unresolved is where a driver that crosses the body and
  brain boundary lives and how it is run.
- 2026-08-08: The fold-under-load run later the same day committed its driver as
  `packages/orchestrator/tests/test_fold_under_load_live.py`, settling where such a driver lives
  and how a corpus is pre-seeded, but not the two hard parts, because a run whose subject is a lock
  inside the brain process is driven in-process rather than over the wire.
- 2026-08-09: Closed. Restarts live in a `just turn-cost` recipe, which puts the variants in
  separate processes, so each block writes a JSON sample and `scripts/contrast.py` reports the
  blocked paired bootstrap while the block driver asserts only invariants. Two of the entry's
  claims did not survive, and the defect found on the way, that no `CORTEX_MEMORY_*` setting
  reached the dockerized brain, was fixed rather than filed. The block driver's own limits are
  stated in its docstring.
