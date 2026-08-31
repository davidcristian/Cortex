# Why a schema restores a trace the same server just suppressed is unknown

**Status:** landed 2026-08-28
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-27 by the close of
[R-458](458-the-ports-thinking-switch-is-conditional.md), whose measurement is a fact with no
mechanism under it.

On the shipped subagent pick (gemma-4-E4B QAT q4_0) with no server-side reasoning flags at all, one
prompt sent four ways to one server gives 654 characters of trace with no switch and none with it
on a plain request, then 599 with no switch and **664 with it** once the request carries a
`response_format`. The switch is the same key, the server is the same process, and the minute is the
same minute. Nothing in this repo can say why.

What the same probe rules out is the easy answer. On the cortex pick (gemma-4-12B QAT q4_0), same
build and same adapter, the constrained arm with the switch writes no trace at all, so a
`response_format` does not cost a request its `chat_template_kwargs` on the way in. The key arrives
and something downstream of it differs by pick.

**Why it was left.** The measurement is what the port needed: whatever the cause, the field is
advisory and the dependable bound is the tier's `--reasoning-budget`, which is what ships. Naming
the cause changes no code today.

**Why it is worth knowing anyway.** It decides whether a deployment can ever have the cheap lever
back on the constrained shape, and it is the difference between a model behaviour (the pick
deliberates under a grammar because that is what it does) and an engine one (llama.cpp resolves a
different chat format, or forces the thought open, when a JSON schema is in play). Only the second
has a fix.

**What would close it.** Read the engine's side rather than the wire's: which `common_chat_format`
llama.cpp resolves for each pick with and without a `json_schema`, whether the reasoning section is
forced open in that path, and whether the rendered prompt differs between the two shapes. The
server can be asked for the applied template (`GET /props`), and a build's own verbosity prints the
format it chose, so this is a reading rather than a study. Either answer belongs in the ADR-0005
switch-is-advisory addendum, whose fourth reading is deliberately the small one because this is
unknown.

## Trail

- 2026-08-27: opened by the close of
  [R-458](458-the-ports-thinking-switch-is-conditional.md), as the mechanism under a fact that
  entry measured and could not explain.
- 2026-08-28: Landed. The phenomenon reproduces on llama.cpp `b10644-d7a207411`, and the repeats
  correct it before the mechanism does: at five draws a cell rather than one, the E4B's constrained
  arm with the switch deliberates on **4 of 5** rather than every time, so the recorded reading was
  a tendency written as a rule. Every other cell of both picks is 5 of 5 the way it was recorded.
  **It is an engine behaviour, and the model is doing nothing surprising.** All three of the entry's
  questions answer the same way. The chat format does not change: `peg-gemma4` on all 54 requests,
  schema or none. The rendered prompt does not change either, asked of each server through
  `POST /apply-template`: for one pick and one value of the switch the two request shapes render
  byte-identical prompts, so the key reaches the template under a schema exactly as it does without
  one. What a schema changes is that llama.cpp builds a grammar at all, and the gemma-4 handler's
  root for one is a `start`, then an optional `thought`, then the fenced JSON payload, and it is
  byte-identical across both picks and both values of the switch. It does not **force** the thought
  open; it **holds** it open, as the only continuation that admits prose. That handler never reads `enable_thinking`, while sibling handlers
  in the same file gate their reasoning rule on it, so the omission is per handler rather than a
  property of constrained decoding. The split between the picks is then the **template**: with the
  switch sent, the cortex's renders a pre-closed empty thought (`<|channel>thought` then
  `<channel|>`) and the E4B's renders nothing, so on the constrained shape one pick's thought block
  is already closed and the other's is open.
  Written into the ADR-0005 switch-is-advisory addendum as its mechanism section, which also
  qualifies that addendum's first reading and its one-draw table. The committed probe now draws each
  cell `CORTEX_THINKING_REPEATS` times and reads the rendered prompt for all four shapes ahead of
  them, asserting that one switch renders one prompt, so the half of the engine's side that is
  free over HTTP is now a line of its output rather than a session's notes.
  Opened by it: [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md). Naming the cause
  turned up the lever: this build reads `reasoning_budget_tokens` off the request body, and sent as
  zero on the exact failing cell it holds 5 draws of 5, while the name this repo recorded as
  ignored, `reasoning_budget`, is still ignored on the same build in the same minute.
