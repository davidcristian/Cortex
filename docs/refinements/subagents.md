# Subagents

Deferred refinements from the subagent runner of Slice 7 and its heterogeneous roster of
Slice 8.6, recorded at [ADR-0010](../adr/ADR-0010-subagents.md) and
[ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries
are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** subagent progress reporting, spawn-spec tuning for spontaneous model
picks, measured trade-off advertisement, per-role escape hatch

**Subagents in Slice 7 ([ADR-0010](../adr/ADR-0010-subagents.md)):**
- **Subagent progress reporting over the `Converse` status stream.** v1 delegation is synchronous
  within the cortex turn; surfacing per-subagent progress to the overlay is a later refinement. See
  ADR-0010 risks. **Cost correction:** this is not a progress-sink parameter. While a spawn runs,
  the engine generator is suspended inside `await dispatcher.dispatch(...)` in `tool_loop.py`, so
  it cannot yield an event; progress needs a side channel writing to the `Converse` queue directly.
  And `SpawnSubagentsTool` is built **once** in `subagent_builders.py` and shared by every turn, so
  it must become per-stream (or carry the stream's channel per call) before it can address one
  turn's overlay.
- **Richer `spawn_subagents` object schema landed 2026-07-03 with Slice 8.6 (ADR-0018).**
  An instructions item is now a bare string or `{instruction, model?, context?}`, so per-subtask
  context reaches `SubagentTask.context` and the model choice rides alongside, closing the
  ADR-0010 increment-2 deferral. Remaining nearby: the cortex uses the model knob reliably when
  directed but may not reach for it spontaneously on a prose-only ask (ADR-0018 addendum
  finding 1). Further spec/description tuning is a later refinement behind the same tool.

**Heterogeneous subagents in Slice 8.6 ([ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md)):**
- **Measured trade-off advertisement.** Roster descriptions are config-authored text
  (`description` per entry, `CORTEX_SUBAGENTS_MODEL_DESCRIPTION` for the default); deriving or
  cross-checking them from measured latency/robustness numbers is a later refinement behind the
  same spec-building seam. Wrong text misleads only the optimization. Safety is deterministic.
- **Spontaneous model picks.** See the richer-spawn-schema entry above (ADR-0018 addendum
  finding 1): further nudging beyond the inline example, if the cortex should reach for cheap
  models unprompted.
- **The per-role escape hatch.** A future subagent role needing a cheap model on a
  tainted/tool path for a proven-safe reason would be a per-role override on the same roster
  seam, never a relaxation of the forced-robust default (ADR-0017 risks, ADR-0018 risks).
  Unimplemented by design; no role justifies it today.
