# Tools & MCP

This area's deferrals originate in [ADR-0009](../adr/ADR-0009-tools-mcp.md), with the
spawn batch cap recorded at [ADR-0010](../adr/ADR-0010-subagents.md). Extracted from the
ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed
entries are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** salience limit knob, cross-loop salience, `CORTEX_SUBAGENTS_MAX_BATCH` knob,
cost-aware batch cap, fair-share policy across a batch, sidecar session cache/pool

**Tools in Slice 6 ([ADR-0009](../adr/ADR-0009-tools-mcp.md)):** multi-server aggregation,
advertised-tool filtering, and readable-text-from-HTML extraction **landed 2026-07-03**
(ADR-0009 refinements addendum, with `AggregateToolRegistry`/`FilteredToolRegistry` in the core,
`CORTEX_TOOLS_ENDPOINTS__<name>` config, `html_to_text` in the email sidecar); the
partial-degradation policy for the aggregate **landed 2026-07-03** as well (degraded-mode
addendum adds `SkipUnavailableToolRegistry` + `CORTEX_TOOLS_ON_UNAVAILABLE=skip`, default
`fail`). Remaining:
- **The dispatch half of the rate policy landed 2026-07-14 ([ADR-0009 budget
  addendum](../adr/ADR-0009-tools-mcp.md)).** This entry claimed the loop was "bounded by
  `MAX_TOOL_STEPS`", and the ADR's risks said the same; both were false for tool spam.
  `MAX_TOOL_STEPS` bounds inference **rounds**, and within one round `stream_tool_loop`
  dispatched *every* call the model emitted, uncapped, on the only path reaching external
  services (one round of 500 `tool_calls` was 500 dispatches; eight rounds, 4000). Now
  `MAX_TOOL_DISPATCHES` (32, per loop via `ToolLoopContext.dispatch_budget`) caps the **total**
  across rounds, a total rather than a per-round cap so the answer to "how many external calls
  can one turn make?" is one number and not a product of two constants. Past it the call is
  still handed to the dispatcher, which refuses it (`BUDGET_EXHAUSTED_MSG`) and audits it:
  breaking out instead would strand the round's `tool_calls` without their `Role.TOOL` answers
  (malformed conversation on re-inference) and produce refusals no audit record sees. The check
  sits **ahead of the gate**, so hundreds of gated calls cannot become hundreds of confirmation
  prompts, and **above** the `ToolStep` yield, so a refused call lights no activity chip (which
  makes the chip addendum's "emission is intrinsically bounded per turn" true retroactively).
  CI-gated over the fakes at 100% and mutation-proven (reverting each of the three guards
  individually turns the new tests red). Remaining behind the same seams:
- **The per-tool cost half of the budget landed 2026-07-14 ([ADR-0009 cost
  addendum](../adr/ADR-0009-tools-mcp.md)).** The budget counted *calls*, so 32 filesystem reads
  and 32 `spawn_subagents` batches spent it identically. The loop now keeps a running spend and
  charges each call `dispatcher.cost_of(name)` from a `ToolCostPolicy` that lives on the
  dispatcher beside the gated-name set (a composition-root declaration by name, never read off
  a `ToolSpec`, so a sidecar cannot price itself). Unpriced tools cost 1, so with nothing priced
  the budget is the call count it was, and neither `ToolLoopContext` builder needed a new
  parameter. A call that does not fit **closes** the budget rather than being stepped over, so
  the refusal's "stop calling tools" stays true and the turn's spend does not depend on call
  order. Only `spawn_subagents` is priced by default (`MAX_TOOL_DISPATCHES // 4`, four
  delegations a turn): it is the one wired tool that fans out into a batch of model runs with no
  gate in front of it, whereas `send_email` is deliberately left unpriced because the ADR-0022
  confirmation is the far tighter bound on it. `CORTEX_TOOLS_COSTS__<name>` is validated to
  `1..MAX_TOOL_DISPATCHES` at boot (free and unaffordable both hide rather than announce
  themselves), and because a nested-dict env key replaces the whole mapping, the built-in prices
  are merged *under* the user's so pricing one tool cannot silently unprice another. CI-gated
  at 100% and mutation-proven (four guards, each reverted individually to red). It also moved
  `MAX_TOOL_DISPATCHES` into the new `tool_budget.py` beside the prices (one currency: that
  module owns how much a loop may *spend*, `tool_loop.py` how *long* it runs), which the line
  cap forced by failing at 302 on `cortex_core/__init__.py`. Remaining:
- **`cortex_core/__init__.py`'s headroom returned 2026-07-14 (300 lines to 162).** The barrel sat
  at exactly the cap, so the *next* public core name broke the line-cap gate for whatever
  unrelated change added it. None of the three options this entry listed was taken, because each
  treated the 151-name public surface as the cost when the surface was never the problem: the
  file spent **two** lines per name, one to import it and one to restate it in `__all__`.
  Re-export is now declared with the typing spec's redundant-alias form (`X as X`), which pyright
  honors identically and which says it once, so the same 151 names cost 151 lines and a new one
  costs a line instead of two. No consumer changed (every name still imports from `cortex_core`,
  so the package-level convention stands), no export was pruned, and no sub-barrel was
  introduced. Two things the implementation found: ruff **exempts `__init__.py` from PLC0414**
  (useless-import-alias) precisely because the redundant alias is the re-export convention there,
  so `select = ["ALL"]` needed no new ignore; and nothing in the tree read `cortex_core.__all__`
  (only `cortex_seam`'s own facade test reads its package's list), so dropping it broke no
  contract. Verified green: ruff, ruff format, pyright strict, and the full brain suite at 100%.
- **Salience on the tool loop landed 2026-07-14 ([ADR-0009 salience
  addendum](../adr/ADR-0009-tools-mcp.md)).** The third and last bound of decision 3's rate policy,
  and the one that asks whether a call is worth making rather than how many or how much. Three
  wastes were bounded only by the pool of 32: the same call twice in one round (the model chose
  both before seeing either result, so the second cannot inform anything), the same call every
  round, and, the one that mattered, **a declined gated call retried**, since the gate consults
  the `Confirmer` per dispatch and nothing but the budget stopped a model re-emitting a refused
  `send_email` from putting **up to 32 approval cards** in front of the user for one action.
  `RepeatSalience` (a pure `SaliencePolicy` seam in `tool_salience.py`, the
  `HistoryWindow`/`RecallPolicy` pattern) admits a call unless an identical one (same `name` and
  `arguments`) already ran **in this round**, or already ran **twice in this loop**. The tempting
  reading of "deserve", a policy that predicts whether a call will help, was rejected outright as
  a model judgment smuggled into deterministic code. Two rather than one on the asymmetry of the
  failures: refusing at one denies information (the re-read after a write returns the stale
  listing), allowing two wastes at most one dispatch, and preferring the benign failure is the
  ADR-0025 clamp's argument again. **Attempts are counted, not answers**, which an earlier draft
  had backwards: a gate denial and a declined confirmation are `is_error` results too, so
  counting successes would have left the card spam this entry exists for completely untouched.
  The refusal rides the budget's own machinery (dispatcher-issued, audited, model-visible) and
  is checked **before** the budget is charged, so a repeat costs nothing, and **ahead of the
  gate**, which is what turns those 32 cards into at most two. **Per loop, not per turn, the
  opposite of the budget and deliberately**: the pool bounds reach, a resource the turn's
  subagents share, while a repeat is redundant only against the `working` messages holding its
  answer, which a sibling cannot see. Two costs this entry did not predict, both real: the
  ruff argument ceiling made a third declaration impossible as a seventh parameter, so
  `gated_names`, `costs`, and `salience` became one `DispatchPolicy` (the honest grouping anyway,
  and headroom for the next one), and `over_budget: bool` became `refusal: DispatchRefusal | None`
  rather than growing a second parallel boolean. `CORTEX_TOOLS_SALIENCE=off` (`AlwaysSalient`) is
  the pre-policy loop exactly, but the default is on, because a bound that ships off protects
  nobody. CI-gated at 100% with twelve guards mutation-proven, including the counterfactual pair
  (the fixture whose forty repeats cost a pool of two spends and closes that same pool with the
  policy off). Remaining behind the same seam: **argument identity is structural**, so two
  spellings of one intent are two calls (normalizing needs the advertised parameter schema at the
  policy, and the direction is at least the safe one); **a per-round cap on distinct calls**,
  the one shape neither bound closes, since a round may still append unboundedly many results or
  refusals to `working` (a context-growth problem, not a reach one, and pre-existing); **a limit
  knob** if two proves wrong; and **cross-loop salience** for a batch of subagents handed one
  instruction, which would need a different justification than this policy's.
- **The per-round cap on distinct calls landed 2026-07-16 ([ADR-0009 round-cap
  addendum](../adr/ADR-0009-tools-mcp.md)).** The one shape the pool and salience both leave open,
  and this entry, its own ADR, and the index warning all had the diagnosis exactly right: it is a
  **context-growth** problem, not a reach one. Every call a round emits costs an appended
  `Role.TOOL` message whether it ran, was refused as a repeat, or was refused past a closed pool,
  so a round of a thousand calls was a thousand messages fed straight back into the next inference
  at a cost of one dispatch when they were identical (salience refuses the twins) and of zero pool
  when the pool had closed (the budget refuses them and still appends). A cap on the calls
  *dispatched* would therefore have bounded nothing, since the refusal is appended too. The cap is
  `MAX_CALLS_PER_ROUND` (16, half of `MAX_TOOL_DISPATCHES`) in a new pure-core `tool_round.py`,
  and it works by **dropping**: `plan_round` cuts a round to the cap plus one **overflow slot**,
  the assistant message's own `tool_calls` truncated with it so the conversation stays well formed
  (one `Role.TOOL` answer per `tool_call_id`), and everything past the slot appends nothing at
  all. The slot is refused as `ROUND_OVERSIZED_MSG`, which names the cap and invites the next
  reply, because a truncation the model **cannot observe** is the one failure a cap must not
  create: it would re-emit the dropped calls every round until the round bound ran out. Three
  boundary behaviours were rejected: refusing the whole round (drops work the model may still
  need and grows the context by a refusal per call), truncating silently (the retry-forever
  failure), and a per-call refusal result (bounds the reach the pool already bounds, not the
  growth). "**Distinct**" was read as *calls emitted*, not distinct names or `(name, arguments)`
  pairs: growth is driven by emission regardless of identity (a round of 200 identical calls still
  appended 201 messages though salience let one through), so the cap counts emitted calls and, by
  construction, does **not** depend on the separate structural-argument-identity entry above. Half
  of `MAX_TOOL_DISPATCHES` on purpose: a model chooses a round's calls before seeing any of that
  round's results, so a blind burst that could spend the turn's whole reach is strictly worse than
  one that must stop and read halfway, and two rounds at the cap exhaust the default pool. Refused
  ahead of both other bounds (the slot reaches nothing, so it is charged nothing and lights no
  chip), audited like every dispatch. CI-gated at 100% line and branch over the fakes and
  mutation-proven (the truncation, the kept slot, the boundary, the overflow flag, the refusal,
  its ordering ahead of the budget, and the assistant-message truncation each reverted
  individually to a distinct red test), and **live-validated** 2026-07-16: a real Qwen3.5-4B on
  the GPU, asked over the reference filesystem sidecar to read more files than the cap in one
  reply, emitted an oversized round, was truncated to the cap plus one refusal, and read the
  refusal to fetch the rest over further rounds. Nothing behind this one; the adjacent
  refinements (structural argument identity, the salience limit knob, cross-loop salience) stay as
  listed above.
- **Structural argument identity in salience is declined 2026-07-16 ([ADR-0009 structural-identity
  addendum](../adr/ADR-0009-tools-mcp.md)).** The salience addendum's first remaining item, and the
  index warned this very area had misdiagnosed its own cost before, so it was read against the code
  first. The threat it carried, that permuted keys and other spellings evade a per-argument dedup,
  is **already closed** for the case that motivated it: `RepeatSalience` compares `arguments` with
  `Mapping.__eq__`, which is deep and key-order-independent at every nesting level, so permuted keys
  already collapse to one call (`test_arguments_compare_structurally_rather_than_by_key_order` pins
  it, and turns red the moment identity switches to an unsorted serialization), JSON whitespace
  never survives into the parsed mapping, and Python-equal scalars (`1` and `1.0`) collapse too. A
  **schema-free** canonical form (recursively sort keys) closes nothing equality does not, and its
  natural serialized shape is a regression: unsorted reopens permuted keys, sorted splits `1` from
  `1.0`. The only cases a **schema** would close (a present-versus-omitted defaulted optional, a
  cross-type scalar, and the entry's own `a.txt` versus `./a.txt`, which no schema reaches) are
  unsound to fold: JSON Schema `default` is advisory, not applied, so folding an omitted key onto it
  can collapse two calls a tool runs differently and **refuse a legitimate call**, the non-benign
  failure this policy's "limit is two, not one" decision deliberately avoids. And the residual is
  bounded anyway: extra dispatches are capped by `MAX_TOOL_DISPATCHES` (32) and `MAX_CALLS_PER_ROUND`
  (16), and the card-spam case is bounded independently of spelling, since a gated call on a tainted
  turn is denied outright with no card and an untainted turn's budget caps dispatches at 32. Docs
  only, no seam change; the entry above stays verbatim as the historical record. It reopens only if
  a real wired tool shows a semantic-equivalence evasion those three bounds do not cover, and even
  then the sound fix is a per-tool domain normalizer (the model judgment the ADR rejected), not
  schema folding. Nothing opened behind it.
- **The turn-wide dispatch budget landed 2026-07-14 ([ADR-0009 turn-wide
  addendum](../adr/ADR-0009-tools-mcp.md)).** Both budget addenda sold "one number answers how many
  external calls one turn can make", and delegation made it false: `spent` was a local in
  `stream_tool_loop` and the runner builds a fresh `ToolLoopContext` per task, so every subagent
  started at zero. This entry's own "can exceed 32 in aggregate" understated it, because
  `spawn_subagents` takes an **unbounded** `instructions` array: four batches (all the
  `MAX_TOOL_DISPATCHES // 4` price allows) of fifty subagents was 6400 dispatches for a spend of
  32, so the price bought bounded *batches* and unbounded *calls*. The counter is now a
  `DispatchBudget` object in `tool_budget.py` (`charge(cost) -> bool`, which also moves "a call
  that does not fit closes the budget" out of the loop and into the budget), and it reaches
  spawned work on the **`TurnStamp`**, the channel the loop already stamps and
  `spawn_subagents` already reads for taint, so no `dispatch()` keyword and no second field on
  `ToolCall` were added. That is the stamp's first non-provenance field, a deliberate widening to
  "what the dispatching turn hands work this call spawns" (`tainted` was already both), and the
  handle is excluded from the stamp's equality (`compare=False`) since a shared resource is not
  part of a value. One pool first-come-first-served, not a per-subagent share: dividing the
  remainder has to guess how many of a batch will call tools at all, and it makes the answer a
  function of fan-out again, which is the arithmetic being removed. Closure is turn-wide too, so
  `BUDGET_EXHAUSTED_MSG`'s "this turn has reached its limit" is literally true. The spawn price
  stays, because the two bounds count different things: the pool counts dispatches, and a
  subagent that calls no tools spends nothing from it while still costing an admission slot, a
  placement, and a model run. A root caller with no pool (the ticker's fire) still gets its own,
  unchanged. CI-gated at 100% with six guards mutation-proven (each reverted individually turns
  the new tests red). Remaining:
- **The batch cap on `spawn_subagents` landed 2026-07-14 ([ADR-0010 batch-cap
  addendum](../adr/ADR-0010-subagents.md)).** The shared pool bounded a batch's dispatches, never its
  **model runs**, so one call could still ask for any number of subagents, each an admission slot,
  a placement, and an inference. The pool could not close this itself, because the two count
  different currencies: a tool-less subagent spends nothing from it, and
  `ResourceBudgetScheduler.admit` **queues** rather than refuses (ADR-0012, by design), so an array
  of fifty was never an error the cortex saw, just fifty inferences the turn sat through, two at a
  time under the default CPU budget. `MAX_SPAWN_BATCH = 8` (a constant beside `MAX_TOOL_DISPATCHES`,
  since how many subtasks one *call* may ask for is policy, while what the host runs *concurrently*
  is the deployment fact the CPU-budget env already tunes) **refuses** an oversized batch rather
  than truncating it, since dropped subtasks would hand the cortex an aggregate that reads as
  complete, whereas the `is_error` result is one the model corrects by re-delegating in batches that
  fit. The check runs **ahead of item parsing**, so nothing is stored and nobody is placed, and the
  cap is advertised as the array's `maxItems` plus prose, so the runtime check is a backstop rather
  than the first the cortex hears of it. Per call rather than a turn-wide pool: the turn-wide
  addendum's "one number, not a product" argument was really about a factor that was *unbounded*,
  and both factors are deliberate now (a spawn costs a quarter of the pool by default, so a turn
  affords four batches, ceiling 32 model runs), while a closing turn-wide pool would end delegation for the whole
  turn on the first oversized batch instead of correcting it. One property fell out rather than
  being designed: a refused batch still costs its spawn price (the loop charges ahead of the
  dispatch), so retry spam is bounded at four attempts. CI-gated at 100% and mutation-proven (cap,
  comparison, advertisement; each reverted individually turns a distinct test red). Remaining behind
  the same tool: a **`CORTEX_SUBAGENTS_MAX_BATCH` knob** if a host ever wants a different ceiling,
  and a **cost-aware batch** (a cap in placements or estimated VRAM rather than in items) if roster
  entries ever differ enough that eight of one is not eight of another.
- **A fair-share policy across a batch.** One greedy subagent can spend the turn's remaining pool
  before its siblings charge anything. Starvation degrades an answer without breaching the bound
  (the starved subagent reads the refusal and reports stopping short), so it stays deferred until
  it shows up in practice.
- **Connect-time sidecar tolerance / reconnect policy landed 2026-07-08
  ([ADR-0009 boot-tolerance addendum](../adr/ADR-0009-tools-mcp.md)).** Skip mode covered a sidecar
  dying *after* connect; a sidecar down *at brain startup* still failed `McpToolRegistry.connect`
  in the wiring, with no re-dial. A Docker/uv probe against the real `mcp`/`httpx`/`anyio` stack
  found the held-`AsyncExitStack` `connect` was the problem. Its anyio task-group cancel scopes
  are task-bound (close-from-another-task errors) and a refused boot dial surfaced as a bare
  `CancelledError`, uncatchable by skip mode. So `connect` is **retired** for a structured,
  same-task `streamable_http_session` (`@asynccontextmanager`) driven by a new
  `ReconnectingMcpToolRegistry` that opens a **fresh session per call**: `build_tool_registry` is
  now synchronous and dials nothing, so a sidecar down at boot no longer fails the build (its
  first-use open fails as `ToolError` that `SkipUnavailableToolRegistry` serves around) and a
  recovered sidecar rejoins without a restart. CI-gated end to end over a scripted opener (open
  success, refused dial, anyio `ExceptionGroup`, re-dial, listing passthrough) at 100%. Remaining
  behind the same `ToolRegistry` port: a **session cache/pool** to retire the per-call open
  overhead (a localhost handshake per describe/invoke, which is acceptable at personal scale, an
  optimization when it matters).
