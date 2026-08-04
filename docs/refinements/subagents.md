# Subagents

Deferred refinements from the subagent runner of Slice 7 and its heterogeneous roster of
Slice 8.6, recorded at [ADR-0010](../adr/ADR-0010-subagents.md) and
[ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries
are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** the per-role escape hatch (on the dead-until-a-consumer list) and the
spontaneous-pick nudge's live uptake (fix when it bites, recorded at the end, and **observed live
on 2026-08-04** without closing: the run found the probe's own premise false, so the entry stays
open with a sharper trigger). Subagent progress
reporting **landed 2026-07-16** as one side channel with the tool-step chip surfacing entry from
[email-confirmer.md](email-confirmer.md) (annotated in place below). The spawn-spec tuning for
spontaneous model picks and the measured trade-off advertisement landed together on 2026-07-16
(one prose change, annotated in place below).

**Count corrected 2026-07-19, from 1 to 2.** The nudge residual was named here from the day it
opened but never counted, so the index read this area at 1 while the doc held two open things. The
arithmetic that dropped it is visible in the index's own narrative: two entries closed on
2026-07-16 and one opened behind them, so the count should have moved 4 to 3 and then 3 to 2, not
4 to 2 and then 2 to 1. Every other area counts its fix-when-it-bites entries as open (repo gates
counts three, memory counts its ANN index and recall observability, resource governance counts
five), so this was a slip rather than a convention, and a count that does not move for a still-open
deferral is the same way an open item gets lost as a count moved for a half-closed one.

