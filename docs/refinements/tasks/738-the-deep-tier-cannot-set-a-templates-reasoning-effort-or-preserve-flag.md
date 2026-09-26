# The deep tier cannot set a template's reasoning effort or preserve flag

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a Qwen3.8 artifact named in `CORTEX_MODEL_FILE_BRAIN` by a compose default, a recipe
or an env file in this tree, ADR-0004 naming for the cortex or the deep tier a pick or alternate
whose template reads the effort (the effort table of the thinking-switch readings), or the
maintainer's pick of step two's names written in this task's History. Read it with
`grep -rn 'CORTEX_MODEL_FILE_BRAIN' docker/ justfile` and decision 8's first sentence.
**Verified:** 2026-09-26

The Qwen3.8 chat template reads two settings the deep tier cannot send. With thinking on,
`reasoning_effort` takes `xhigh` (the value when nothing or an empty string is sent), `high`, which
it renders as `xhigh`, `medium` and `low`, and raises on any other value, `Low` included; with
thinking off it ignores the value. `preserve_thinking` is on unless sent off. The deep tier's argv
(`tiers.py`, `config.py` in `cortex_model_manager`) has a setting for neither and `build_payload`
sends neither, so a Qwen3.8 deep tier runs at `xhigh` with preserve on. On the stop row of
2026-09-26 ([deep candidates](../../readings/deep-candidates.md)), Qwen3.8-27B stopped on 10 of 12
draws at `xhigh`, the two misses filling the 8192 context with reasoning and returning nothing, and
on 12 of 12 at `low` and at `medium`. `max` returned HTTP 500 live, the template raising, and
`minimal` raises the same way in an offline render.

## What the lineup offers

