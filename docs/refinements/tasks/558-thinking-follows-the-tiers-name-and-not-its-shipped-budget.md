# Thinking follows the tier's name and not its shipped budget

**Status:** open, waiting for its trigger
**Area:** inference
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)
**Trigger:** a deployment that starts the cortex or the deep tier with `CORTEX_REASONING_BUDGET` or
`CORTEX_REASONING_BUDGET_BRAIN` at anything other than `-1` and wants the injection harness to draw
that tier's rows as it runs them. Read it with
`grep -n 'CORTEX_REASONING_BUDGET' docker/docker-compose.gpu.yml`, which names both variables and
defaults both to `-1` today, and confirm what a tier's flag tail then has with
`ModelHostConfig(...).tiers()`.
**Verified:** 2026-09-17

`Model.thinking` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
is `tier != SUBAGENT_TIER`: the subagent tier is the thinking-off tier because ADR-0010 made it one,
and the cortex and deep tiers think because they ship with the unbounded budget. That reads the
tier's name. The same `ModelHostConfig` the harness reads the head off answers the question
structurally, in whether the tier's `extra` ends its trace at zero, and the harness does not read it
there.

Measured 2026-09-08 and read again 2026-09-17: the two readings still agree everywhere the stack
runs. Both variables default to `-1` in `docker/docker-compose.gpu.yml`, and
`_UNRESTRICTED_REASONING` in `brain/packages/model_manager/src/cortex_model_manager/config.py` emits
no flag at that value. Since 2026-09-13 every tail also has the tier's host-RAM prompt cache, so the
tails read:

| tier | `extra` at the shipped default | `extra` with both budgets at zero |
| --- | --- | --- |
| cortex | `('--cache-ram', '8192')` | `('--cache-ram', '8192', '--reasoning-budget', '0')` |
| brain | `('--cache-ram', '0')` | `('--cache-ram', '0', '--reasoning-budget', '0')` |
| subagent-gpu | the reasoning-off pair, then `('--cache-ram', '0')` | the same |

`Model.thinking` reads `True` for the first two rows of either column, so the two readings differ
only in the second column, which nothing this repo ships produces.

Reading it structurally means naming the budget flag and telling a zero budget from a bounded one
(`--reasoning-budget 128` is still thinking), which is the flag naming the harness keeps to one
place. The zero column adds a second reason for care: a cortex tier at zero has the budget alone,
without the `--chat-template-kwargs` half that the subagent tier's `_REASONING_OFF` pairs with it,
and ADR-0049 measured the budget alone to do one thing on the gemma family and another on the Qwen
one, emptying gemma-4-E4B's channel on 40 draws of 40 while leaving Qwen3.5-2B deliberating on 40 of
40. Both cortex candidates are in the lineup, one of each family, so a structural reading of that
tail answers what the tier was told and not what the model then does, which is what `repeat_of`
needs.

Closing it means reading `thinking` off the tier's tail: absent, or present with a count above zero,
is thinking; present at zero is not. The flag has to be found by name rather than by position,
because the budget is no longer the last pair of every tail, and the name is written today as
`_REASONING_BUDGET_FLAG` in `brain/packages/inference/tests/test_switch_rows.py`, so the harness
would import that constant rather than write it a second time.

## History

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which chose to
  read the tier's name.
- 2026-09-08: read again against the tree. The trigger has not fired, both budgets shipping at `-1`;
  the tails at zero and at the default were measured through `ModelHostConfig` and the trigger now
  says how to take that reading. Recorded in the lineup-trigger reading of 2026-09-08
  ([ADR-0004](../../adr/ADR-0004-model-lineup.md)).
- 2026-09-11: read against the tree and not fired. The grep names both variables at lines 139 and
  160 of `docker/docker-compose.gpu.yml` and defaults both to `-1`. `ModelHostConfig().tiers()`
  under `brain/.venv` produced the table above cell for cell. `Model.thinking` is still
  `self.tier != SUBAGENT_TIER`, at line 212 of the harness. One thing the table leaves out: at the
  shipped default the config declares one tier, the cortex, because the brain and subagent tiers are
  opt-in behind an empty file name, so the second and third rows are read with
  `CORTEX_MODEL_FILE_BRAIN` and `CORTEX_MODEL_FILE_SUBAGENT_GPU` set.
- 2026-09-17: read against the tree and not fired. The grep still names both variables at the same
  lines, both defaulting to `-1`, and no other compose file, `.env` or script outside the tests sets
  either. `Model.thinking` is still `self.tier != SUBAGENT_TIER`, now at line 215. The table was
  stale: every tail now has a `--cache-ram` pair (8192 for the cortex, 0 for the other two), added
  by the prompt-cache change of 2026-09-13, so the cortex and brain tails at the default are that
  pair and not empty. A budget of `128` still produces `('--reasoning-budget', '128')` after it. The
  proposed fix is corrected to find the flag by name and to reuse the one copy of it the switch-rows
  test keeps.
