# Subagents

Deferred refinements from the subagent runner of Slice 7 and its heterogeneous roster of
Slice 8.6, recorded at [ADR-0010](../adr/ADR-0010-subagents.md) and
[ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries
are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** subagent progress reporting, per-role escape hatch. The spawn-spec tuning for
spontaneous model picks and the measured trade-off advertisement landed together on 2026-07-16
(one prose change, annotated in place below); a fix-when-it-bites residual on the nudge's live
uptake is recorded at the end.

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
  **Advanced 2026-07-16 by the trade-off change below:** the new parallelism line is also the
  spontaneous-pick nudge finding 1 wanted, giving the model knob a concrete reason (a wall-clock
  win from spreading independent subtasks across distinct models) to reach for beyond a directed
  pick. The *uptake* by a live cortex is unverified here (gemma-12B does not fit the 8 GB dev
  GPU), so it is recorded as a fix-when-it-bites residual below rather than proven closed.

**Heterogeneous subagents in Slice 8.6 ([ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md)):**
- **Measured trade-off advertisement.** Roster descriptions are config-authored text
  (`description` per entry, `CORTEX_SUBAGENTS_MODEL_DESCRIPTION` for the default); deriving or
  cross-checking them from measured latency/robustness numbers is a later refinement behind the
  same spec-building seam. Wrong text misleads only the optimization. Safety is deterministic.
  **Landed 2026-07-16: the advertisement now states the measured trade-off, not a blanket
  parallel claim** ([ADR-0018 addendum](../adr/ADR-0018-heterogeneous-subagents.md)). The entry
  read the "measurement" as *deriving the config description strings from numbers*; that half is
  still declined and stays config-authored, because those strings are deployment-specific and
  safety is deterministic regardless. What was measurable and worth advertising was the
  *structural* trade-off the spec asserted independently of config: `spawn.py`'s description told
  the cortex subagents "run concurrently" and delegation was "worth parallelizing", a blanket
  parallel claim. The measured reality (ADR-0012 admission-wall addendum, live on the Qwen-2B CPU
  override: two same-model spawns 10.0 s vs two across two backends 4.8 s, ratio 2.08) is that
  each roster entry holds one backend whose `SingleResidentModelManager` lease is held for the
  whole stream, so same-model subtasks serialize and only distinct-model subtasks overlap. The
  base description dropped the blanket claim, the choice note now points the cortex at
  distinct-model spread as the wall-clock lever, and the pinned/single-entry note says a batch
  groups independent work rather than speeding it up. Measurement reused from the same-day
  admission-wall work, cited as prior; the mechanism (`asyncio.Lock` per entry, held for the
  stream) is confirmed in `model.py`.
- **Spontaneous model picks.** See the richer-spawn-schema entry above (ADR-0018 addendum
  finding 1): further nudging beyond the inline example, if the cortex should reach for cheap
  models unprompted.
  **Landed 2026-07-16 as the same prose change** (annotated at the richer-spawn-schema entry):
  the added parallelism line is the nudge. Whether a live cortex now reaches for distinct models
  unprompted is the residual below.

**Fix when it bites ([ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md)):**
- **The spontaneous-pick nudge's live uptake.** The measured trade-off line gives the cortex a
  concrete wall-clock reason to spread independent subtasks across distinct roster models, but its
  uptake cannot be validated on the 8 GB dev GPU (gemma-12B, the cortex tier, does not fit; the
  spawn tool is cortex-only, and the small subagents do not respect prompt framing the way the
  cortex does, so a subagent-tier proxy would not test it). The trigger is a live cortex on
  user-tier hardware still folding cheap-model picks into instruction text or piling same-model
  batches for latency; the fix is stronger nudging behind the same spec seam (a worked example, a
  sharper phrasing), never a schema change.
- **The per-role escape hatch.** A future subagent role needing a cheap model on a
  tainted/tool path for a proven-safe reason would be a per-role override on the same roster
  seam, never a relaxation of the forced-robust default (ADR-0017 risks, ADR-0018 risks).
  Unimplemented by design; no role justifies it today.
