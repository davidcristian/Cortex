# The end-to-end turn-cost harness

**Status:** landed 2026-08-09
**Area:** repo-gates
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-08 by the run that moved `CORTEX_MEMORY_RECALL` to `judge`
([ADR-0038 turn-cost addendum](../../adr/ADR-0038-ranked-recall.md)). It is filed here rather than
in [memory.md](../index.md#memory) because what is unresolved is where a driver that spans the seam lives
and how it is run, which is what this section is about, while the recall entry the measurement
served closed the same day and left nothing open about recall. Every other measurement in that
ADR names an `integration`-marked test that reproduces it
(`packages/inference/tests/test_rerank_judge_wide_live.py`, `test_history_recap_live.py`,
`test_session_title_live.py`); the turn-cost numbers name none. What produced them was a
host-side Python client that opened one `Converse` stream per turn against the brain's
`BrainService`, timed the first `TextDelta` and the `TurnComplete`, and ran three blocks of 48
turns in A/B/A order with a container restart between them, and it lived in a scratchpad, so the
published 0.515 s of time to first token is a figure nobody can re-derive without rebuilding the
driver from that addendum's prose. **The stated reason for punting was that a driver spanning the
seam is not an adapter test and wanted its own decision about where such a thing belongs, and
reading the tree afterwards makes that decision smaller than the punt implied:**
`packages/orchestrator/tests/test_schedule_live_seam.py` already is one, an `integration`-marked
host-side client that drives the shipped `BrainServiceStub` against the compose stack and cleans
up after itself, so the placement question has a precedent and the answer is probably
`packages/orchestrator/tests/`. What has no precedent is the rest of the shape: a measurement
restarts containers between arms with one environment variable changed, pre-seeds a corpus into a
session scope, and reports a distribution with a confidence interval rather than asserting a
bound, none of which a pytest case expresses well, and a committed one would still have to decide
whether the A/B/A control arm is part of the test or part of a runbook. **Trigger:** the next
end-to-end measurement of a whole turn (a vision turn, a tool turn, a handoff), which would
otherwise pay the same build cost again, or any challenge to the shipped recall default that
needs the run reproduced rather than cited.

**The trigger fired 2026-08-08 and the entry stays open, narrower
([ADR-0038 fold-under-load addendum](../../adr/ADR-0038-ranked-recall.md)).** The fold-under-load
measurement is the next end-to-end run of a whole turn, and it committed its driver rather than
leaving it in a scratchpad: `packages/orchestrator/tests/test_fold_under_load_live.py`,
`integration`-marked, in the directory this entry guessed. **Two thirds of what it named as
unresolved are settled by that second instance.** Placement is no longer a guess, since
`test_schedule_live_seam.py` and this one now sit beside each other doing the same kind of thing;
and pre-seeding a corpus into a session scope has a shape, which is writing through the real
`RedisSessionStore` under test-owned session ids and deleting them in a `finally`, exactly the
schedule test's own discipline. **The rest is untouched, and the reason is a distinction this
entry did not draw.** A measurement whose subject lives INSIDE the brain process is better driven
in-process than across the wire: the fold run had to timestamp a lock, so it wired the real
adapters and drove the shipped `converse` generator directly, which let it change an arm by
constructing a config rather than by restarting a container, and let it read the thing being
measured at all. So it never met the two hard parts. **What is still unresolved is therefore
narrower and better named:** how a committed test expresses an arm that needs the brain container
restarted with one environment variable changed (which only a driver going over gRPC ever needs),
and how one reports a distribution with an interval rather than asserting a bound, the
fold run having reported numbers and asserted only invariants that hold whatever the model says.
The A/B/A question is the same question in another form: a control arm that is another
container configuration belongs wherever the restart belongs. **Trigger unchanged**, minus the
half this run answered: the next measurement that genuinely needs a differently-configured brain
container between arms, or a challenge to the shipped recall default.

**Landed 2026-08-09, on the second reading of that trigger** (the run reproduced rather than
cited), and the answer to both remaining halves is one division of labour rather than one clever
test ([ADR-0038 harness addendum](../../adr/ADR-0038-ranked-recall.md)). **An arm is a container
configuration, so a restart is a deployment step and lives in a recipe**, `just turn-cost`, which
brings the gpu plus memory stacks up and runs three blocks in A/B/A order, recreating only the
brain between them. A test that recreated its own subject would both measure the stack and
administer it, would spell the whole compose file set a second time inside a test file, and would
own a stack it neither brought up nor could restore. **That decision then makes the second half's
answer forced rather than chosen**, which is why the entry was right to call them one question
and wrong about which one: restarting between arms puts the arms in
separate processes, so no one process can hold the comparison, so each block writes a JSON sample
and the interval is computed afterwards. It is computed by `scripts/contrast.py`, the first
module in that tree that gates nothing, gated at 100% like everything beside it, which pairs the
blocks question by question, bootstraps the mean of the per-question differences over a printed
seed, and stars an interval that does not span zero. The block driver
(`packages/orchestrator/tests/test_turn_cost_live.py`) therefore asserts only invariants, in the
fold run's discipline. The A/B/A control needed no separate answer at all: it is the recipe
running its outer two blocks in one configuration and its middle block in another.
**Two of this entry's own claims did not survive the tree.** It said corpus seeding was settled
by the fold run, whose shape is conversation history written through `RedisSessionStore` and
deleted with `delete`; a turn-cost corpus is 41 memory notes written through
`PgVectorMemoryStore`, each needing the CPU embedder first, and removed with `delete_scope`,
so what carried over was the discipline (test-owned ids, deletion in a `finally`) and never the
mechanism. And the harness it described could not have been written at the time it was filed:
**no `CORTEX_MEMORY_*` knob reached the dockerized brain at all**, the memory override having set
the backend, the DSN and the embedder endpoint and nothing else, so the runbook had been
documenting `CORTEX_MEMORY_RECALL=raw` and `CORTEX_MEMORY_RECALL_AUDIT=1` past an operator with
no way to supply either. That is fixed rather than filed: every remaining `MemoryConfig` field is
a bare pass-through key on the override, which reaches the container when the host sets it and
never enters it otherwise, so no shipped default is restated in YAML where it could drift.

## Trail

- 2026-08-08: Opened by the run that moved `CORTEX_MEMORY_RECALL` to `judge`, and filed under
  test-runner mechanics rather than under memory because what was unresolved is where a driver
  that spans the seam lives and how it is run.
- 2026-08-08: The trigger fired the same day and the entry stayed open, narrower. The
  fold-under-load run committed its driver in the directory this entry guessed, settling placement
  and the shape of seeding a corpus, but it never met the two hard parts, because a run whose
  subject is a lock inside the brain process is better driven in-process than across the wire.
- 2026-08-09: Landed on the second reading of its trigger, the recall default reproduced rather
  than cited, and the close lowered the area count from five to four rather than exchanging it. An
  arm is a container configuration, so the restarts live in a `just turn-cost` recipe, which puts
  the arms in separate processes, so each block writes a JSON sample and `scripts/contrast.py`
  reports the blocked paired bootstrap while the block driver asserts only invariants. Two of the
  entry's own claims did not survive the tree, and the defect it had to fix on the way, that no
  `CORTEX_MEMORY_*` knob reached the dockerized brain at all, was fixed rather than filed. The
  block driver's own limits were written into the harness addendum rather than filed as a backlog
  entry beside it.
