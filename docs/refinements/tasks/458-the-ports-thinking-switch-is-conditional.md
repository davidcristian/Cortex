# The port's thinking switch holds on one request shape and silently does nothing on another

**Status:** open, actionable
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
