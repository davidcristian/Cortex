# Richer `spawn_subagents` object schema

**Status:** done 2026-07-03
**Area:** subagents
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

An instructions item may now be a bare string or `{instruction, model?, context?}`, so per-subtask
context reaches `SubagentTask.context` and the model choice travels with it. That closes the
object item form ADR-0010 deferred.

What stayed nearby: the cortex uses the model setting reliably when told to, but may not reach for
it on its own from a prose-only ask (ADR-0018 decision 8). The trade-off change of 2026-07-16
([R-122](122-measured-tradeoff-advertisement.md)) added the parallelism sentence that gives the
model setting a concrete reason to be used, a wall-clock win from spreading independent subtasks
across distinct models. Whether a live cortex takes that hint is
[R-124](124-nudge-live-uptake.md).

## History

- 2026-07-03: Shipped with Slice 8.6
  ([ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)).
- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area, among the
  Slice 7 subagent-runner deferrals recorded at ADR-0010.
- 2026-07-16: Advanced by the measured trade-off advertisement's prose change, and the live uptake
  of that hint was recorded as a separate entry.
- 2026-07-19: The reason this entry gave for that uptake being unverifiable, that gemma-12B does
  not fit the 8 GB dev GPU, was struck as false, and the probe was found to be runnable by the
  agent.
