# Richer `spawn_subagents` object schema

**Status:** landed 2026-07-03
**Area:** subagents
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

An instructions item is now a bare string or `{instruction, model?, context?}`, so per-subtask
context reaches `SubagentTask.context` and the model choice rides alongside, closing the
ADR-0010 increment-2 deferral. Remaining nearby: the cortex uses the model knob reliably when
directed but may not reach for it spontaneously on a prose-only ask (ADR-0018 addendum
finding 1). Further spec/description tuning is a later refinement behind the same tool.
**Advanced 2026-07-16 by the trade-off change below:** the new parallelism line is also the
spontaneous-pick nudge finding 1 wanted, giving the model knob a concrete reason (a wall-clock
win from spreading independent subtasks across distinct models) to reach for beyond a directed
pick. The *uptake* by a live cortex is unverified: not measured rather than unmeasurable, since
the reason recorded until 2026-07-19 (gemma-12B does not fit the 8 GB dev GPU) is false. It is
recorded as a fix-when-it-bites residual below rather than proven closed, with the probe itself
agent-runnable now.

## Trail

- 2026-07-03: Landed with Slice 8.6
  ([ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)), closing the ADR-0010 increment-2
  deferral.
- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area doc, kept
  verbatim, among the Slice 7 subagent-runner deferrals recorded at ADR-0010.
- 2026-07-16: Advanced by the measured trade-off advertisement's prose change, whose parallelism
  line is the nudge ADR-0018 addendum finding 1 asked for; the live uptake of that nudge was left
  unverified and recorded as a separate fix-when-it-bites residual.
- 2026-07-19: The reason this entry gave for the uptake being unverifiable, that gemma-12B does
  not fit the 8 GB dev GPU, was struck as false, and the probe was found to be agent-runnable.
