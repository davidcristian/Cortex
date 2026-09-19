# Cross-loop salience across a batch

**Status:** open, waiting for its trigger
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19
**Trigger:** the tool audit trail shows two subagent tasks of one turn (one `turn_id`, two `task_id`
values) dispatching the same tool with the same arguments.

Recorded inside [R-039](039-salience-on-the-tool-loop.md) as one of the things left behind it:
salience across the loops of a batch of subagents given one instruction, which would need a
different justification from the per-loop policy's.

That policy is per loop rather than per turn, and deliberately: the dispatch pool bounds reach,
which is a resource the turn's subagents share, while a repeat is redundant only against the
`working` messages holding its answer, which a sibling cannot see.

The code says the same in two places. `RepeatSalience` in
`brain/packages/core/src/cortex_core/tool_salience.py` reads nothing but the calls it is handed,
and the list it is handed is `dispatched`, a local of `stream_tool_loop` in `tool_loop.py`. A
spawned subagent runs its own loop over its own list, so it can see neither its parent's calls nor
a sibling's, which is what makes a batch given one instruction dispatch that instruction's calls
once per member.

## History

- 2026-08-09: A review of deferred triggers ran against the tree and none fired. Everything left
  open there needs live observation, its trigger being a deployment doing something rather than a
  file saying something.
- 2026-09-09: Claims checked against the code and one sentence repaired: the entry opened by
  saying it had no bullet of its own, which described the per-area layout the backlog left behind
  when it became one file per task. The mechanism is unchanged and the trigger has not fired. The
  one full batch of eight this repo has measured was given eight distinct subtasks over their own
  material on purpose, so that no two prompts shared a slot's prompt cache, which is the opposite
  of a batch given one instruction.
- 2026-09-13: Checked again and left open. `RepeatSalience` still reads nothing but the calls it
  is handed, its port declaring `admits(call, dispatched)` and nothing else, and `dispatched` is
  still a local of `stream_tool_loop`, declared at `tool_loop.py:126` and passed into `run_round`
  on each round. Nothing joins that list across the loops of one batch.
- 2026-09-19: Checked again, trigger repaired, left open. `SaliencePolicy.admits(call,
  dispatched)` still reads nothing else, and `dispatched` is still the local at `tool_loop.py:126`
  handed to `run_round` each round. The trigger read "a batch of subagents handed one
  instruction", which named no observation: `SpawnSubagentsTool` accepts a batch whose items
  repeat one instruction today, so the clause was true of the code the day it was written, while
  the cost this entry is about is the repeated call, which a shared instruction over different
  material does not produce. It now names that call as the audit trail records it. Each
  `cortex.tools.audit` line has `tool`, `arguments`, `turn_id` and `task_id`, and the audit trail
  can be written to the file `CORTEX_TOOLS_AUDIT_FILE` names, so the question is one query over
  that file. Nothing in the tree records such a pair.
