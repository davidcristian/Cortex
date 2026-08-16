# The reasoning budget is all or nothing

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a build of llama.cpp, or a request field it accepts, that bounds `reasoning_content` by a token count rather than switching it off.

Opened 2026-08-16 by the capped-reply landing
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) capped-reply addendum), which measured the
thing this entry is about and then could do nothing with it. On the shipped cortex an ordinary
open question spends 11.8 to 18.1 s before its first word, and every second of that is a
deliberation of 2545 to 3064 characters, against 0.4 s and an answer of the same size with
thinking off. So the wait a user minds is the trace and not the reply, and the bound that would
fix it precisely is a budget on the trace alone: think for this many tokens, then answer.

Nothing in reach offers one. `--reasoning-budget` is a per-server switch taking 0 or -1, not a
count, and it does not work on this build at all, which is why the per-request
`chat_template_kwargs: {"enable_thinking": false}` is the only lever that does. The OpenAI request
surface llama-server accepts has `max_tokens`, which bounds the whole completion, and a reasoning
model spends its budget on thinking first: measured on this same cortex, `max_tokens: 512` with
thinking left on returned an EMPTY reply 3 of 3 under traces of 1465 to 2126 characters. So the
two settings this repo now offers are the two ends of one dial with nothing in between, and a
deployment that wants a short think and a full answer has to choose between a full think and no
think at all.

**What would close it, and why none of it was taken now.** Waiting on the engine is the honest
answer for the per-request half, since a field the server does not read cannot be sent. What this
repo could build without it is a client-side budget: stop the stream when the `ReasoningChunk`
count passes a bound and re-ask with thinking off, which spends the whole trace's time and then
some, or cut the completion outright, which is the empty reply above wearing a different hat.
Both are worse than either end of the dial, so the entry waits rather than building one.

## Trail

- 2026-08-16: Opened by the capped-reply landing, which measured the trace as the whole of the
  wait and then found no way to bound it separately. The two levers that did land,
  `CORTEX_REPLY_THINKING` and `CORTEX_REPLY_MAX_TOKENS`, are the ends of the dial this entry wants
  a middle of ([119-disable-thinking-token-budget.md](119-disable-thinking-token-budget.md)).
