# Why a schema restores a trace the same server just suppressed is unknown

**Status:** done 2026-08-28
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

On the shipped subagent pick (gemma-4-E4B QAT q4_0) with no server-side reasoning flags, one prompt
sent four ways to one server gave 654 characters of trace with no switch and none with it on a
plain request, then 599 with no switch and 664 with it once the request included a
`response_format`. Same key, same process, same minute, and nothing in this repo could say why.

The same probe ruled out the easy answer. On the cortex pick (gemma-4-12B QAT q4_0), same build and
same adapter, the constrained run with the switch wrote no trace at all, so a `response_format`
does not strip a request's `chat_template_kwargs` on the way in.

The answer decides whether a deployment can ever use the cheap switch on the constrained shape, and
it separates a model behaviour from an engine one. Only the second has a fix.

## History

- 2026-08-27: opened by the close of
  [R-458](458-the-ports-thinking-switch-is-conditional.md), as the mechanism under a fact that
  entry measured and could not explain.
- 2026-08-28: closed. The behaviour reproduces on llama.cpp `b10644-d7a207411`, and repeating each
  cell five times corrects the reading: the E4B's constrained run with the switch deliberates on
  4 of 5 rather than every time, so the recorded result was a tendency written as a rule. Every
  other cell of both picks is 5 of 5 as recorded. It is an engine behaviour. The chat format does
  not change: `peg-gemma4` on all 54 requests, schema or none. The rendered prompt does not change
  either, asked of each server through `POST /apply-template`: for one pick and one value of the
  switch, the two request shapes render byte-identical prompts. What a schema changes is that
  llama.cpp builds a grammar at all, and the gemma-4 handler's root for one is a `start`, then an
  optional `thought`, then the fenced JSON payload, byte-identical across both picks and both
  values of the switch. It leaves the thought open as the only continuation that admits prose. That
  handler never reads `enable_thinking`, while sibling handlers in the same file do, so the
  omission is per handler rather than a property of constrained decoding. The difference between
  the picks is the template: with the switch sent, the cortex's renders a pre-closed empty thought
  (`<|channel>thought` then `<channel|>`) and the E4B's renders nothing, so on the constrained
  shape one pick's thought block is already closed and the other's is open. Written into ADR-0049
  and the thinking-switch readings, which also qualify the first one-draw table. The committed
  probe now repeats each cell `CORTEX_THINKING_REPEATS` times and reads the rendered prompt for all
  four shapes first, asserting that one switch renders one prompt. Opened by it:
  [R-474](474-the-ports-thinking-switch-could-be-sent-as-a-request-value.md), because this build reads
  `reasoning_budget_tokens` off the request body, and sent as zero on the exact failing cell it
  suppresses the trace on 5 draws of 5, while `reasoning_budget`, the name this repo recorded as
  ignored, is still ignored on the same build in the same minute.
