# The port's thinking switch could be sent as a request value the engine applies

**Status:** done 2026-08-29
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

`GenerationBounds(thinking=False)` is sent as `chat_template_kwargs: {"enable_thinking": false}` and
nothing else, which is a hint to the deployment's chat template. On a request with a
`response_format` that hint is overruled by the grammar llama.cpp builds, so on the shipped subagent
pick the switch works only sometimes: 4 draws in 5 deliberate through it and spend the whole of a
paired cap on the trace, which deletes the reply rather than shortening it.

Measured on `ghcr.io/ggml-org/llama.cpp` `b10644-d7a207411`, the same request can send
`reasoning_budget_tokens` (or `thinking_budget_tokens`), which the server reads off the body and
falls back to the tier's `--reasoning-budget` for only when the request says `-1`. Sent as `0` on
the exact cell that fails, the switch works on 5 draws of 5, each returning the envelope. It is a
sampler rather than a prompt or a grammar: it detects the thought's start sequence and forces its
end tag, so it reaches every request shape. The name this repo tried and recorded,
`reasoning_budget`, is genuinely ignored on the same build in the same minute.

[R-295](295-per-request-trace-budget.md) records the other half of the same engine fact, a positive
count per request rather than a zero, and names this build as what it was waiting for.

## History

- 2026-08-28: opened by the close of [R-464](464-why-a-grammar-restores-the-trace.md), which went
  looking for the cause of a switch that does nothing under a schema and found a request value that
  works.
- 2026-08-29: closed as ADR-0049, which included
  [R-295](295-per-request-trace-budget.md), both being one key on one payload. `GenerationBounds`
  gained `trace_tokens`, sent as `reasoning_budget_tokens`; the three side calls whose trace
  `drain_text` discards each send a zero, and a user's own reply sends nothing unless
  `CORTEX_REPLY_TRACE_TOKENS` says so. The port's wording about the switch being advisory moved with
  it, and the shared contract list gained an eleventh test: a trace that arrived despite a budget of
  zero still reaches the caller, since a count is a stronger instruction than a hint. The three open
  questions were answered. The minimum build is checked by probing the running server
  (`CORTEX_INFERENCE_TRACE_LEVER=auto|on|off`, the same shape `CORTEX_VISION` has) rather than by a
  deployment setting alone, because the images this repo names are mutable tags and the build under
  this repo had already moved from `b10644-d7a207411` to `b10666-4e97ac86e`. The trace a user reads
  is protected by a rule: nothing derives a count from the switch, and two tests assert that. The
  leaked start tag reproduced once in 58 budgeted draws and is worse than this entry supposed: it
  arrives inside the envelope (`{"reply": "thought"}`), so nothing rejects it and a delegated run
  reports the leaked tag as the answer. The same sampler as a tier flag did not do it in 20 draws,
  so it reads as a rare engine behaviour the request key inherits rather than adds. No repair
  shipped, since one would need the core to know a per-pick template token. Two of this entry's own
  numbers were better than the close's first reading: its failing cell at 4 draws in 5 was read as
  5 of 5 on five draws before twenty draws said 17 of 20, and the leak shape it described, a reply
  beginning with the leaked word, is the one that did not appear. Opened by it:
  [R-495](495-the-forced-thought-can-leak-its-own-start-tag.md),
  [R-496](496-the-trace-budget-probe-runs-once-per-boot-and-is-never-repeated.md),
  [R-497](497-nothing-reports-a-trace-budget-that-went-unread.md) and
  [R-498](498-one-reply-trace-budget-for-two-tiers.md).
