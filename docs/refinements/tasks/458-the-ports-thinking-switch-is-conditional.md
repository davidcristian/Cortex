# The port's thinking switch works on one request shape and does nothing on another

**Status:** done 2026-08-27
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

`GenerationBounds.thinking=False` is sent as `chat_template_kwargs: {"enable_thinking": false}`, and
its docstring said it asks the chat template to skip the model's deliberation entirely. Measured
against the shipped CPU subagent entry (gemma-4-E4B QAT q4_0 on
`ghcr.io/ggml-org/llama.cpp:server`), that was true of a plain request and false of one with a
`response_format`: the same prompt, server and key returned a reasoning trace and no reply text,
while `--reasoning-budget 0` on the server suppressed the trace completely.

Four shipped bounds pair `thinking=False` with a cap sized on the answer: `TITLE_BOUNDS`,
`RECAP_BOUNDS`, the rerank judge's bounds in `rerank_judge.py`, and the cortex turn's
`TurnCapabilities.bounds`. The judge's is the one that also sends a schema (`ORDER_ENVELOPE`),
which is the pairing the subagent tier's defect was made of. A cap on a reasoning model whose trace
is still running deletes the reply instead of shortening it.

## History

- 2026-08-26: opened by the close of
  [R-456](456-a-constrained-request-loses-the-thinking-lever.md), as the residue of a fix that was
  built on this switch, measured to do nothing, and reverted.
- 2026-08-27: closed, with the paragraph above corrected on its own subject. A new committed probe
  ran both shipped picks with neither `--chat-template-kwargs` nor `--reasoning-budget`, sending
  one prompt four ways. The E4B template does read the kwarg (654 characters of trace without the
  switch, none with it, on a plain request), and it is the `response_format` that costs the switch
  its effect (599 without, 664 with). The cortex pick honours it in both shapes (735 / 0 and
  685 / 0). So the request shape decides it, not the template; the earlier reading had taken the
  plain case on a prompt that produced no trace either way. All four shipped bounds were re-measured
  live on the unbudgeted cortex tier and each is still the cheaper option (title 0.3 s against
  4.1 s, recap 2.2 s against 8.2 s, rank 0.8 s per question against 7.5 s at an unchanged MRR of
  1.000). What changed is the documentation and the evidence: `GenerationBounds.thinking` is now
  documented as a request and not a guarantee, `InferenceBackend` must pass a trace that arrived
  despite the switch to the caller as a `ReasoningChunk` rather than dropping it, checked by a
  shared contract test over the fake and the real adapter, and `drain_text` warns with the model
  and the number of characters it dropped unread. Recorded in ADR-0049, which also corrected
  ADR-0010 and ADR-0038. Opened by it:
  [R-464](464-why-a-grammar-restores-the-trace.md),
  [R-465](465-the-switch-across-the-lineup.md) and
  [R-466](466-nothing-holds-a-cap-to-a-bounded-trace.md).
