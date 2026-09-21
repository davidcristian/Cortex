# ADR-0049: The thinking switch and the trace budget

**Status:** Accepted (2026-09-19)

## Context

Every chat model in the lineup ([ADR-0004](ADR-0004-model-lineup.md)) is a reasoning model: before
its answer it may write a trace, which llama.cpp returns as `reasoning_content` and the adapter
passes on as `ReasoningChunk`. On a user's reply the trace is the wait before the first word: on the
cortex pick, turning it off brought the first word forward by more than an order of magnitude with
the reply the same size. Where a cap is sized on the wanted answer, an unbounded trace uses up the
cap and the reply comes back empty rather than short.

llama.cpp offers two controls, and they do not behave alike.

- **The template switch**, `enable_thinking: false`, sent per request as `chat_template_kwargs` or
  per server as `--chat-template-kwargs` (written `--reasoning off` on current builds). It changes
  the rendered prompt, and what a pick's template does with it decides whether it works. Under a
  JSON schema the engine builds a grammar that keeps a thought block reachable, and a template that
  responds to the switch by leaving the thought open lets the model write one anyway.
- **The sampler budget**, `--reasoning-budget N` per server or `reasoning_budget_tokens` per request
  on builds that parse it. It watches for a thought's start sequence and forces its end tag, so it
  applies to every request shape, but only to a thought whose start it sees generated.

How each control behaves per pick is measured in [thinking switch](../readings/thinking-switch.md);
how those measurements are taken is [ADR-0050](ADR-0050-live-probe-records.md).

## Decision

### The port

1. **`GenerationBounds.thinking` is a request, not a promise.** It renders as
   `chat_template_kwargs: {"enable_thinking": false}` or as nothing, and is honoured or not per pick
   and per request shape. The rule it serves is that a cap sized on the wanted answer needs a
   bounded trace; the switch is the cheapest source of one and not a dependable one.
2. **`GenerationBounds.trace_tokens` is the per-request budget.** `0` ends the deliberation at once,
   a positive count lets it run that far and closes it, and `None` leaves the tier's own
   `--reasoning-budget` deciding; a negative count raises rather than passing the engine's `-1`
   through the port. It renders as `reasoning_budget_tokens`, a zero included. The older name
   `reasoning_budget` is ignored by the engine, and the working alias `thinking_budget_tokens` is
   not sent. The wire name is one entry of the constant registry (`scripts/tracecouplings.py`,
   [ADR-0042](ADR-0042-cross-tree-constant-registry.md)).
3. **The switch and the count are independent, and neither is derived from the other.**
   `thinking=False` says the caller will not read the trace; `trace_tokens=0` says it must not be
   generated. A cortex turn renders its trace as the thinking status the overlay shows
   ([ADR-0020](ADR-0020-reasoning-status.md)), so a zero inferred from the switch would blank it.
   One test at the payload and one at the deployment's producer check this.
4. **The port passes both on and enforces neither.** A trace that arrives against the switch, or
   despite a budget of zero, still crosses as `ReasoningChunk`; the shared contract checks it with
   `check_a_deliberation_the_request_asked_against_still_crosses` and
   `check_a_trace_the_request_budgeted_away_still_crosses`. That trace is the only evidence a caller
   has that its request went unhonoured, so no adapter filters it.

### Who asks for what

5. **The three side calls set a zero.** `TITLE_BOUNDS`, `RECAP_BOUNDS` and `rank_bounds(k)` set
   `thinking=False` and `trace_tokens=0`: `drain_text` discards their trace unread, so there is
   nothing to lose and a whole cap to win back. `drain_text` logs a warning naming the model and the
   character count when a completion deliberated against the switch, and returns the text unchanged,
   because the repair is a tier flag an operator sets. The rank is the one of the three that also
   sends a schema, and it runs against the cortex.