Every chat template on the models mount was rendered under both settings on 2026-09-26; the table,
the engine's handling and the method are in the
[thinking-switch readings](../../readings/thinking-switch.md#the-effort-and-preserve-settings).

- **gemma-4** (the cortex, deep and subagent picks): no effort setting. Every value, `max` and
  `minimal` included, renders the same prompt as sending no value. Depth is set by the thinking
  switch and the trace budget only.
- **Qwen3.5 and Qwen3.6** (the cortex and deep alternates): the same.
- **Qwen3.8** (both Qwen3.8 deep candidates): the three levels above, and nothing else with
  thinking on. It is the only template whose `chat_template_caps.supports_reasoning_effort` in
  `GET /props` is true, and the caps list no values.

So no shipped pick or alternate has an effort setting, and nothing can be measured per level on the
cortex. Two engine facts decide the design. The request field `reasoning_effort: "none"` turns
thinking off rather than reaching the template, and under `--reasoning on` it does not even do that.
The server flag `--reasoning-effort` passes any value, `none` included, to the template unchecked:
set to `none`, `minimal` or `max` on a Qwen3.8 tier, every thinking-on request that sends no value
of its own raises, while the server starts normally (read from the engine source).

## Proposal

### Step one: a default level for the deep tier

1. **The level is a core type.** `GenerationBounds` gains an optional `effort`, a closed enum of
   three levels in the core's own vocabulary, as `StopReason` is. `None` sends nothing and the
   template's default applies, so a deployment that sets nothing sends byte for byte today's
   request. The `InferenceBackend` signature does not change.
2. **The deep tier's default is a brain setting.** It takes the level as `low`, `medium` or `high`,
   the words the adapter sends, is validated at wiring so a typo fails the brain's start and not
   every handoff, and `engines.py` puts it on the deep phase's bounds in the `replace` that builds
   the phase. The cortex gets no setting, since neither cortex candidate's template reads the
   effort. The name is the maintainer's; `CORTEX_REPLY_EFFORT_BRAIN` is the parallel of the reply
   settings the phase inherits today (ADR-0049 decision 6).
3. **The adapter maps and checks.** `build_payload` sends a level as the request field
   `reasoning_effort`, from one table in `cortex_inference`: `low`, `medium`, `high`. Qwen3.8
   renders `high` byte for byte as `xhigh`. The table never holds `none` or the values Qwen3.8
   raises on. Inside the model lease, before the completion, the adapter sends `GET /props` to the
   leased server: with `supports_reasoning_effort` false, the request goes without the field and one
   warning per model says the level has no setting there; with it true, one `POST /apply-template`
   renders the level, and HTTP 500 drops the field with a warning. Nothing is cached, for the reason
   in [ADR-0071](../../adr/ADR-0071-leading-system-messages.md) decision 3, so an engine bump or a
   new model file needs no reading taken again. A level never becomes a trace budget in this step.
4. **It holds no state.** The level is configuration read at wiring and written on every deep
   request. No model server holds it, and a request field overrides any server default, so a
   swapped or restarted server gets the same level on its next request. The `HandoffRecord` gains
   no field: a resumed handoff builds its bounds from the same configuration.
5. **Rejected: the model host's `--reasoning-effort`**, this entry's first remedy. It passes the
   engine's words unchecked, a value the template raises on fails every deep reply while the tier
   reports ready, and `ModelHostConfig` never reads a template, so a check against the template's
   values could run only at tier readiness, once per start.
6. **The default for a Qwen3.8 deep tier: `medium`, recommended.** At 8192 it stopped on 12 of 12
   where `xhigh` stopped on 10, at a median wall of 0.97 of the pick's (`low` 0.78), and was right
   by hand on 11 (`low` 10). No stop count reads apart from another's, and `low` did not shorten
   Q2's reasoning, so the choice between `low` and `medium` rests on the hand reading, which
   decides nothing on its own; the maintainer decides it with the pick.
7. **What it touches.** Ports: `GenerationBounds`, and the stream contract gains a check that a
   request naming a level is answered whatever the served template reads, added to
   [ADR-0068](../../adr/ADR-0068-port-contract-lists.md) decision 8's list; the check, the fake and
   the adapter come in that order. Settings: the brain service in `docker/docker-compose.yml` names
   the setting as a bare key, which `settingscheck` requires; a bare key writes no default, so
   `defaultcheck` has nothing to compare. `flagcheck` gains nothing: no subagent server gets a
   flag, and the subagent tier runs thinking off, where Qwen3.8 ignores the level. The injection
   harness builds its own requests, so a deep row at the chosen level sends it too.
   Records edited: [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md) (a third
   control beside the switch and the budget; decision 6's inheritance), ADR-0068 decision 8, and
   ADR-0004 decision 8 when a Qwen3.8 deep tier ships; the brain-core, brain-inference and
   brain-orchestrator module docs and the GPU runbook.

**The preserve flag stays out of step one.** The brain stores no reasoning, so with preserve on
every earlier reply renders behind an empty thought. If a multi-turn row shows that matters, the
deep tier's argv takes `--no-reasoning-preserve`, a switch with no value to raise on. It changes
nothing on a template whose preserve default is already off, and on one without the variable the
engine logs a warning at start.

### Step two, optional: one user preference

1. **One choice, applied to every turn**, written with `SetPreference` like the Face tab's rows and
   read by the brain from the record at each turn and again by the deep phase after a swap, so it
   needs no `HandoffRecord` field. A set level wins over the tier's default; a cleared key leaves
   the default ([ADR-0032](../../adr/ADR-0032-preference-record.md) decision 3). The brain reading
   this one key changes ADR-0032 decision 1, under which it stores values and never parses them,
   and the `PreferenceStore`, wired today into the RPC ports only, reaches the turn.
2. **Hidden where the serving model has no setting.** No RPC sends a structured capability to the
   body (`Health` returns sentences), so hiding the row is a proto change. The cortex's answer is
   live, from `GET /props`; the deep tier's server exists only during a handoff, so its answer is
   the one the last handoff recorded, tied to the model host's boot id, since the roster is fixed
   for a boot. On every shipped pick the answer is no, so on a default deployment the row stays
   hidden unless a level also becomes a trace budget where the template has no effort setting.
   Whether it should is open: the budget ends a gemma trace, but what that costs an answer is
   [R-296](296-trace-budget-quality-floor.md), and the budget alone measured no effect on a
   Qwen3.5 request whose template opens the thought in the prompt.
3. **Where it lives.** The Face tab holds only how the overlay looks, each row with a preview, so
   the row needs a third console tab, whose name joins the Face and Chords family
   ([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 1).
4. **Why not per message.** A control beside the composer would ask before each turn how hard to
   think. The deep handoff's confirm card ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision
   1) already asks, mid-turn, whether to hand the turn to the deep model, the lineup's main way to
   reason more on a task, and ADR-0030 rejected a user-only trigger because the need for depth shows
   only mid-turn. A per-message level would be a second answer for one turn that could contradict
   the first, such as the lowest level on a turn the user then escalates. A per-turn choice, if ever
   wanted, belongs on the card. On today's cortex it would change nothing.

**Naming, awaiting the maintainer's pick.** One family of three, ordered from least to most
reasoning. Recommended: **Wade, Swim, Dive**, named for how far into the water one goes, stored as
`wade`, `swim` and `dive`. The overlay's surfaces are water already (the bubble mark, the liquid
edge, the whisper's mist), and the window's Still to Trance is ordered by depth too, the depth of
sleep, with no word shared; Dive and not Deep, because deep names the tier. Alternatives: **Stroll,
Hike, Trek** (`stroll`, `hike`, `trek`), by distance and effort, with a weaker tie to the other
families; and **Presto, Andante, Largo** (`presto`, `andante`, `largo`), tempo markings from fast to
slow, the musical vocabulary the Chords tab's name comes from, though a reader may not know Andante
and the most thought gets the slowest word. The record key is `reply.effort` (recommended, the
engine's own term and a sibling of `CORTEX_REPLY_*`) or `reply.depth`, never `overlay.`, which marks
values the brain never parses. The three stored values map in order to the core's levels and so to
`low`, `medium` and `high`. There is no fourth level for thinking off: that is the switch,
`CORTEX_REPLY_THINKING`, and thinking on is what the deep pick was chosen for. The row returns to
the tier's default by clearing the key, as the Light row's Auto does. Before this entry, none of the
nine words and neither key appeared in the tree or its history. Once picked, the family joins the
product-name exemption in AGENTS.md, which is at its 250 lines, and the stored values, written in
both the overlay's TypeScript and the brain's Python, get a `wirecouplings` entry in `crosscheck`'s
registry.

## What each step needs measured first

- **Step one:** nothing more to recommend `medium` at 8192. Before a Qwen3.8 deep tier ships, the
  injection row at the chosen level (ADR-0004's consequences; the row of 2026-09-26 ran at
  `xhigh`), and the stop row again if
  [R-736](736-the-deep-phase-sends-a-history-window-sized-for-the-cortexs-context.md) moves the deep
  tier off 8192, since the case against `xhigh` is the 2 draws of 12 that filled that context. The
  preserve half needs a multi-turn row with preserve on and off.
- **Step two:** the maintainer's pick of the names and the tab. On the cortex there are no levels to
  measure; if a level becomes a trace budget, each level's budget needs a graded row (R-296), beside
  the latencies at 512 and 128 that `config.py` records for the cortex pick.

**What closes it.** Done when step one is built behind the trigger, with the injection row drawn at
the chosen level and the records above edited, and step two with it when its names, its tab and the
trace budget question were decided first; otherwise step two, if the maintainer wants it, is filed
at that close as its own task. Declined if ADR-0004 drops both Qwen3.8 candidates from the deep set
and the maintainer declines step two. Until the trigger fires the status stays waiting: on every
shipped pick and alternate, step one would change no prompt, a setting for a case no deployment has
reached, which ADR-0049 already declined once for the deep tier's reply count.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-26: the proposal written, on renders of every template on the mount (thinking-switch
  readings): only Qwen3.8 reads the effort, so the cortex has no levels to measure. The remedy of a
  model-host flag was replaced by a core level the adapter checks per request, the trigger widened
  to any tier whose template reads the effort and to the maintainer's name pick, and the raise
  corrected to thinking on only. Status unchanged, since step one changes no prompt on a shipped
  pick.
