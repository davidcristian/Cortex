# ADR-0018: Heterogeneous subagent models via the roster, per-spawn choice, and its plumbing

- **Status:** Accepted (Slice 8.6)
- **Date:** 2026-07-03

## Context

Slice 7 delegation runs every subagent on **one** wired model: `spawn_subagents` takes bare
instruction strings, `SubagentRunner` holds a single `SubagentResources`, and the wiring builds
that bundle from the flat `CORTEX_SUBAGENTS_*` env. But the design intent (ROADMAP Slice 8.6) is
that the cortex **chooses the subagent model per spawn and mixes-and-matches** across the
ADR-0004 roster, using a small-fast model for a trivial transform, the robust pick for a harder or
untrusted-content subtask. [ADR-0017](ADR-0017-subagent-model-safety.md) already fixes the safety
boundary: the choice is an optimization *hint, not authority*. Any spawn path that can carry
untrusted content runs the injection-robust default, deterministically.

What ADR-0017 deliberately left open is the mechanics: how the choice is expressed in the tool
schema, how the turn's taint reaches the spawn tool, where the forced-robust rule executes, what
the roster looks like in config and wiring, and what a persisted task must now carry. Those are
this ADR. Two adjacent facts shape it:

- The turn's `TaintLedger` lives in the tool loop; the `ToolRegistry.invoke(call)` port carries
  no taint, so a built-in tool cannot see it today. The dispatcher *does* receive `tainted` per
  call (the ADR-0013 gate).
- A subagent is a stateless function over the `TaskStore` (the one hard rule): whatever the
  runner needs to select resources safely must ride **on the task record**, not in cortex memory.
  Reviewing that store surfaced a latent fail-open gap: `RedisTaskStore` does not round-trip
  `SubagentResult.tainted`, so a result re-read after a restart would silently lose its taint.

## Decision

1. **The spawn schema grows per-item choice, and delivers the deferred `context` field with it.**
   Each `instructions` item is a bare string (as today, the default model and no context) **or** an
   object `{instruction, model?, context?}` (`anyOf` in the advertised JSON Schema). `model` names
   a roster entry (a JSON-Schema `enum` of the advertised names); `context` is the material the
   subagent works from, landing as the task's `context`, closing the ADR-0010 increment-2
   deferral ("the context field joins that schema growth"). Bad items (empty instruction, unknown
   model, non-string context) become an `is_error` result the cortex can correct, never an
   exception (the existing tool contract).

