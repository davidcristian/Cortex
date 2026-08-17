# The reasoning budget is all or nothing

**Status:** landed 2026-08-17
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-16 by the capped-reply landing
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) capped-reply addendum), which measured the
thing this entry is about and then could do nothing with it. On the shipped cortex an ordinary
open question spends 11.8 to 18.1 s before its first word, and every second of that is a
deliberation of 2545 to 3064 characters, against 0.4 s and an answer of the same size with
thinking off. So the wait a user minds is the trace and not the reply, and the bound that would
fix it precisely is a budget on the trace alone: think for this many tokens, then answer.

The entry as written said nothing in reach offers one, on the reading that `--reasoning-budget`
takes 0 or -1 and does not work on this build, that the OpenAI request surface bounds only the
whole completion, and that a client-side budget is worse than either end of the dial. Only the
last of those survived.

**What the engine actually offers, measured 2026-08-17
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) trace-budget addendum).** The binary's own help
reads `--reasoning-budget N: token budget for thinking: -1 for unrestricted, 0 for immediate end,
N>0 for token budget`, and on the cortex pick it does exactly that: at 128 the trace falls from
2323 to 2996 characters to about 500 and the first word from 10.1 to 12.6 s to 1.7 to 2.6 s, the
reply keeps its size, and every arm still finishes `stop`. It is the engine closing the thought and
letting the model answer, which is the one thing a client-side cut cannot do, and it is why the
rejected client-side options stay rejected. It also rescues the cap this repo shipped half usable:
`max_tokens: 512` returned an empty reply 3 of 3 against an unbounded trace and 1488 to 1561
characters of answer under a budget of 128.

**What landed** is that count as tier configuration, `CORTEX_REASONING_BUDGET` and
`CORTEX_REASONING_BUDGET_BRAIN` rendering llama.cpp's own flag onto the tier's argv, with `-1` the
default and no flag emitted at all. Nothing crosses `InferenceBackend`: the engine reads the budget
per server and ignores it on a request, measured in both directions, so the port keeps saying
whether a request wants deliberation while the tier says how long a wanted one may be.

## Trail

- 2026-08-16: Opened by the capped-reply landing, which measured the trace as the whole of the
  wait and then found no way to bound it separately. The two levers that did land,
  `CORTEX_REPLY_THINKING` and `CORTEX_REPLY_MAX_TOKENS`, are the ends of the dial this entry wants
  a middle of ([119-disable-thinking-token-budget.md](119-disable-thinking-token-budget.md)).
- 2026-08-17: Landed as a per-tier trace budget, after re-deriving the engine claim this entry
  rested on and finding it false: `--reasoning-budget` reads `N > 0` as a token budget on the image
  this repo runs, and `0` works too, so the lever the entry waited for was already in the box. The
  measured dial and the argument for keeping it out of the port are in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) trace-budget addendum. What the close opens is
  that one tier still has one budget
  ([295-per-request-trace-budget.md](295-per-request-trace-budget.md)) and that what a bounded
  trace costs a hard answer is unmeasured
  ([296-trace-budget-quality-floor.md](296-trace-budget-quality-floor.md)).
