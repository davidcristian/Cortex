# ADR-0018: Heterogeneous subagent models via the roster, per-spawn choice, and its plumbing

**Status:** Accepted (2026-09-11)

## Context

Delegation ([ADR-0010](ADR-0010-subagents.md)) first ran every subagent on one wired model:
`spawn_subagents` took bare instruction strings, `SubagentRunner` held one `SubagentResources`, and
the wiring built it from the flat `CORTEX_SUBAGENTS_*` environment. The intent is that the cortex
chooses the subagent model per spawn and mixes entries of the
[ADR-0004](ADR-0004-model-lineup.md) lineup: a small fast model for a trivial transform, the
injection-resistant pick for a harder subtask or one over untrusted content.
[ADR-0017](ADR-0017-subagent-model-safety.md) fixes the safety rule: the choice is a hint, not
authority, and any spawn that can bring in untrusted content runs the injection-resistant default,
deterministically.

ADR-0017 left the mechanics open: how the choice is expressed in the tool schema, how the turn's
taint reaches the spawn tool, where the forced-default rule runs, what the roster looks like in
config and wiring, and what a persisted task holds. Two facts shaped them. The turn's taint lives
in the tool loop, and the `ToolRegistry.invoke(call)` port has no place for it, although the
dispatcher receives it per call for the confirmation rule. And a subagent is a stateless function
over the `TaskStore`, so whatever the runner needs to select resources safely must travel on the
task record.

## Decision

1. **The spawn schema gains a per-item choice and the task's `context`.** Each `instructions` item
   is a bare string (the default model, no context) or an object `{instruction, model?, context?}`
   (`anyOf` in the advertised JSON Schema). `model` names a roster entry (an `enum` of the
   advertised names); `context` is the material the subagent works from. A bad item (empty
   instruction, unknown model, non-string context) becomes an `is_error` result the cortex can
   correct, never an exception. A string item that parses as a JSON object with an `instruction`
   key is read as the object form, because a live cortex sometimes emits the object stringified
   into the string slot; a string starting with a brace that is not that stays an instruction.

2. **The roster is a pure-core value** (`cortex_core/roster.py`): `SubagentResources`,
   `SubagentProfile` (`resources` and an advertised `description`), and `SubagentRoster` (`entries`
   by name and a `default` name, validated non-empty with the default present). The default is the
   injection-resistant pick by construction, ADR-0017's config-level logical id.

3. **ADR-0017 runs in the core, at the runner.** `SubagentRoster.resolve(requested, *, tainted,
   tools_enabled)` returns the default when `tainted or tools_enabled`, else the requested entry,
   else `None` for an unknown name, which the runner persists as an `ok=False` "unknown subagent
   model" result. Parsing validates and the runner enforces, so a task written to the store by any
   path resolves safely, and ADR-0017's three cases (tainted and weak runs the default, clean
   tool-less weak runs weak, tools-enabled weak runs the default) test one pure function.

4. **The turn's provenance reaches built-in tools as a stamp on `ToolCall`.** `ToolCall.stamp` is a
   frozen `TurnStamp` (`session_id`, `tainted`, [ADR-0027](ADR-0027-turn-provenance.md));
   `ToolDispatcher.dispatch(call, stamp=...)` overwrites it with its own argument before the
   registry invoke, so a stamp the model forged feeds nothing. Registries pass the call through,
   and the spawn tool reads `call.stamp.tainted` with no `ToolRegistry` port change. The stamp is
   transient: the loop appends the unstamped calls to the conversation. The confirmation rule reads
   the dispatcher's argument, never the call's field, and a refactor merging the two must keep the
   dispatcher's argument authoritative.

