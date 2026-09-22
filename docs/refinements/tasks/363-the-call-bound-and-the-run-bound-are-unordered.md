# A tool call may be bounded above the run that has to contain it

**Status:** done 2026-08-21
**Area:** tools-mcp
**Origin:** [ADR-0047](../../adr/ADR-0047-delegated-run-bound-ordering.md)

A subagent's whole run is bounded by `CORTEX_SUBAGENTS_RUN_TIMEOUT_S`, and that deadline covers the
tool dispatches its loop makes between completions, which is why it lives on the runner rather than
on an HTTP client. Since the tool-call bound arrived, one of those dispatches is bounded too, by
`CORTEX_TOOLS_CALL_TIMEOUT_S`. Nothing related the two numbers.

The shipped pair is ordered correctly by a wide margin (60 s under 2400 s) and nothing enforced it.
A deployment that tightened the run bound, or loosened the call bound, could reach a state where a
single tool call is allowed to outlast the entire run that has to contain it: the run's deadline
fires first, the delegated work is reported truncated, and the reason is a setting two steps away
that nobody would look at. `SubagentsConfig` already refuses to start unless the run timeout sits
strictly above the stall ceiling, because the three bounds there are ordered by the scope of what
they bound. The call bound is a fourth term in the same series, innermost of all, and it was the
only one nothing checked.

The fix has the shape `check_control_deadline` already has for the model-host interface: a
boot-time comparison that refuses rather than a sentence in a runbook. Where it lives is the real
question, since the two numbers are read by two settings classes (`ToolsConfig` and
`SubagentsConfig`) and neither can see the other, so the comparison belongs at the composition root
that holds both.

The cortex's own loop is deliberately not part of this: a `Converse` turn has no deadline, so its
tool calls have nothing to be ordered against.

## History

- 2026-08-21: Filed by the close of [341](341-nothing-declines-work-it-cannot-finish.md), which
  added the innermost of the four bounds and left it related to none of the others. Recorded in
  ADR-0009 decision 10.
- 2026-08-21: Built as a boot-time refusal, `check_tool_call_deadline` in the new
  `cortex_orchestrator/bounds.py`, checking `SubagentsConfig` on its way out of the environment so
  a mispaired deployment is refused before a single adapter is built. A clamp and a logged warning
  were both weighed and rejected, and the measurement that settled it is in ADR-0047 decision 3:
  with the pair inverted, a stuck sidecar does not merely fail late, it costs the whole delegated
  run and is reported as a subtask that would not stop talking. What the check compares is a whole
  dispatch, not the bound, because the bound is used per walk: measured through the real
  composition root, one delegated dispatch reaches `BoundedToolRegistry` twice at one configured
  sidecar and four times at two, the run's own advertisement walk arriving before any of it, so
  `delegated_call_bounds` counts the walks and the check compares the product. A fixed factor was
  rejected, the endpoint count being in the config the check already holds, and widening it to a
  whole run was rejected too, that limit being one the shipped pair does not clear. Four entries
  opened: [367](367-the-shipped-ordering-of-two-bounds-is-not-checked-in-the-repo.md) for the repo's own copy of
  the pair, [368](368-the-composition-root-has-no-headroom.md) for the composition root reaching
  its line cap exactly, [369](369-the-run-deadline-under-the-queue-is-prose-only.md) for the one
  relation in the same series still written only in a runbook, and
  [370](370-an-expiry-reading-is-asserted-exactly.md) for a load-sensitive assertion this task's
  mutation run caught failing once in an unrelated suite.
