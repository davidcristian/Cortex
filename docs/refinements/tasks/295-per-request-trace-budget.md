# One tier still has one thinking budget

**Status:** done 2026-08-29
**Area:** inference-model-manager
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

Opened 2026-08-17 by the trace budget
([ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)), which gave the thinking
setting a middle value and could only fit it per server.

`CORTEX_REASONING_BUDGET` is a flag on a tier's `llama-server`, so every request that tier serves
thinks under the same count. That covered the cases this repo has, because the passes whose
deliberation is thrown away unread already say so per request and get a trace of zero: the history
summary, the session title and the recall rank all send `thinking=False`, and a budget of any size
leaves them alone (measured: 0 characters of trace under a tier budget of 128). What it cannot
express is two positive budgets on one tier.

The engine was what held it shut, measured in both directions: a request with `reasoning_budget:
128` was ignored on an unbudgeted server, and one with `reasoning_budget: -1`, at the top level and
inside `chat_template_kwargs` alike, did not raise a budgeted server's own count. Measured again
2026-08-28 on `ghcr.io/ggml-org/llama.cpp` `b10644-d7a207411`, the server reads
`reasoning_budget_tokens` (or `thinking_budget_tokens`) off the request body and falls back to the
tier's flag only when the request says `-1`. The earlier reading was right about the name it sent:
`reasoning_budget` is ignored on that same build in the same minute, logged as `tokens=-1` on every
draw.

The shape this entry predicted is the shape that shipped: `GenerationBounds` gained a third number,
`build_payload` renders it, and the tier flag became the deployment's default rather than its only
setting. The summary, the title and the recall rank each send a zero and a user's reply sends
whatever `CORTEX_REPLY_TRACE_TOKENS` names, all on the one resident cortex. Measured per request on
one unbudgeted server: unbounded spent 591 to 854 characters of trace and returned nothing inside a
cap of 256, `reasoning_budget_tokens: 128` spent 310 to 516 and returned an answer, and `32` spent
0 to 92 and returned a longer one. What the change adds beyond this entry's design is a check under
the key, since a build that does not read it ignores it without error.

## History

- 2026-08-29: Done as ADR-0049, together with the close of
  [R-474](474-the-ports-thinking-switch-could-be-sent-as-a-request-value.md), the two being one key on one
  payload read twice. The engine half of the trigger had come true the day before. The residue is
  on that entry's history: [R-495](495-the-forced-thought-can-leak-its-own-start-tag.md),
  [R-496](496-the-trace-budget-probe-runs-once-per-boot-and-is-never-repeated.md),
  [R-497](497-nothing-reports-a-trace-budget-that-went-unread.md) and
  [R-498](498-one-reply-trace-budget-for-two-tiers.md).
