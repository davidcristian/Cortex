# Why a schema restores a trace the same server just suppressed is unknown

**Status:** open, actionable
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
