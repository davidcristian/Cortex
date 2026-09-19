# What a bounded trace costs a hard answer is unmeasured

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-09-19
**Trigger:** a `CORTEX_REASONING_BUDGET` or `CORTEX_REASONING_BUDGET_BRAIN` default in
`docker/docker-compose.gpu.yml` other than `-1`, or `CORTEX_REPLY_TRACE_TOKENS` given a value by
any compose file, recipe or env file in this tree, or a recorded run in this repo where the cortex
or the deep tier answers a question wrong at a bounded or zero budget and right at the unbounded
default.

Opened 2026-08-17 by the trace budget
([ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)), which measured the setting in
seconds and left its cost in answers open.

Every number behind that setting is a latency: the trace falls from 2323 to 2996 characters down to
about 500 at a budget of 128, and the first word arrives in 0.17 to 0.23 of the unbounded wait on
the same question, with the reply the same size and still finishing on its own. The quality side
has one weak reading and one absence. The weak reading is four multi-step items with a single right
answer (a bat and ball, the five machines, a train timetable sum, an ages puzzle), each answered
correctly at unbounded, at 128 and with thinking off entirely, which says only that the cortex pick
does not need its trace for those. The absence is everything the trace is for: the questions the
deep tier was chosen over faster candidates to answer
([ADR-0004](../../adr/ADR-0004-model-lineup.md)).

What would close it is a graded comparison rather than a timed one: a set of questions hard enough
that the shipped model gets some of them wrong, run across unbounded, a few positive budgets and
zero, scored by something better than reading the replies. That is a corpus and a judge, which is
why it was not done at the time. The advice recorded with the setting, to start at 512 on a tier a
user reads and treat anything lower as a trade, is the placeholder until this exists.

## History

- 2026-09-06: Not triggered on either clause, and the trigger restated because neither was
  decidable as written. The deployment half is now a grep: every place the setting is written in a
  shipped file is a compose default of `-1`,
  [docker-compose.gpu.yml](../../../docker/docker-compose.gpu.yml) line 139 for the cortex tier and
  line 160 for the deep one, and no justfile recipe, runbook command or env file sets either. The
  other five occurrences are `monkeypatch.setenv` calls in
  `brain/packages/model_manager/tests/test_model_roster.py` and one measurement session recorded in
  [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md), which started the model host
  at 128 to take the latency readings. A test and a measurement are not a deployment. The answer
  half said "a wrong answer somebody blames on it", which names a person's judgement, so it now
  names the comparison a recorded run has to show.
- 2026-09-06: The absence this entry describes has been filled on a different tier, by a different
  setting, and that does not answer it. The subagent tier acquired `--reasoning-budget 0` on its
  argv and the port acquired a per-request `reasoning_budget_tokens`, and the ADR-0005 measurements
  behind both do compare a bounded trace against the answer rather than the clock: on the shipped
  subagent pick at a cap of 256, an unbounded trace spent 591 to 854 characters and returned
  nothing inside the cap, a budget of 128 spent 310 to 516 and returned an answer, and 32 spent 0
  to 92 and returned a longer one. That is on a 4B tier nobody reads a trace from. This entry is
  about the two tiers a user reads.
- 2026-09-14: Neither clause has come true, and the second half of the earlier survey is out of
  date. Both shipped defaults are still `-1` at lines 139 and 160, and nothing sets either variable
  as a deployment: the GPU runbook's one instruction to set `CORTEX_REASONING_BUDGET=0` is a repair
  an operator applies after a result rather than a value this stack starts with.
  `test_model_roster.py` now has eight `monkeypatch` occurrences rather than five, and two more
  sites exist in `scripts/modelhostcouplings.py`, where `crosscheck` compares both tiers' `-1` as
  one set. None of those is a deployment.
- 2026-09-19: Neither clause has come true, and the deployment clause missed a second setting. Both
  shipped defaults are still `-1`, now at
  [docker-compose.gpu.yml](../../../docker/docker-compose.gpu.yml) lines 161 and 182 after the
  2026-09-17 settings pass-through moved them, and nothing else gives either a value: eight
  `monkeypatch` occurrences in `test_model_roster.py`, the two in
  `scripts/modelhostcouplings.py`, and comments in `config_reply.py` and
  `docker-compose.subagents.yml`. The clause read only the argv budget, but
  `CORTEX_REPLY_TRACE_TOKENS` bounds the same trace per request on both tiers a user reads, and
  since 2026-09-17 `docker/docker-compose.yml` passes it through by name, so a value set on the
  host now reaches the brain. It ships with no value there and in no recipe or env file, and the
  trigger now names it. The first-word figures above were seconds on one card; they are now the
  ratio of each question's bounded wait to its own unbounded one in the tier-budget table of the
  thinking-switch readings.
