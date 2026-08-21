# A tool call may be bounded above the run that has to contain it

**Status:** open, actionable
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
