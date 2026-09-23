# ADR-0017: Untrusted content never reaches an injection-weak subagent model

**Status:** Accepted (2026-07-13)

## Context

Heterogeneous subagent models ([ADR-0018](ADR-0018-heterogeneous-subagents.md)) let the cortex pick
the subagent model **per spawn** from the whole roster, including small models the injection tests
find weak: framed and at temperature 0, gemma-4-E2B obeyed 3 of 10 payloads and Qwen3.5-2B 1 of 10,
where the cortex and the subagent pick (gemma-4-E4B) obeyed none. At the engine's sampler the
subagent pick obeys 8 of 100 framed draws, `output-laundering` in 46 of 100, and the others are not
yet drawn there ([injection text rows](../readings/injection-text-rows.md)). Treating the cortex's
model choice as pure discretion opens a failure the deterministic layers do not cover. The plausible
failure is not an injection tricking the injection-resistant cortex. It is a **well-behaved** cortex
routing a subtask over untrusted content to a cheap model to save latency, with no way to know the
content is hostile.

The deterministic layers contain a subagent's *actions* regardless of model: no outbound tools and
none that need confirmation ([ADR-0013](ADR-0013-untrusted-content.md) decision 9), the fail-closed
confirmation rule, taint containment, and the [ADR-0015](ADR-0015-output-guardrail.md) URL
redaction on the user-facing reply. But content-parroting and laundering **into** that
taint-contained output is strictly worse from a weak reader than a resistant one, and the whole
path is avoidable. The earlier framing ("the roster's weak entries are never deployed") was wrong:
with a per-spawn pick, every roster entry is a live runtime choice.

## Decision

1. **Model choice is an optimization hint, not authority.** The wiring **forces** the
   injection-resistant default model (the [ADR-0004](ADR-0004-model-lineup.md) subagent pick)
   whenever the spawn path can bring in untrusted content, overriding the model the cortex
   requested. The cortex still picks *how many* and *what* subtasks freely.
2. **"Can bring in untrusted content" means either of two deterministic, turn-local signals known
   at spawn time:**
   - **(a) the spawning cortex turn is already tainted**. It read untrusted content before
     spawning (the `TaintLedger`, ADR-0013), so anything it forwards into a subagent's instruction
     or context is suspect; **or**
   - **(b) the subagent is tools-enabled**. It holds the read-only MCP subset and can fetch
     untrusted content *itself*, so its own future taint cannot be known at spawn time; force the
     resistant model to be safe.
3. **Therefore a cheap or weak model is reachable only for a tool-less subagent on an untainted
   turn** (a pure text transform over trusted material). Every path where untrusted content could
   reach a subagent runs the resistant model by construction, not by the cortex's judgment.
4. **The resistant default follows the ADR-0004 pick** (a config-level logical id, `subagent`, not
   a hard-coded model), so a future change of pick moves the override with it.
5. **The rule is applied per task, in the core, from the store.** `SubagentRoster.resolve`
   (`cortex_core/roster.py`) takes the requested name, the task's `tainted` flag and whether the
   wiring gives subagents tools, and returns the default on either signal whatever was requested,
   unknown names included. On a clean tool-less path it returns the requested entry (`""` means the
   default), and an unknown name resolves to nothing, which the runner persists as a failed result,
   failing closed. The runner calls it for every task it loads, rather than the spawn tool calling
   it once, so a task reaching the store by any path still resolves safely. The taint signal
   travels on the task record as the dispatcher's stamp; a scheduled task keeps its creating turn's
   taint and resolves again when it runs ([ADR-0025](ADR-0025-scheduling-reminders.md)). A roster
   with no entries, or whose default is not an entry, fails at construction.
6. **Grammar-constrained output composes with this rule on the one path it leaves open.**
   [ADR-0028](ADR-0028-grammar-constrained-subagents.md) decodes a tool-less subagent's reply into
   a fixed `{"reply": "..."}` envelope, so format-laundering (appended footers, links, sections)
   has no grammatical position even on a weak model. It applies to the tool-less path only,
   exactly the narrow case decision 3 leaves a weak model reachable in. This ADR is the
   *which-model* boundary; the envelope is the *what-shape-of-output* boundary.

## Consequences

- Untrusted content never reaches an injection-weak subagent model. This closes the gap the
  heterogeneous-roster design would otherwise open, the exact gap that made "the weak entries do
  not matter" false.
- The cheap fast models keep a **real but narrow** use: trusted pure-text subtasks. The spawn spec
  advertises them to the cortex with their trade-offs and says that on a turn that has read
  untrusted content the resistant default is enforced regardless of the pick. When subagents are
  tools-enabled, every spawn is forced by rule 2b, so no model choice is advertised at all.
- A roster entry's description is advertising only; no description changes what `resolve` returns.
- The rule is covered at 100% over fakes: a tainted turn with a weak model requested resolves to
  the resistant default, a clean tool-less spawn with a weak model requested gets it, and a
  tools-enabled spawn with a weak model requested gets the resistant default. One test runs the
  whole chain from an untrusted read through the taint ledger, the dispatcher stamp and the task
  record to the resolved model.

## Risks and notes

- **The subtlety in signal (b).** The tainted-turn rule (2a) alone misses a subagent that reads
  untrusted content *itself*, since at that spawn the cortex turn is not yet tainted. Rule 2b
  covers that case by keying on whether tools are enabled, which is known structurally at spawn
  time. Both rules together form the constraint; neither alone does.
- **Deliberate loss** of the "cheap model for a trivial *untrusted* lookup" optimization, as that
  path is precisely what is being closed.
- **Per-role exception, if ever justified:** a future subagent role needing a cheap model on a
  tainted or tool path for a proven-safe reason is a per-role override on the same port, not a
  relaxation of the default.

## Alternatives rejected

- **Trusting the cortex's judgment of which content is hostile**: the cortex cannot know, and the
  failure this closes is a well-behaved cortex choosing a cheap model.
- **Resolving once in the spawn tool**: a task reaching the store by another path (a scheduled run)
  would skip the rule.

## Related

- Code: `brain/packages/core/src/cortex_core/roster.py`, `runner.py`, `spawn_spec.py`,
  `subagent_attempt.py`; tests `test_roster.py`, `test_runner.py`, `test_delegation.py`.
- ADRs: [ADR-0018](ADR-0018-heterogeneous-subagents.md) (the roster),
  [ADR-0013](ADR-0013-untrusted-content.md) (taint),
  [ADR-0028](ADR-0028-grammar-constrained-subagents.md) (the reply envelope),
  [ADR-0004](ADR-0004-model-lineup.md) (the pick).
- Readings: [injection text rows](../readings/injection-text-rows.md).
