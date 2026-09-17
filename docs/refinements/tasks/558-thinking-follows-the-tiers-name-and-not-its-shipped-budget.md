# Thinking follows the tier's name and not its shipped budget

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a deployment that starts the cortex or the deep tier with `CORTEX_REASONING_BUDGET` or
`CORTEX_REASONING_BUDGET_BRAIN` at anything other than `-1`, and wants the injection harness to draw
that tier's lever rows as it runs them. Read it with `grep -n 'CORTEX_REASONING_BUDGET'
docker/docker-compose.gpu.yml`, which names both variables and defaults both to `-1` today, and
confirm what a tier's tail then holds with `ModelHostConfig(...).tiers()`.
**Verified:** 2026-09-17

Opened 2026-09-05 by the close of
[R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which made a
`Model` name its tier and read `thinking` off it.

`Model.thinking` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
is `tier != SUBAGENT_TIER`: the subagent tier is the thinking-off tier because ADR-0010 made it
one, and the cortex and deep tiers think because they ship with the unbounded budget. That is a
reading of the tier's name. The same `ModelHostConfig` the harness reads the head off carries the
answer structurally, in whether the tier's `extra` ends its trace at zero, and the harness does not
read it there.

**Measured 2026-09-08 and re-read 2026-09-17, and the two readings still agree everywhere the stack
runs.** Both variables default to `-1` in `docker/docker-compose.gpu.yml`, and
`_UNRESTRICTED_REASONING` in `brain/packages/model_manager/src/cortex_model_manager/config.py` emits
no flag at that value. Since 2026-09-13 every tail also carries the tier's host-RAM prompt cache, so
the tails read:

| tier | `extra` at the shipped default | `extra` with both budgets at zero |
| --- | --- | --- |
| cortex | `('--cache-ram', '8192')` | `('--cache-ram', '8192', '--reasoning-budget', '0')` |
| brain | `('--cache-ram', '0')` | `('--cache-ram', '0', '--reasoning-budget', '0')` |
| subagent-gpu | the reasoning-off pair, then `('--cache-ram', '0')` | the same |

`Model.thinking` reads `True` for the first two rows of either column, so the nominal reading and a
structural one part company only in the second, which nothing this repo ships produces.

**Why it was left, and what the reading adds to that.** Reading it structurally means naming the
budget flag and distinguishing a zero budget from a bounded one (`--reasoning-budget 128` is still
thinking), which is the flag-naming the harness keeps to one place. The zero column above adds a
second reason to be careful: a cortex tier at zero carries the budget alone, without the
`--chat-template-kwargs` half that the subagent tier's `_REASONING_OFF` pairs with it, and the
ADR-0005 budget-alone addendum measured the budget alone to be one thing on the gemma family and
another on the Qwen one, emptying gemma-4-E4B's channel on 40 draws of 40 while leaving Qwen3.5-2B
deliberating on 40 of 40. Both cortex candidates are in the lineup, one of each family, so a
structural reading of that tail answers what the tier was told and not what the model then does.
What `repeat_of` needs is the former, which is why the reading is still the right one to take.

**What would close it.** `thinking` read off the tier's tail: absent, or present with a count above
zero, is thinking; present at zero is not. The flag has to be found by name rather than by position,
because the budget is no longer the last pair of every tail, and the name is spelled today as
`_REASONING_BUDGET_FLAG` in `brain/packages/inference/tests/test_switch_rows.py`, so the harness
would take that constant over rather than spell it a second time. The test that holds each lineup to its tier would then
hold the two readings to each other.

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which chose
  the nominal reading.
- 2026-09-08: re-read against the tree. The trigger has not fired, both budgets shipping at `-1`;
  the tails at zero and at the default were measured through `ModelHostConfig` and the trigger now
  says how to take that reading. Recorded in the
  [ADR-0004 lineup-trigger addendum](../../adr/ADR-0004-model-lineup.md).
- 2026-09-11: read against the tree and not fired. The prescribed grep names both variables,
  at lines 139 and 160 of `docker/docker-compose.gpu.yml`, and defaults both to `-1`.
  `ModelHostConfig().tiers()` under `brain/.venv` rendered the table above cell for cell: `()`
  for the cortex and brain tails at the default, `('--reasoning-budget', '0')` for both with the
  budgets at zero, the reasoning-off pair for the subagent tier in both columns, and a budget
  of `128` rendering `('--reasoning-budget', '128')`. `Model.thinking` is still
  `self.tier != SUBAGENT_TIER`, at line 212 of the harness. One reading the table leaves out:
  at the shipped default the config declares one tier, the cortex, because the brain and
  subagent tiers are opt-in behind an empty file name, so the second and third rows are read
  with `CORTEX_MODEL_FILE_BRAIN` and `CORTEX_MODEL_FILE_SUBAGENT_GPU` set.
- 2026-09-17: read against the tree and not fired. The prescribed grep still names both variables
  at lines 139 and 160 of `docker/docker-compose.gpu.yml`, both defaulting to `-1`, and no other
  compose file, `.env` or script outside the tests sets either. `Model.thinking` is still
  `self.tier != SUBAGENT_TIER`, now at line 215 of the harness. The table above was stale:
  `ModelHostConfig().tiers()` under `brain/.venv`, with the brain and subagent files set, now
  renders a `--cache-ram` pair in every tail (8192 for the cortex, 0 for the other two), which the
  prompt-cache change of 2026-09-13 added, so the cortex and brain tails at the default are that
  pair and not empty. A budget of `128` still renders `('--reasoning-budget', '128')` after it.
  The remedy is corrected to find the flag by name, and to reuse the one spelling of it the
  switch-rows test now keeps.
