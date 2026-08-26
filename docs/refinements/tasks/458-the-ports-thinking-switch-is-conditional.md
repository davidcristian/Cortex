# The port's thinking switch holds on one request shape and silently does nothing on another

**Status:** landed 2026-08-27
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-26 by the close of
[R-456](456-a-constrained-request-loses-the-thinking-lever.md), whose fix was built on this switch
and had no effect.

`GenerationBounds.thinking=False` renders as `chat_template_kwargs: {"enable_thinking": false}`, and
its docstring says it "asks the chat template to skip the model's deliberation entirely". Measured
against the shipped CPU subagent entry (gemma-4-E4B QAT q4_0 on `ghcr.io/ggml-org/llama.cpp:server`),
that is true of a plain request and false of one carrying a `response_format`: the same prompt,
the same server and the same key returned a reasoning trace and no reply text either way, while
`--reasoning-budget 0` on the server suppressed it completely. The reason is on the template rather
than on the request, ADR-0010 having recorded that the kwarg "is ignored by non-reasoning templates
like gemma-4-E\*", so what the field really does is deployment-dependent in a way no caller can see.

**Why this is more than the entry that opened it.** Four shipped bounds pair `thinking=False` with a
cap sized on the answer: `TITLE_BOUNDS`, `RECAP_BOUNDS`, the rerank judge's
`GenerationBounds(max_tokens=RANK_ENVELOPE_TOKENS + RANK_TOKENS_PER_CANDIDATE * k, thinking=False)`,
and the cortex turn's own `TurnCapabilities.bounds`. The judge's is the one that also carries a
schema (`ORDER_ENVELOPE`), which is the exact pairing the subagent tier's defect was made of. Each
cap is sized on the length of the answer wanted, which is the pairing rule this ADR keeps: a cap on
a reasoning model with the trace still running deletes the reply rather than shortening it.
`rerank_judge.py` already carries a comment about "a reasoning tier ignoring `thinking=False`", so
the possibility is written down in one place and measured in none. None of those four has been run
against a tier whose template ignores the kwarg, and the cortex pick is a gemma, the same family.

**What would close it.** Run each of the four shapes against the shipped cortex tier with the trace
left unbudgeted and read whether the reply survives its cap. Then say in the port's own docstring
what the field is: a request for a template that reads it, and not a guarantee. If the answer is
that the cortex family ignores it too, the honest repair is the one the subagent tier just took, a
tier-level `--reasoning-budget` the deployment sets, and the field's docstring should point at it.

## Trail

- 2026-08-26: opened by the close of
  [R-456](456-a-constrained-request-loses-the-thinking-lever.md), as the residue of a fix that was
  built on this switch, measured to do nothing, and reverted.
- 2026-08-27: Landed, with **the paragraph above corrected on its own subject**. The claim in the
  title is right and its stated reason is wrong, and so was the correction R-456 replaced it with.
  Measured through a new committed probe against both shipped picks, each server started with
  neither `--chat-template-kwargs` nor `--reasoning-budget`, one prompt sent four ways: the E4B
  template **does** read the kwarg, writing 654 characters of trace without the switch and none
  with it on a plain request, and it is the `response_format` that costs the switch its effect (599
  without, **664 with**). The cortex pick honours it in both shapes (735 / 0 and 685 / 0). So it is
  the request's shape after all, and not the template, and the reading that concluded otherwise had
  taken its plain arm on a prompt that produced no trace even with no switch set, which cannot tell
  a suppressed deliberation from an absent one. The probe asserts that control now.
  The four shipped bounds are safe where they run: all four were re-measured live on the unbudgeted
  cortex tier, the rank's cap-plus-schema-plus-switch included, and each is still the cheap arm
  (title 0.3 s against 4.1 s, recap 2.2 s against 8.2 s, rank 0.8 s per question against 7.5 s at an
  unchanged MRR of 1.000).
  What landed is the honesty rather than a behaviour change: `GenerationBounds.thinking` is
  documented as a request and not a guarantee, with the pairing rule restated as needing a bounded
  trace; `InferenceBackend` now owes the caller the evidence, a trace that arrived despite the
  switch crossing as `ReasoningChunk` rather than being filtered away, held by a shared contract
  check over the fake and the real adapter; and `drain_text`, the one place that sees both the
  request that asked and the trace that came back, warns with the model and the characters it
  dropped unread. Recorded in the ADR-0005 switch-is-advisory addendum, which also corrects the
  thinking-lever addendum above it, ADR-0010's parenthesis about gemma-4-E\* templates, and
  ADR-0038's line about `--reasoning-budget`.
  Opened by it: [R-464](464-why-a-grammar-restores-the-trace.md) (the mechanism under the reading is
  still unknown), [R-465](465-the-switch-across-the-lineup.md) (two picks are not a rule) and
  [R-466](466-nothing-holds-a-cap-to-a-bounded-trace.md) (the pairing is reported at runtime and
  still held by nothing).
