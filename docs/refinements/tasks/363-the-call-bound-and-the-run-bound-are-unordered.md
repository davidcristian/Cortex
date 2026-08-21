# A tool call may be bounded above the run that has to contain it

**Status:** landed 2026-08-21
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

A subagent's whole run is bounded by `CORTEX_SUBAGENTS_RUN_TIMEOUT_S`, and that deadline explicitly
covers the tool dispatches its loop makes between completions, which is why it lives on the runner
rather than on an HTTP client. As of the tool-call bound, one of those dispatches is bounded too,
by `CORTEX_TOOLS_CALL_TIMEOUT_S`. Nothing relates the two numbers.

The shipped pair is ordered correctly by a wide margin (60 s under 2400 s) and nothing enforces
that. A deployment that tightened the run bound, or loosened the call bound, could reach a state
where a single tool call is allowed to outlast the entire run that has to contain it: the run's
deadline fires first, the delegated work is reported truncated, and the reason is a knob two
settings away that nobody would look at. That is precisely the failure the neighbouring bounds on
that tier already refuse to ship: `SubagentsConfig` will not start unless the run timeout sits
strictly above the stall ceiling, because the three bounds there are ordered by the scope of what
they bound, one silent gap inside one whole run inside the queue for a run. The call bound is a
fourth term in that same series, sitting innermost of all, and it is the only one nothing checks.

The fix is the shape `check_control_deadline` already has for the model-host seam and
`SubagentsConfig` has for its own three: a boot-time comparison that refuses rather than a sentence
in a runbook. Where it lives is the one real question, since the two numbers are read by two
different settings classes (`ToolsConfig` and `SubagentsConfig`) and neither can see the other, so
the comparison belongs at the composition root that holds both, which is where the model-host
pairing check ended up for the same reason.

The cortex's own loop is deliberately not part of this: a `Converse` turn has no deadline at all,
so its tool calls have nothing to be ordered against.

## Trail

- 2026-08-21: Filed by the close of
  [341](341-nothing-declines-work-it-cannot-finish.md), which added the innermost of the four
  bounds and left it related to none of the others. Recorded in the ADR-0009 bound addendum.
- 2026-08-21: Landed as a boot-time refusal, `check_tool_call_deadline` in the new
  `cortex_orchestrator/bounds.py`, gating `SubagentsConfig` on its way out of the environment so a
  mispaired deployment is refused before a single adapter is built. A clamp and a logged warning
  were both weighed and rejected, and the measurement that settled it is in the ADR-0009 ordering
  addendum: with the pair inverted, a wedged sidecar does not merely fail late, it costs the whole
  delegated run and is reported as a subtask that would not stop talking. **What the check compares
  is a whole dispatch, not the bound**, because the bound is spent per walk: measured through the
  real composition root, one delegated dispatch reaches `BoundedToolRegistry` twice at one
  configured sidecar and four times at two, the run's own advertisement walk arriving before any of
  it, so `delegated_call_bounds` counts the walks and the check compares the product. A fixed
  factor was rejected, the endpoint count being in the config the check already holds, and
  widening it to a whole run was rejected too, that ceiling being one the shipped pair does not
  clear. Two entries opened,
  [367](367-the-shipped-ordering-of-two-bounds-is-ungated.md) for the repo's own copy of the pair,
  which the constant scan's integer-only ordering cannot hold, and
  [368](368-the-composition-root-has-no-headroom.md) for the composition root reaching its line cap
  exactly, [369](369-the-run-deadline-under-the-queue-is-prose-only.md) for the one relation in
  the same series that is still written only in a runbook, and
  [370](370-an-expiry-reading-is-asserted-exactly.md) for a load-sensitive assertion this task's
  mutation sweep caught reddening once in an unrelated suite.