5. **The task record holds what safe resolution needs.** `SubagentTask` holds `model` (the
   requested entry, `""` for the default) and `tainted` (the spawning turn's taint at spawn time).
   `RedisTaskStore` encodes and decodes both strictly, and `SubagentResult.tainted` round-trips
   too, so taint survives a restart or a model swap like the rest of the record.

6. **The flat fields define the default entry; `CORTEX_SUBAGENTS_ROSTER__<name>` adds alternates.**
   Each value is one JSON object `{endpoint, gpu_endpoint?, vram_gb?, cpus?, memory_gb?,
   description?}` (`SubagentRosterEntry` in `config_subagents.py`), whose numbers default like the
   flat fields and whose empty `gpu_endpoint` falls back to `endpoint`. `CORTEX_SUBAGENTS_MODEL`
   names the default entry, whose resources come from the flat fields and whose description is
   `CORTEX_SUBAGENTS_MODEL_DESCRIPTION`, so a deployment without alternates is a one-entry roster
   and a compose override adds its `ROSTER__<name>` key without touching the base. A roster key
   equal to the default's name is rejected.

7. **One runner, one scheduler, one placer; per-entry backends and requests.** `_entry_profile` in
   `cortex_orchestrator/subagent_builders.py` builds one `SubagentProfile` per entry with its own
   `LlamaCppBackend` per placement target (one `SingleResidentModelManager` each, one shared HTTP
   client) and its own `PlacementRequest`. The `ResourceBudgetScheduler` and `VramBudgetPlacer` are
   shared, so admission and the VRAM total stay one budget whatever the mix
   ([ADR-0012](ADR-0012-resource-governance.md)). The runner loads the task first, resolves the
   entry, then admits, places and runs on that entry's resources.

8. **The advertised spec describes the wiring it runs in** (`spawn_spec.py`). The `model` property
   lists every entry with its description, and the tool description states the ADR-0017 rule. The
   property is built only when `not tools_enabled and len(roster.entries) > 1`: under tools-enabled
   subagents every spawn is forced to the default, so the choice would do nothing. The note about
   choosing includes an inline object example, because a cortex given only prose folded its pick
   into the instruction text. On timing it says subtasks on distinct models run in parallel while
   subtasks sharing one model run one after another, and the forced-default note says a batch
   groups independent work. A roster entry holds one backend per target and each keeps its lease
   for the whole stream, so spawns on one model overlap two ways at most (ADR-0012's consequences;
   the reading is in [subagent-budget.md](../readings/subagent-budget.md)); the sentence
   understates that overlap, and it stays.

   The live uptake was measured on the deployed cortex at its production context, with
   `spawn_subagents` as the only tool: 20 turns of prose requests containing independent subtasks
   produced no spawn call, and 16 turns inviting delegation produced 16 delegations and no spread,
   one batch of 15 recorded with a `model` key, chosen on cost and safety. The wording stays,
   because one deployment's behaviour does not say which other wording would be taken, and the
   entry that reopens it is [124](../refinements/tasks/124-nudge-live-uptake.md), with its probe in
   `packages/orchestrator/tests/test_spawn_nudge_live.py`.

9. **The alternate entry's server has the default's caps and thread count.**
   `llama-subagent-qwen` in `docker/docker-compose.subagents-roster.yml` declares `cpus`,
   `mem_limit` and `memswap_limit` written exactly as `llama-subagent` writes them, and passes
   `--threads` from the same substitution as its `cpus` cap ([ADR-0004](ADR-0004-model-lineup.md)
   decision 12). Each server is capped at the whole budget rather than a share: the scheduler's
   soft budget limits the pair, and splitting it between servers stays deferred with ADR-0012's
   single-executor position. The uncapped alternate was the slow one: its one thread per hardware
   thread decoded six to seven times slower than four threads under the four-CPU quota.
   `scripts/subagentcouplings.py` counts both occurrences in the roster file, and
   `scripts/defaultcheck.py` compares its defaults with the subagents file's.

10. **A roster description is config-authored trade-off text, and contains no measured rate.** The
    text lives beside the endpoint that serves the model; a wrong description misleads the cortex's
    optimization only, since safety is `resolve`. Deriving the text from latency or resistance
    numbers was declined, and so was writing a measured delivery rate into it, for three reasons. A
    rate would be filed under a roster name, and a name does not fix a model: the weights are a
    `command:` argument in a compose file the brain never reads, so a deployment that overrode the
    artifact would keep reading a number about another one. A rate is a reading under conditions no
    profile records (the artifact, the engine build, `CORTEX_SUBAGENTS_MAX_TOKENS`, the appended
    sentence, and a human judge). And the chooser barely reads the text, which reaches only a
    tool-less multi-entry wiring. The operator's runbook, where the pick is made, holds the rates
    ([subagents-cpu.md](../runbooks/subagents-cpu.md)); the matching decline for a per-entry wording
    is [ADR-0028](ADR-0028-grammar-constrained-subagents.md) decision 8, and the per-pick numbers
    are in [reply-envelope.md](../readings/reply-envelope.md).

11. **Which artifact serves an entry is the server's to report and the operator's to read.** The
    brain is not told. The core uses logical ids ([ADR-0004](ADR-0004-model-lineup.md) decision 2)
    and nothing in it branches on which weights answer. An artifact is a property of the server's
    argv, so a read would belong per call, an HTTP call on every spawn spec for a value nothing
    acts on. A path is not an identity: `GET /props` reports `model_path` as `/models` joined onto
    the operator's own variable, and the server's `digest` is empty. And a declared per-entry
    artifact would diverge from the compose `command:` with nothing comparing them. Each subagent
    server publishes on loopback, and the runbook says how to read `GET /props` against the running
    stack.

## Consequences

- The cortex composes a mixed team in one spawn call within the one shared budget, and every path
  that can bring in untrusted content runs the resistant default by construction.
- `docker/docker-compose.subagents-roster.yml` adds a second CPU `llama-server` (Qwen3.5-2B) and
  its `ROSTER__qwen` variable; [subagents-cpu.md](../runbooks/subagents-cpu.md) sections 2b and 3c
  bring the roster up and repeat the uptake probe, and the probe means nothing under a tool
  override or a one-entry roster.
- A roster entry whose server is down stays advertised; the spawn fails at inference and returns an
  `ok=False` result the cortex reads, the same behaviour as any dead sidecar.
- One entry's two targets are named by two artifact variables, `CORTEX_MODEL_FILE_SUBAGENT` and
  `CORTEX_MODEL_FILE_SUBAGENT_GPU`, and nothing compares them; a deployment naming different files
  makes which weights answer a spawn depend on where the placer put it. The compose comment and the
  runbook say both name one file; a check waits on
  [527](../refinements/tasks/527-one-roster-entrys-two-targets-are-named-by-two-artifact-variables.md).
- The per-role exception of ADR-0017 stays unbuilt by design
  ([125](../refinements/tasks/125-per-role-escape-hatch.md)).

## Alternatives rejected

- **`ToolRegistry.invoke(call, *, tainted)`**: a port change through every registry (MCP,
  aggregate, filtered, skip, `ConfirmFreeToolRegistry`, composite, fakes) to serve one built-in.
- **A context variable or a per-turn tool instance for taint**: implicit state or per-turn
  construction where a value stamp is explicit and testable.
- **Resolving the model in the spawn tool only**: a task reaching the store by another path would
  bypass the rule.
- **Object-only `instructions` items**: the bare string is what the small tier emits most reliably.
- **Per-entry schedulers or placers**: the machine has one CPU and RAM budget and one GPU total,
  and per-entry budgets would let a mixed team exceed both.
- **A measured rate on `SubagentProfile`, or a sentence typed into a description**: decision 10.

## Related

- [ADR-0017](ADR-0017-subagent-model-safety.md), [ADR-0010](ADR-0010-subagents.md),
  [ADR-0012](ADR-0012-resource-governance.md),
  [ADR-0028](ADR-0028-grammar-constrained-subagents.md).
- [brain-core](../modules/brain-core.md), [brain-orchestrator](../modules/brain-orchestrator.md),
  [subagents-cpu runbook](../runbooks/subagents-cpu.md).