2. **The roster is a pure-core value: `SubagentRoster`.** A new `cortex_core.roster` module holds
   `SubagentResources` (moved verbatim from `runner.py`, as `roster` cannot import `runner` without
   a cycle), `SubagentProfile` (`resources` + an advertised `description` of the entry's
   trade-offs), and `SubagentRoster` (`entries: Mapping[name, SubagentProfile]` + `default:
   name`, validated non-empty with the default present). The default **is** the injection-robust
   ADR-0004 pick by construction (ADR-0017's "config-level logical id").

3. **ADR-0017 executes in the core, at the runner. Parse validates, the runner enforces.**
   `SubagentRoster.resolve(requested, *, tainted, tools_enabled)` returns the entry to run:
   the **default** when `tainted or tools_enabled` (the ADR-0017 disjunction), else the requested
   entry, else `None` for an unknown name (the runner persists an `ok=False` "unknown subagent
   model" result, failing closed, mirroring "task not found"). Enforcing at the runner rather than
   in the spawn tool means a task written to the store by any path still resolves safely, and the
   CI matrix ADR-0017 demands (tainted+weak→robust, clean+tool-less+weak→weak,
   tools-enabled+weak→robust) tests one pure function.

4. **The turn's taint reaches built-in tools as a dispatcher stamp on `ToolCall`.**
   `ToolCall` gains `tainted: bool = False`; `ToolDispatcher.dispatch` stamps it
   (`dataclasses.replace`) with the same per-call `tainted` it already receives for the ADR-0013
   gate, before the registry invoke. Registries pass the call through untouched, so the spawn
   tool reads `call.tainted` with **no `ToolRegistry` port change**. The stamp is provenance the
   loop attaches. The model never sets it, and it is transient: the loop appends the *unstamped*
   calls to the conversation, so nothing new is persisted in session history. This mirrors
   `ToolResult.trust`: provenance rides the value that crosses the seam.

5. **The task record carries what safe resolution needs.** `SubagentTask` gains
   `model: str = ""` (the requested entry, `""` = default) and `tainted: bool = False` (the
   spawning turn's taint at spawn time, from the stamped call). `RedisTaskStore` encodes/decodes
   both strictly (task records are hot, ephemeral, single-deployment, so no legacy decode paths),
   and the same change **fixes the fail-open gap**: `SubagentResult.tainted` now round-trips too,
   so taint survives a restart/swap exactly like the rest of the record (the one hard rule).

6. **Config: the flat fields define the default entry; `CORTEX_SUBAGENTS_ROSTER__<name>` adds
   alternates.** Each roster env value is one JSON object `{endpoint, gpu_endpoint?, vram_gb?,
   cpus?, memory_gb?, description?}` (per-entry `PlacementRequest` numbers defaulting like the
   flat ones; `gpu_endpoint` falls back to the entry's `endpoint`, matching the interim
   one-CPU-executor compose stance). `CORTEX_SUBAGENTS_MODEL` keeps naming the default entry,
   whose resources come from the existing flat fields (`ENDPOINT`, `GPU_ENDPOINT`, `VRAM_GB`, …)
   so today's deployments are a one-entry roster with **zero env changes**, and compose
   overrides stay layerable (an override contributes its `ROSTER__<name>` key without touching
   the base). A roster key colliding with the default name is rejected (one source of truth for
   the default's resources).

7. **One runner, one scheduler, one placer; per-entry backends and request.** The wiring builds
   one `SubagentProfile` per entry, with its own `LlamaCppBackend` pair (GPU/CPU endpoints, one
   `SingleResidentModelManager` each, sharing one HTTP client) and its own `PlacementRequest`,
   while the `ResourceBudgetScheduler` and `VramBudgetPlacer` are shared across entries:
   admission and the VRAM ledger stay **one budget** whatever the mix (ADR-0012 unchanged, since a
   bigger model simply fit-tests to CPU more often). `SubagentRunner` takes the roster, loads the
   task **first**, resolves the entry, then admits→places→runs on that entry's resources.

8. **Advertisement is honest about the wiring it runs in.** The spawn tool builds its spec from
   the roster: the `model` enum lists every entry with its description, and the tool description
   states the ADR-0017 rule (on a turn that read untrusted content the default is enforced). In a
   wiring whose subagents are **tools-enabled**, ADR-0017 rule 2b pins *every* spawn to the
   default. The spec thus **omits the `model` property entirely** rather than advertising a knob
   that cannot do anything (the `context`/object form stays). The runner enforces regardless of
   what was advertised. That is defense in depth, not trust in the spec.

## Alternatives considered

- **Threading taint by changing `ToolRegistry.invoke(call, *, tainted)`** was rejected: a port
  change rippling through every registry (MCP, aggregate, filtered, skip, ungated, composite,
  fakes) to serve one built-in.
- **A context-var or a per-turn tool instance for taint** is rejected: implicit state or per-turn
  construction where a value-stamp is explicit, local, and testable.
- **Resolving the model in the spawn tool only** was rejected: the runner is the authority over
  what runs; a task reaching the store by any other path would bypass the boundary (decision 3).
- **Object-only `instructions` items** was rejected: the bare-string form is what the small tier
  emits most reliably, is backward compatible with the validated live behavior, and costs one
  `anyOf`.
- **Per-entry schedulers/placers** was rejected: the machine has one CPU/RAM budget and one GPU
  ledger; per-entry budgets would let a mixed team exceed both (ADR-0012's invariant).

## Consequences

- The cortex composes a heterogeneous team in one spawn call, choosing count, size, and per-subtask
  model, all within the one shared budget, and every untrusted-content path is pinned to the robust
  default by construction (ADR-0017 delivered).
- `builders.py` would cross the 300-line cap with roster construction; the subagent builders
  split into their own orchestrator module (same public names, re-exported).
- `SubagentResources` moves to `cortex_core.roster`; the `cortex_core` re-export keeps every
  import site unchanged.
- The interim compose stance (ADR-0012 deferral: both placement targets on one CPU server until
  Slice 11) is unchanged; a new **`docker/docker-compose.subagents-roster.yml`** override layers a second
  CPU `llama-server` (the documented cheap override, Qwen3.5-2B) plus its `ROSTER__qwen` env as the
  live multi-model validation target.
- Taint now degrades safely across a mid-delegation restart (decision 5) instead of silently
  clearing.

## Risks & notes

- **The enum can go stale against the wiring** if a roster entry's sidecar is down: the spec
  still advertises it and the spawn fails at inference, surfacing as an `ok=False` subagent
  result the cortex reads. This is acceptable (matches the existing dead-sidecar posture); the
  connect-time tolerance refinement (ADR-0009 addendum) covers the general problem.
- **Advertised descriptions are config-authored**, not measured: the trade-off text lives beside
  the endpoint that serves the model (`description` per entry;
  `CORTEX_SUBAGENTS_MODEL_DESCRIPTION` for the default). Wrong text misleads the cortex's
  *optimization* only and never safety, which is deterministic (decision 3).
- **`ToolCall.tainted` must never influence the *gate***. The gate keeps using the dispatcher's
  explicit `tainted` argument; the stamp is informational provenance for built-ins. A future
  refactor collapsing the two must keep the gate's source authoritative.
- **Deferred, recorded in the ROADMAP:** grammar-constrained subagent output (ADR-0017
  composes-with) stays open; richer measured-latency advertisement; the per-role escape hatch
  (ADR-0017 risks) remains unimplemented by design.

## Addendum on live validation via Docker (2026-07-03, agent)

Stack: base + subagents + subagents-roster overrides (`CORTEX_MODELS_DIR=/srv/models`), both
CPU sidecars healthy off the real GGUFs (default gemma-4-E4B on 8082, alternate Qwen3.5-2B as
`qwen` on 8083); the GPU override added for the cortex-driven half (resident gemma-4-12B).

- **Machinery:** the new roster live test (`test_spawn_subagents_routes_each_pick_to_its_roster_model`)
  passed on one batch mixing a bare item with a `{"model": "qwen"}` pick, both answered; servers
  are per-model, and the log counts confirmed routing (the pick was the qwen server's only
  request).
- **Cortex-driven:** over the seam, gemma-4-12B called `spawn_subagents` with a per-item
  `"model": "qwen"` object (audit trail), the qwen server's request count incremented, and the
  reply reported both subagent results (the full chain, model-decided).
- **Finding 1 (the pick needs the object form shown).** Given only prose ("run this one on the
  small fast 'qwen' model"), the cortex emitted bare strings and folded the pick into the
  instruction text. The subtask silently ran on the default (safe direction, wrong
  optimization). The spec's choice note now includes an inline object example.
- **Finding 2 (the object item can arrive JSON-encoded as a string).** On one run the cortex
  emitted `"{\"instruction\": ..., \"model\": \"qwen\"}"`, the object form *stringified into
  the string slot of the `anyOf`*. It parsed as a literal instruction on the default model.
  Run-to-run the same model emits either form, so the parser now diverts a string item that
  parses as a JSON object carrying an `instruction` key into the object path (same validation,
  same runner-side ADR-0017 enforcement; a brace-led string that is not that stays a plain
  instruction). Re-validated live after the change: the pick reached the qwen server.

Evidence commands and bring-up in [runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md) §2b.

## Addendum (2026-07-13): the taint stamp is now the ADR-0027 TurnStamp

Structured turn provenance (ADR-0027) renamed the field and keyword this ADR's mechanism
names: `ToolCall.tainted` became `ToolCall.stamp` (a frozen `TurnStamp` of `session_id` +
`tainted`) and `dispatch(call, tainted=...)` became `dispatch(call, stamp=...)`. The
mechanism and the invariant are unchanged with the rename applied: the dispatcher still
overwrites the call's stamp with its own argument, a model-forged stamp still feeds
nothing, and the gate still decides on the dispatcher's argument (`stamp.tainted`), never
the call field. The spawn tool reads `call.stamp.tainted`.

## Addendum (2026-07-16): the advertised trade-off now matches the measured hardware

The "advertised descriptions are config-authored, not measured" note above (Risks) framed the
deferred measurement work as *deriving the per-entry `description` strings from latency/robustness
numbers*. Reading it against the code found a sharper, measurable target the note missed. The
`description` strings are deployment-specific config and stay config-authored (deriving them in
code is declined; safety is deterministic in `SubagentRoster.resolve` regardless). But `spawn.py`
also advertised a *structural* trade-off independent of config: the tool description told the
cortex subagents "run concurrently" and delegation was "worth parallelizing", a blanket parallel
claim.

That claim was contradicted by the same-day measurement recorded in the
[ADR-0012 admission-wall addendum](ADR-0012-resource-governance.md): each roster entry holds one
`LlamaCppBackend` per target whose `SingleResidentModelManager` lock is held for the whole stream,
so **same-model** spawns serialize on that lease and only **distinct-model** spawns overlap
(measured live on the Qwen-2B CPU override: two concurrent same-model spawns 10.0 s vs 4.8 s
across two backend objects, ratio 2.08, full serialization).

**Landed:** the spawn spec's description now states this measured trade-off. The base description
drops the blanket "concurrently"/"worth parallelizing" wording; the model-choice note points the
cortex at spreading independent subtasks across distinct roster models as the wall-clock lever;
the pinned/single-entry note says a batch on the one model groups independent work rather than
speeding it up. Decision 8 (advertisement honest about the wiring) now extends to being honest
about the wiring's *timing*, not just its safety pins. This also delivers the "spontaneous model
picks" nudge finding 1 wanted, since the parallelism line gives the model knob a concrete reason
(a faster batch) to reach for beyond a directed pick. The behavior is unchanged: `invoke` still
dispatches the runs together via `asyncio.gather`; only the advertised text changed, guarded by
spec-description assertions in `test_spawn.py` (mutation-proven: reverting the text reddens them).

The measurement is reused from the same-day admission-wall work, cited as prior rather than
re-run; the mechanism (`asyncio.Lock` per entry, held for the stream) is confirmed in `model.py`.
**Residual (fix when it bites):** whether a live cortex now reaches for distinct models unprompted
cannot be validated on the 8 GB dev GPU (gemma-12B, the cortex tier, does not fit, and the
cortex-only spawn tool cannot be proxied on the small subagents, which do not respect prompt
framing the same way). The trigger is a live cortex on user-tier hardware still under-reaching;
the fix is stronger nudging behind the same spec seam, never a schema change.

## Addendum (2026-07-19): the nudge's uptake is measurable on the dev GPU

The residual above says whether a live cortex reaches for distinct models unprompted "cannot be
validated on the 8 GB dev GPU (gemma-12B, the cortex tier, does not fit ...)" and puts its trigger
on "user-tier hardware". The parenthetical is false.
[ADR-0029](ADR-0029-vision-screen-capture.md) ran `gemma-4-12b-it-qat-q4_0.gguf` on that card on
2026-07-17 at `-ngl 99 --ctx-size 4096 --parallel 1` with its vision projector loaded and drove a
real vision turn through the shipped inference adapter on 2026-07-18, and
[ADR-0030](ADR-0030-brain-handoff.md) records the model alone taking 7715 of that card's
8188 MiB. The rest of the
parenthetical stands and is the part that matters for design: the spawn tool is cortex-only and the
small subagents do not respect prompt framing the way the cortex does, so no subagent-tier proxy
tests this.

**What this changes.** The probe becomes agent-side work: a resident cortex at 4K, the roster up on
its CPU sidecars, which contend for no VRAM, and a prose-only ask carrying independent subtasks. It
is listed as actionable now in [docs/refinements/index.md](../refinements/index.md), with the entry
itself at [docs/refinements/index.md#subagents](../refinements/index.md#subagents). The fix stays
fix-when-it-bites, unchanged, and the same question at the production 16K context with more than
one slot stays host-side. The pointer at
[ADR-0010](ADR-0010-subagents.md) repeats the false clause and is corrected there.

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-08-04): the nudge's live uptake, observed

The residual the two addenda above hand forward, whether a live cortex reaches for **distinct**
roster models unprompted, was run on the development card. It has an answer, and running it split
the question in two, because the residual had folded a prior question inside it: before a cortex
can spread a batch it has to want a batch at all.

**Setup.** Base + gpu + subagents + subagents-roster on the 24 GB card, models under
`CORTEX_MODELS_DIR`. The cortex tier is the shipped one, started by the model host over
`gemma-4-12b-it-qat-q4_0.gguf` with `-ngl 99 --ctx-size 16384 --parallel 1 --jinja`, so this ran at
the **production 16K context and a single slot** rather than the 4K the entry proposed;
`nvidia-smi` read 1893 MiB with nothing loaded, 9676 MiB with it resident, and 1870 MiB again after
teardown. The roster is the two-entry one the overrides build, read live inside the brain container
through `SubagentsConfig()`: `subagent` (gemma-4-E4B on `:8082`, the robust default) and `qwen`
(Qwen3.5-2B on `:8083`). Every turn ran through the real `stream_tool_loop` over a dispatcher the
real builders assembled (`build_subagents`, `build_builtin_tools`, `build_cortex_tools`), with the
security preamble in place via `assemble_inference_messages` and `spawn_subagents` as the **only**
advertised tool, which is the most favourable condition delegation could be given.

**The tool was armed, checked before any silence was read as a decision.** The advertised spec
carried the model enum `["qwen", "subagent"]` and the trade-off sentence verbatim ("Subtasks on
distinct models run in parallel, while subtasks that share one model run one after another (one
backend each), so spread independent subtasks across models to finish the batch sooner"). A control
ask that directed the picks produced one `spawn_subagents` call carrying `{"model": "qwen"}` and
`{"model": "subagent"}`, one `launch_slot_` line in each server's log, and both answers back, in
95.34 s.

**Finding 1: a prose-only ask does not reach for delegation at all.** Four asks, each carrying
three or four genuinely independent subtasks and saying nothing about delegation, over **20 turns**
(twelve run to completion, eight sampled at the dispatch): **zero** `spawn_subagents` calls, 9.88 s
to 76.03 s per turn. The traces do not decline to delegate, they never raise it: `subagent`,
`delegat`, `spawn` and `farm` appear **zero** times across the twelve full reasoning traces. The
cortex enumerates the subtasks as a checklist and answers them itself, which on this deployment is
also the better answer, since the CPU tiers generate at 0.35 tok/s (gemma-4-E4B under its 4 CPU
cap) and 0.97 to 1.10 tok/s (Qwen3.5-2B), so a delegated paragraph costs minutes the cortex spends
in seconds. **The probe as specified therefore cannot observe a spread**, because it never produces
a batch.

**Finding 2: invited to delegate, it delegates every time and piles the batch on one entry every
time.** Two asks that request delegation in ordinary user prose (no tool name, no model name, no
parallelism language), over **16 turns: 16 delegations, 0 spreads.** Of the 15 batches whose
arguments were recorded, 11 used the object item form and 4 bare strings, and exactly **one**
carried a `model` key at all: it put all three subtasks on `qwen`, which is a pile on the cheap
entry rather than a spread. The other fourteen ran entirely on the default, as did the sixteenth
turn, which was abandoned while its batch ran and during which the alternate's server served
nothing at all. The one explicit pick states
the reasoning plainly, and states it while holding the belief the trade-off line was written to
remove: "I can use `spawn_subagents` to handle these three requests in parallel. Since the content
is simple and doesn't involve untrusted data, I can use the default model or `qwen` for speed, but
`subagent` is safer. Actually, `qwen` is fine for these simple definitions." The choice is made per
subtask on cost and safety, never on the batch's shape.

**Finding 3, from the code rather than the card: the nudge is only ever shown to the deployment
with the least reason to delegate.** `build_spawn_spec` advertises the `model` knob, and the spread
sentence with it, only when `not tools_enabled and len(roster.entries) > 1`, while
`build_subagent_tools` hands subagents a dispatcher whenever any tool registry is configured at
all. So the moment a deployment layers the tools or email overrides, every spawn is pinned to the
robust default (rule 2b above) and the spec swaps the spread advice for the pinned note, which says
the batch groups independent work rather than speeding it up. Confirmed by building the spec both
ways off the running deployment's own roster: `tools_enabled=False` publishes the knob and the
spread sentence, `tools_enabled=True` publishes neither. The nudge's whole audience is a tool-less
multi-entry deployment, whose subagents can only do prose work, which is exactly the work finding 1
shows the cortex keeps for itself.

**A correction to the advertised sentence, measured rather than argued.** "Subtasks that share one
model run one after another (one backend each)" is not quite true of this deployment. An entry
holds one backend **per placement target**, and the roster override omits `gpu_endpoint`, so both
of an entry's targets dial one server. With the `qwen` ask at 2.5 GB against a 2.7 GB headroom
(`CORTEX_VRAM_SOFT_CAP_GB` 14.0 minus `CORTEX_VRAM_CORTEX_GB` 11.3) exactly one spawn of a batch is
GPU-placed and the rest overflow, so two lock objects front one server: the three `qwen` subtasks
launched two in the same millisecond and the third only when the first released. The default
entry's 5.5 GB ask never fits, so its batches are strictly serial (258.4 s, 208.7 s, 330.2 s, one
after another). The advertised claim is therefore conservative rather than wrong, and what it
overstates is the size of the prize for spreading, which is one more reason to leave the fix
queued. **The last of those readings has since changed and the conclusion has not (2026-08-08):**
both budget terms were measured, the reservation to 8.6 GiB and the default entry's ask to 3.5, so
the default entry now behaves exactly as `qwen` did here, one spawn of a batch GPU-placed and the
rest overflowing, rather than strictly serial. Two lock objects still front one server wherever an
entry omits `gpu_endpoint`, which is what this correction is about.

**What the correction reached a day later (2026-08-09), and what it deliberately did not.** The
same premise had also been written into arithmetic rather than into prose: the bounded admission
wait in `scheduler.py` derived its 3600 s default from the serialization reading as though it held
unconditionally, and a test pinned the derivation. That one was corrected against the measurement
above ([ADR-0012](ADR-0012-resource-governance.md)). The number did not move, the serial reading
surviving as what a closed GPU tier leaves and 3600 s being twice it; what moved is the claim, from
an equality to an upper bound four times the wait the shipped stack produces. The advertised
sentence stays declined on the grounds this section already gave, being prose a model reads whose
error understates the prize, where the arithmetic's error was a derivation with a correct answer
and a false reason and no wording to guess at.

**What changes, and what does not.** The spec text is unchanged. This run says the advice is not
taken; it does not say which wording would be taken, and rewriting on the strength of one
deployment's behaviour is the guess this residual was written to avoid. The entry stays open and fix-when-it-bites, with its trigger
sharpened by all three findings, at
[docs/refinements/index.md#subagents](../refinements/index.md#subagents). What the run buys is a probe that is
cheap to repeat: `packages/orchestrator/tests/test_spawn_nudge_live.py` carries the armed check and
both asks, and [runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md) section 3c carries the
bring-up and the two ways to make the run meaningless (any tool override, or a one-entry roster).
