# The reasoning budget is all or nothing

**Status:** done 2026-08-17
**Area:** inference-model-manager
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

Opened 2026-08-16 by the capped-reply work ([ADR-0048](../../adr/ADR-0048-generation-bounds.md)),
whose measurement covered this and could do nothing with it. On the shipped cortex an ordinary open
question spends 11.8 to 18.1 s before its first word, and every second of that is a deliberation of
2545 to 3064 characters, against 0.4 s and an answer of the same size with thinking off. So the
wait a user minds is the reasoning trace and not the reply, and what would fix it precisely is a
budget on the trace alone: think for this many tokens, then answer.

The entry said nothing available offers one, on the reading that `--reasoning-budget` takes 0 or -1
and does not work on this build, that the OpenAI request format bounds only the whole completion,
and that a client-side budget is worse than either extreme. Only the last of those survived.

Measured 2026-08-17 ([ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)). The
binary's own help reads `--reasoning-budget N: token budget for thinking: -1 for unrestricted, 0
for immediate end, N>0 for token budget`, and on the cortex pick it does exactly that: at 128 the
trace falls from 2323 to 2996 characters down to about 500 and the first word from 10.1 to 12.6 s
down to 1.7 to 2.6 s, the reply keeps its size, and every condition still finishes `stop`. It is
the engine closing the thought and letting the model answer, which is the one thing a client-side
cut cannot do. It also rescues the reply cap this repo shipped half usable: `max_tokens: 512`
returned an empty reply 3 of 3 against an unbounded trace, and 1488 to 1561 characters of answer
under a budget of 128.

What was built is that count as tier configuration, `CORTEX_REASONING_BUDGET` and
`CORTEX_REASONING_BUDGET_BRAIN`, rendering llama.cpp's own flag onto the tier's argv, with `-1` the
default and no flag emitted at all. Nothing crosses `InferenceBackend`: the engine reads the budget
per server and ignores it on a request, measured in both directions, so the port keeps saying
whether a request asks for deliberation while the tier says how long a requested one may be.

## History

- 2026-08-16: Opened by the capped-reply work, which measured the trace as the whole of the wait
  and then found no way to bound it separately. The two settings that were added,
  `CORTEX_REPLY_THINKING` and `CORTEX_REPLY_MAX_TOKENS`, are the two extremes this entry needs a
  middle of ([119](119-disable-thinking-token-budget.md)).
- 2026-08-17: Done as a per-tier trace budget, after checking the engine claim this entry rested on
  and finding it false: `--reasoning-budget` reads `N > 0` as a token budget on the image this repo
  runs, and `0` works too. The measured numbers and the argument for keeping it out of the port are
  in [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md). It opened two entries:
  one tier still has one budget ([295](295-per-request-trace-budget.md)), and what a bounded trace
  costs a hard answer is unmeasured ([296](296-trace-budget-quality-floor.md)).