**Subagents in Slice 7 ([ADR-0010](../adr/ADR-0010-subagents.md)):**
- **Subagent progress reporting over the `Converse` status stream.** v1 delegation is synchronous
  within the cortex turn; surfacing per-subagent progress to the overlay is a later refinement. See
  ADR-0010 risks. **Cost correction:** this is not a progress-sink parameter. While a spawn runs,
  the engine generator is suspended inside `await dispatcher.dispatch(...)` in `tool_loop.py`, so
  it cannot yield an event; progress needs a side channel writing to the `Converse` queue directly.
  And `SpawnSubagentsTool` is built **once** in `subagent_builders.py` and shared by every turn, so
  it must become per-stream (or carry the stream's channel per call) before it can address one
  turn's overlay.
  **Landed 2026-07-16 ([ADR-0010 progress addendum](../adr/ADR-0010-subagents.md)), as the
  carry-the-channel-per-call option.** Both halves of the cost correction were confirmed against
  the code before building: the suspended generator (the spawn `dispatch` is awaited in
  `tool_loop.py`, so `handle_turn` cannot yield while subagents run) and the shared singleton
  (`build_subagents` runs once in `wiring.run_from_env` and its `spawn_tool` goes into `builtins`,
  built once and reused by every per-stream `make_engine`). A new pure-core `ProgressSink` port
  (`progress.py`, port-free so `tools.py` may depend on it) rides the dispatch `TurnStamp` beside
  `budget` (a live handle, `compare=False`), so the one shared `SpawnSubagentsTool` reads the
  stream's sink off `call.stamp.progress` per call and holds no per-stream state to leak, which is
  the "carry the channel per call" alternative the entry named (a per-stream tool was the other).
  It serves **both** this entry and the tool-step surfacing entry: `SpawnSubagentsTool` emits a
  `StatusUpdate(state="delegating", "delegating N subtasks")` for the batch's scale and the
  `SubagentRunner` maps each subagent's `ToolStep` onto the sink as a registry-authored
  `ToolActivity`. The real adapter `SeamProgressSink` puts onto the stream's own output queue
  **credit-balanced** (takes a credit only when free, drops otherwise), not the confirmer's
  over-crediting control path, since a delegating turn emits many steps; ordering is preserved
  because the turn task is suspended in `dispatch` and puts nothing itself meanwhile. Nothing model-
  or untrusted-authored ever rides the sink (only the count and the matched `ToolSpec`'s fields),
  so a tainted subagent's progress needs no guardrail pass, the `ToolActivity` argument reused. **No
  proto change**: the overlay already renders `ToolActivity`/`StatusUpdate`, so the wire and the
  overlay reducer were untouched. The parallelism claim was avoided in the wording ("delegating",
  not "running in parallel"), honest to the measured same-model serialization (ADR-0012).
- **Richer `spawn_subagents` object schema landed 2026-07-03 with Slice 8.6 (ADR-0018).**
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
  concrete wall-clock reason to spread independent subtasks across distinct roster models, and
  whether it takes that reason unprompted is unmeasured. A subagent-tier proxy would not test it
  (the spawn tool is cortex-only, and the small subagents do not respect prompt framing the way the
  cortex does), so the probe needs a live cortex. **Corrected 2026-07-19: that is agent-runnable
  here, and this entry said it was not.** It read "cannot be validated on the 8 GB dev GPU
  (gemma-12B, the cortex tier, does not fit)";
  [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) had already run the real cortex on that card
  at `-ngl 99 --ctx-size 4096 --parallel 1`, beside its vision projector, which is the heavier case.
  The roster is CPU-placed by default, so it contends for no VRAM. The probe is a resident cortex at
  4K with the roster up and a prose-only ask carrying independent subtasks, and it is listed as
  actionable now in [index.md](index.md); what stays host-side is the same question at the
  production 16K context with more than one slot. The trigger is a live cortex still folding
  cheap-model picks into instruction text or piling same-model batches for latency; the fix is
  stronger nudging behind the same spec seam (a worked example, a sharper phrasing), never a schema
  change.
  **Observed 2026-08-04, and the entry stays open**
  ([ADR-0018 addendum](../adr/ADR-0018-heterogeneous-subagents.md) of that date). The probe ran on
  the 24 GB card at the **production 16K context** with a single slot, not the 4K proposed above,
  cortex resident (9676 MiB of `nvidia-smi` total used against 1893 MiB idle) and both CPU roster
  servers up, driving the real tool loop over the real builders' dispatcher with `spawn_subagents`
  as the only advertised tool. It found three things and none of them is the yes or no this entry
  expected. **The probe as specified cannot answer the question**, because a prose-only ask does
  not produce a batch: 20 turns over four asks carrying three or four independent subtasks each
  emitted **zero** spawn calls, and `subagent`, `delegat`, `spawn` and `farm` appear zero times in
  the twelve full reasoning traces, so delegation was never declined, it was never raised. That is
  also the right call on this deployment, where the CPU tiers run at 0.35 tok/s (the E4B default)
  and about 1 tok/s (the Qwen alternate), so a delegated paragraph costs minutes the cortex spends
  in seconds. **Invited to delegate in ordinary prose** (no tool name, no model name, no
  parallelism language) it delegates every time and piles the whole batch on ONE entry every time:
  16 turns, 16 delegations, 0 spreads, with exactly one of the 15 batches whose arguments were
  recorded carrying a `model` key at all, and that one putting all three subtasks on `qwen` (the
  sixteenth turn was abandoned while its batch ran, and the alternate's server served nothing
  during it, so it too was a pile on the default). And **the nudge is only
  advertised where it matters least:** `build_spawn_spec` publishes the knob and the spread
  sentence only when `not tools_enabled and len(roster.entries) > 1`, while `build_subagent_tools`
  makes subagents tools-enabled whenever any tool registry is configured, so every tools-enabled
  deployment gets the pinned note instead (built both ways off the live roster to confirm). One
  correction to the advertised sentence came out of the same run: an entry holds one backend per
  placement *target*, and with `gpu_endpoint` falling back to `endpoint` both targets dial one
  server, so a same-entry batch whose ask fits the VRAM headroom once overlaps two ways rather than
  serializing (measured on `qwen`: two subtasks launched in the same millisecond, the third when
  the first released; the default entry, whose ask never fits, was strictly serial at 258.4 s,
  208.7 s and 330.2 s). It is folded in here rather than opened as its own entry because it is the
  same sentence, the same seam and the same fix, and because it makes the prize for spreading
  smaller rather than opening new work. **The trigger sharpens accordingly.** Piling is now
  measured, so the old wording would read as fired, but nothing is being paid for it while
  unprompted delegation does not happen at all. What would make it bite is a deployment where the
  cortex reaches for delegation on its own and the batch's wall clock is the user's: a tool-less
  multi-entry roster in real daily use, or roster entries far enough apart that piling is visibly
  slower. The fix is unchanged, and the probe is now cheap to repeat
  (`packages/orchestrator/tests/test_spawn_nudge_live.py`, bring-up in
  [runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md) section 3c).
- **The per-role escape hatch.** A future subagent role needing a cheap model on a
  tainted/tool path for a proven-safe reason would be a per-role override on the same roster
  seam, never a relaxation of the forced-robust default (ADR-0017 risks, ADR-0018 risks).
  Unimplemented by design; no role justifies it today.
