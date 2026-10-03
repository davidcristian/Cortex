# Per-task caller-supplied schema

**Status:** open, waiting for a consumer
**Area:** untrusted-content
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Trigger:** a task file or ADR proposes a subagent result the cortex reads as fields. None does: `SubagentResult.output` is one `str`, and `grep -rli 'structured result' docs/refinements/tasks` finds only this file.
**Verified:** 2026-10-03

Left behind by [R-068](068-grammar-constrained-subagent-output.md): letting the caller supply a
schema per task instead of the fixed `{"reply": <string>}` envelope. ADR-0028 decision 2 rejects it
for now: a schema the cortex writes is one an injected instruction could shape, and the field names
in a schema never reach the model on this engine, so a richer one would constrain the output and
explain nothing.

A caller has no slot to state a result shape in. A spawn item has `instruction`, `context`, `model`
when the spawn is tool-less and the roster has more than one entry, and `role` when roles are
configured ([spawn_spec.py:79](../../../brain/packages/core/src/cortex_core/spawn_spec.py)). A role
has a description and one sentence and no schema
([roles.py:8](../../../brain/packages/core/src/cortex_core/roles.py)). The attempt sends
`REPLY_ENVELOPE` or no schema
([subagent_attempt.py:120](../../../brain/packages/core/src/cortex_core/subagent_attempt.py)), and
the result hands the turn one string
([subagents.py:61](../../../brain/packages/core/src/cortex_core/subagents.py)).

## History

- 2026-09-13: Checked, and the trigger has not fired. There is no structured subagent-result
  feature to revisit this for: the spawn tool advertises `instruction`, `context` and, where the
  roster offers a choice, `model`
  ([spawn_spec.py](../../../brain/packages/core/src/cortex_core/spawn_spec.py)), with no slot in
  which a caller could state a result shape, and the attempt sends the fixed `REPLY_ENVELOPE` or
  no schema at all
  ([subagent_attempt.py](../../../brain/packages/core/src/cortex_core/subagent_attempt.py)). The
  origin's answer-rate measurement has since given the rejection a second reason: the field names
  in a schema never reach the model on this engine, so a richer per-task schema would constrain
  the output and explain nothing.
- 2026-09-19: Checked again, and the trigger has not fired. `build_spawn_spec` in `spawn_spec.py`
  still gives each subtask item `instruction` and `context`, and `model` only when the spawn is
  tool-less and the roster has more than one entry, so a caller still has no slot for a result
  shape; `subagent_attempt.py` still sets `REPLY_ENVELOPE` or no schema. Neither file has changed
  since 2026-09-13, and no structured subagent-result feature has been proposed.
- 2026-09-28: Checked against subagent roles
  ([ADR-0072](../../adr/ADR-0072-subagent-roles.md)), the nearest thing to a result feature so far,
  and the trigger has not fired. A spawn item may now name a `role`, whose one sentence the runner
  appends to the instruction, but a role holds no schema and decision 5 declines an output contract
  the runner checks, naming this entry as what that waits for. `subagent_attempt.py` still sends
  `REPLY_ENVELOPE` or no schema.
- 2026-10-03: Checked again, and the trigger has not fired. `SubagentResult` still has
  `task_id`, `output: str`, `ok`, `detail` and `tainted`, the spawn item still has no slot for a
  result shape, `SubagentRole` still has only `description` and `instruction`, and
  `subagent_attempt.py:120` still sets `REPLY_ENVELOPE` or nothing. The trigger now names the field
  and the search that decide it, and the body states the current code.
