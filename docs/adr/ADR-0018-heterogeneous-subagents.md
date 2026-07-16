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
