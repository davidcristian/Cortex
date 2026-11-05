# A deep phase refuses again a monthly retry the cortex was refused

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

The `YEARLY_DATE` refusal refuses a `schedule_task` call with `on_month_days` once per set of
month days, and a retry on the same days runs. The refused calls live in
`LoopRecord.yearly_refused` (`dispatch_round.py`), which `stream_tool_loop` creates empty for each
loop. The handoff record keeps `forget_refused`, `sidecar_refused` and `monthly_stored`, but not
these calls, so when the cortex was refused and hands off, the deep phase refuses the deep model's
retry on the same days a second time; only a third call runs. The deep model reads two refusals
for one request, and a real monthly request costs one more deep round.

Reproduction: a test that runs `stream_tool_loop` with the person's birthday message as `query`,
`working` holding the user message, an assistant message with the call
`on_month_days` [11] (id `c1`) and a tool message `YEARLY_DATE_MSG` for `c1` (the shape of the
deep phase's `deep_tail`), and a backend whose one call is `on_month_days` [11]. On `bc2e45d3b`
the handler ran nothing and the audit record was the refusal.

## What to do

1. Read the refused calls from the record's `loop_tail` the way `declined_calls` in
   `handoff_view.py` reads denied ones: a tool message starting with `YEARLY_DATE_MSG` names its
   call by id.
2. Pass them through `ToolLoopContext` into the deep phase's `LoopRecord`, with a test that the
   retry above runs and a test that a call on other days is still refused.

## History

- 2026-11-05: filed from the second audit of the yearly date refusal.