6. **A user's reply takes its settings from `ReplyBoundsConfig`** (`config_reply.py`):
   `CORTEX_REPLY_THINKING` (default true), `CORTEX_REPLY_MAX_TOKENS` (default 0, no cap) and
   `CORTEX_REPLY_TRACE_TOKENS` (unset by default; zero is a real setting, so unset is not the falsy
   value). With none set the bounds are `None` and the request is the one the repo always sent. The
   value reaches the core on `TurnCapabilities`, and the deep phase of a handoff inherits it, so one
   count bounds both traces of an escalated turn; a deployment that wants them bounded apart uses
   the two tier flags. No default flips: thinking on is what the deep pick was chosen for. The
   runbook documents the cap and a bounded trace as a pair, since a cap with the trace unbounded is
   no answer. The turn gains no warning like the drain's, the overlay already showing the trace.
7. **The cortex and deep tiers each take a server budget.** `CORTEX_REASONING_BUDGET` and
   `CORTEX_REASONING_BUDGET_BRAIN` reach `ModelHostConfig` and render as `--reasoning-budget N` on
   that tier's argv. `-1`, llama.cpp's word for unrestricted, is the default and emits no flag; `0`
   is a real setting and reaches the argv. Two settings, because the cortex replies while somebody
   watches and the deep pick was chosen for reaching an answer inside its trace. The runbook's
   advice is to start at 512 on a tier a user reads.
8. **Every subagent server sets both the template switch and the sampler zero**:
   `--chat-template-kwargs '{"enable_thinking": false}'` and `--reasoning-budget 0`, in both
   subagent compose files and in the model host's `_SUBAGENT_TAIL`, enforced as one requirement by
   `scripts/flagcheck.py` ([ADR-0043](ADR-0043-subagent-server-flags.md)). Each model family needs a
   different half. On the gemma-4-E picks the kwarg renders the thought away; the budget alone
   empties the reasoning channel but the thought then arrives inside the reply and more answers are
   lost, most of them reported as answers. On the Qwen picks the kwarg renders the thought already
   closed, and the budget alone does nothing, because the template opens the thought inside the
   prompt and the sampler never sees it start. Beside the kwarg the budget has no effect on the
   gemma pick, draw for draw, and the pair stays because no per-family flag set measured better.
   When the kwarg stops parsing, the replacement is `--reasoning off`, which rendered and drew
   identically, with the budget kept beside it.
9. **The delegated path sets no count.** `PlacedAttempt` sends `GenerationBounds(max_tokens=...)`
   and nothing else: a request zero on top of the tier's flag measured identical to the flag alone.
   A per-request thinking key on the constrained attempt was built, measured with no effect, and
   reverted.
