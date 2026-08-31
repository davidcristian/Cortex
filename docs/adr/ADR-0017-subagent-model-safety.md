# ADR-0017: Untrusted content never reaches an injection-weak subagent model

- **Status:** Accepted (a constraint on the **planned** Slice 8.6 with no code yet; recorded ahead
  of implementation so the slice is built safe rather than retrofitted).
- **Date:** 2026-07-03

## Context

Slice 8.6 (heterogeneous subagent models) will let the cortex pick the subagent model **per
spawn** from the full ADR-0004 roster, including the injection-weak small models
(`gemma-4-E2B` 4/10, `Qwen3.5-2B` 1/10 framed-obeyed; ADR-0013 harness). Treating the cortex's
model choice as pure discretion opens a failure the deterministic layers do not cover. The
plausible failure is not an injection tricking the framing-robust cortex, which scores 0/10 against
that harness. It is a **well-behaved** cortex routing an untrusted-content subtask to a cheap model
to save latency, with no way to know the content is hostile.

The deterministic layers contain a subagent's *actions* regardless of model. No outbound/gated
tools ([ADR-0013](ADR-0013-untrusted-content.md) subagent-exclusion addendum), fail-closed gate,
taint containment, and the [ADR-0015](ADR-0015-output-guardrail.md) URL redaction on the
user-facing reply. But content-parroting / laundering **into** that taint-contained output is
strictly worse from a 4/10 reader than a 0/10 one, and the whole path is avoidable. The prior
framing ("the roster's weak rows are non-deployed") was wrong: once 8.6 lands, every roster row
is a live runtime choice.

## Decision

1. **Model choice is an optimization hint, not authority.** In Slice 8.6 the wiring **forces**
   the injection-robust default model (the ADR-0004 subagent pick, currently `gemma-4-E4B`)
   whenever the spawn path can carry untrusted content, overriding the model the cortex
   requested. The cortex still picks *how many* and *what* subtasks freely.
2. **"Can carry untrusted content" is a disjunction of two deterministic, turn-local signals
   known at spawn time:**
   - **(a) the spawning cortex turn is already tainted**. It read untrusted content before
     spawning (the `TaintLedger`, ADR-0013), so anything it forwards into a subagent's
     instruction/context is suspect; **or**
   - **(b) the subagent is tools-enabled**. It holds the read-only MCP subset and can fetch
     untrusted content *itself*, so its own future taint is unknowable at spawn time; force the
     robust model conservatively.
3. **Therefore a cheap/weak model is reachable only for a tool-less subagent on an untainted
   turn** (a pure text transform over trusted material). Every path where untrusted content
   could reach a subagent runs the robust model, by construction, not by the cortex's judgment.
4. **The robust default tracks the ADR-0004 pick** (a config-level logical id, not a hard-coded
   model), so a future pick change moves the override with it.

## Consequences

- Untrusted content never reaches an injection-weak subagent model. This closes the residual the
  heterogeneous-roster design would otherwise open, the exact gap that made "the weak rows are
  moot" false.
- The cheap-fast models keep a **real but narrow** niche (trusted pure-text subtasks); 8.6's spec
  still advertises them to the cortex with their robustness trade-offs, so the cortex can choose
  them *there*. On an untrusted path the wiring overrides that choice.
- Additive behind the Slice 8.6 seams (spawn-tool spec, the `SubagentResources` roster, the
  `SubagentPlacer`): the override lives in the wiring/runner that selects a spawn's resources.
  CI-gated 100% over fakes, covering tainted-turn + weak-requested → robust resources; clean +
  tool-less + weak-requested → weak resources; tools-enabled + weak-requested → robust
  resources.

## Risks & notes

- **The case-2 subtlety, recorded so the implementer does not miss it.** The tainted-turn rule
  (2a) alone misses a subagent that reads untrusted content *itself*, since at that spawn the cortex
  turn is not yet tainted. Rule 2b covers that case by binding to tool-enablement, which is known
  structurally at spawn time. Both rules together form the constraint; neither alone does.
- **Deliberate loss** of the "cheap model for a trivial *untrusted* lookup" optimization, as that
  path is precisely what is being closed.
- **Per-role escape hatch, if ever justified:** a future subagent role needing a cheap model on
  a tainted/tool path for a proven-safe reason is a per-role override on the same seam, not a
  relaxation of the default.

## Composes with (deferred, separate)

- **Grammar-constrained subagent output** is schema-constrained decoding behind
  `InferenceBackend` (option (c) in the discussion): it prevents *format*-laundering (appended
  footers/links/sections) even on a weak model, for the narrow trusted-tool-less niche where one
  is still used. Orthogonal to this ADR; recorded in the ROADMAP for when 8.6 or a hardening
  pass needs it. This ADR is the *which-model* boundary; grammar constraint is the
  *what-shape-of-output* boundary.

## Addendum (2026-07-13): grammar-constrained output landed (ADR-0028)

The composes-with option (c) landed as [ADR-0028](ADR-0028-grammar-constrained-subagents.md):
an additive `schema` keyword on the unchanged `InferenceBackend` lets the `SubagentRunner`
decode a tool-less subagent's reply into a fixed `{"reply": "..."}` envelope, so
format-laundering has no grammatical position even on a weak model. It is gated to the
tool-less path, exactly the niche this ADR leaves a weak model reachable, so it composes with
the which-model boundary rather than touching it.
