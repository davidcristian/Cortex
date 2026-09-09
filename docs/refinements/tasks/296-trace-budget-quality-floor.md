# What a bounded trace costs a hard answer is unmeasured

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-09
**Trigger:** a `CORTEX_REASONING_BUDGET` or `CORTEX_REASONING_BUDGET_BRAIN` default in
`docker/docker-compose.gpu.yml` other than `-1`, or a recorded run in this repo where the cortex or
the deep tier answers a question wrong at a bounded or zero budget and right at the unbounded
default.

Opened 2026-08-17 by the trace-budget landing
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) trace-budget addendum), which priced the knob in
seconds and left its cost in answers open.

Every number behind that knob is a latency: the trace falls from 2323 to 2996 characters to about
500 at a budget of 128, and the first word from 10.1 to 12.6 s to 1.7 to 2.6 s, with the reply the
same size and still finishing on its own. The quality side has one weak reading and one absence.
The weak reading is four multi-step items with a single right answer (a bat and ball, the five
machines, a train timetable sum, an ages puzzle), each answered correctly at unbounded, at 128 and
with thinking off entirely, which says only that the cortex pick does not need its trace for those.
The absence is everything the trace is actually for: the questions the deep tier was chosen over
faster candidates to reach an answer on ([ADR-0004](../../adr/ADR-0004-model-lineup.md)).

What would close it is a graded arm rather than a timed one: a set of questions hard enough that the
shipped model gets some of them wrong, run across unbounded, a few positive budgets and zero, scored
by something better than a reading of the replies. That is a corpus and a judge, which is why it did
not ride the landing; the landing's own advice, to start at 512 on a tier a user reads and treat
anything lower as a trade, is the placeholder until this exists.

## Trail

- 2026-09-06: **Held to the tree and not fired, on either clause, and the trigger is restated
  because neither clause was decidable as written.** The deployment half is now a grep: every
  shipped spelling of the knob is a compose default of `-1`,
  [docker-compose.gpu.yml](../../../docker/docker-compose.gpu.yml) line 139 for the cortex tier and
  line 160 for the deep one, and no justfile recipe, runbook command or env file in the tree sets
  either variable. The other five spellings in the tree are `monkeypatch.setenv` calls in
  `brain/packages/model_manager/tests/test_model_roster.py` and one measurement session recorded in
  the [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) trace-budget addendum, which started the
  model host at 128 to take the latency readings this entry is about. A test and a measurement are
  not a deployment. The answer half said "a wrong answer somebody blames on it", which names a
  person's judgement rather than anything the tree records, so it now names the comparison a
  recorded run has to show: the same tier, the same question, right unbounded and wrong bounded.
- 2026-09-06: **The absence this entry describes has been filled on a different tier, by a
  different lever, and that does not answer it.** Since it was opened, the subagent tier acquired
  `--reasoning-budget 0` on its argv and the port acquired a per-request `reasoning_budget_tokens`,
  and the ADR-0005 measurements behind both do read a bounded trace against the answer rather than
  against the clock: on the shipped subagent pick at a cap of 256, an unbounded trace spent 591 to
  854 characters and returned nothing inside the cap, a budget of 128 spent 310 to 516 and returned
  an answer, and 32 spent 0 to 92 and returned a longer one. That is bounding improving the answer
  under a cap, on a 4B tier nobody reads a trace from, at the request rather than in the
  deployment. This entry is still about the two tiers a user reads, where the graded corpus and the
  judge it asks for do not exist.