10. **Two defects of the pair are recorded and not repaired in the core.** On the gemma-4-E picks,
    some draws of the shipped delegated request open the reasoning channel with a misspelled closing
    marker and write the answer there, coming back empty at the cap: the model's own attempt to
    close a thought on a prompt rendered without the token that opens one, reproduced with no
    sampler set anywhere. And a forced end of thought can leak its start tag into an answer
    (`{"reply": "thought"}` parses and is reported as the subtask's answer), rarely, with the
    request key and the tier flag alike. Stripping a marker needs the core to know a per-pick
    template token, which is what the port exists not to know, and a shape rule cannot tell a
    one-word answer from a defect. What removes both is the pick, a lineup decision
    ([ADR-0028](ADR-0028-grammar-constrained-subagents.md)): no Qwen entry writes to that channel.

### Whether the engine reads the request key

11. **`CORTEX_INFERENCE_TRACE_LEVER` is `auto` (the default), `on` or `off`.** `auto` asks the
    cortex endpoint once, in `build_inference_backend` (`resolve_trace_lever`,
    `reads_a_trace_budget` in `trace_probe.py`): a request sending `reasoning_budget_tokens: -2` is
    answered 400 naming the key by a build that parses it, since the engine range-checks the value
    before decoding, and 200 by one that ignores it. Only a well-typed out-of-range integer triggers
    the check. Every other answer, an unreachable server included, is no, and the request then sends
    no budget. `GET /props` does not answer the question, and its `build_info` is only a proxy for
    it. `on` and `off` fix the answer and open no socket. The probe is bounded by
    `TRACE_LEVER_PROBE_TIMEOUT_S` (5 s), well above the sub-second answer measured on the slowest
    tier the repo ships.
12. **The answer is taken once per startup and covers the deep tier.** Whether the engine reads a
    key is a property of a binary, which changes only with the image, where vision is a property of
    an argv and is asked on every capture. A llama.cpp image pulled under a running brain needs a
    brain restart, which the GPU runbook says; an older answer withholds a key rather than sending
    one nothing reads. Re-asking at a model swap is not built: the only such boundary starts another
    child of the same image and exists only with `CORTEX_ESCALATION` on.
13. **A count that is withheld is reported once.** A `LlamaCppBackend` built with the control off
    logs one `WARNING`, `trace budget not sent because the trace lever is off`, with `model` and
    `trace_budget`, on the first request whose count goes unsent, and nothing after. The field is
    not `trace_tokens` because the log sink withholds any field whose name contains `token`. A zero
    sent beside `thinking=False` is not reported, the drain already covering that request; a zero
    with the switch left on is. A count the engine accepted and ignored cannot occur on a probed
    deployment, and one honoured at a different number could only be guessed from a
    characters-per-token rate, so neither is reported.

### What is not built

14. **No template probe ships in a deployment.** A pick's rendered tail predicts whether the switch
    works under a schema, correct on every lineup entry, but it is a measurement of one engine
    build's handlers, and recognising a closed thought needs per-pick tokens. The side calls' zeros
    already repair the one shipped hazard. The cortex tier runs no sampler minimum and sends the one
    bound that also has a schema, so its safety rests on the request key or on the cortex pick's
    template, which renders the thought closed.
15. **No client-side budget and no budget message.** Stopping the stream and re-asking generates the
    trace and only then buys the thinking-off answer; cutting the completion is the empty reply;
    neither can close the thought. `--reasoning-budget-message` works but its sentence ends up in
    `reasoning_content`, which the overlay shows as the model's own thinking.

### The injection test's switch rows

16. **The test reads each control off the tier's own argv tail by the flag's name.**
    `lever(argv, flag)` returns the flag and the value after it and raises at import when the tail
    lacks the flag; no value of the pair is typed into the test. The budget alone is its own
    `SWITCHES` row (`BUDGET_ALONE`), shown on the table, and `test_switch_rows.py` requires the rows
    to differ by the control alone. The kwarg alone has no row: on the plain request the test posts,
    it renders what the request-key row renders.

## Consequences

- Nothing requires a new side call to set the zero the three set, or a future cap-and-switch bound
  to run on a tier whose trace is bounded; the drain's warning reports the failure when it happens.
- A tier flag an older build does not know fails that server at startup rather than being ignored.
- A reply cap on a deployment whose probe answered no is bounded only by the tier's own flag.
- What a bounded trace costs the answer is not measured. The side calls' zeros rest on their trace
  being discarded unread, not on a measurement of what it was worth.

## Alternatives rejected

- **The per-request thinking key on the constrained delegated attempt**: measured with no effect.
- **The budget as tier configuration only**: the engine now reads it per request, and two callers on
  one tier can want different counts.
- **Filtering a trace in the adapter to make the port look truthful**: forbidden by decision 4.
- **A constant or `build_info` comparison as the probe's test**: the tags float under the stack.
- **A per-family flag set on subagent servers**: measured worse on both families.
- **A constructor rule refusing a cap without a count, or a default bounding the cortex trace**: the
  first rejects one safe caller and one person's setting, the second blanks the thinking status.
- **A second reply count for the deep tier**: a setting for a case no deployment has reached; the
  tier flags already express the split.

## Related

- [ADR-0004](ADR-0004-model-lineup.md), [ADR-0005](ADR-0005-llamacpp-engine.md),
  [ADR-0010](ADR-0010-subagents.md), [ADR-0020](ADR-0020-reasoning-status.md),
  [ADR-0028](ADR-0028-grammar-constrained-subagents.md),
  [ADR-0043](ADR-0043-subagent-server-flags.md), [ADR-0048](ADR-0048-generation-bounds.md),
  [ADR-0050](ADR-0050-live-probe-records.md).
- Module contracts: [brain-inference](../modules/brain-inference.md),
  [brain-core](../modules/brain-core.md), [brain-orchestrator](../modules/brain-orchestrator.md),
  [brain-model-manager](../modules/brain-model-manager.md).
- Runbooks: [llamacpp-gpu](../runbooks/llamacpp-gpu.md),
  [subagents-cpu](../runbooks/subagents-cpu.md).
- Readings: [thinking switch](../readings/thinking-switch.md).
