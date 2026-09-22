# A forced end of thought can deliver its own start tag as the answer

**Status:** open, waiting for its trigger
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-09-15
**Trigger:** a delegated run whose answer is one word, or a budgeted cell of the committed probe
counting two or more leaks in a hundred draws, on any tier that ends a thought at the engine.

A trace budget is a sampler: it detects the thought's start sequence and forces its end tag, so the
forcing necessarily happens after the start has been written. What the model had already emitted of
that tag can end up in the answer. The shape is visible even without a budget: a completion capped
at one token on the shipped subagent pick returns `"<|channel>"` as its reply.

The shape that appears is the dangerous one. Measured on `b10666-4e97ac86e`, the shipped subagent
pick, a constrained reply into the fixed envelope: one draw returned

```
{"reply": "thought"}
```

a whole, valid envelope whose entire answer is the channel name. It is not a prefix, which would
break the JSON and reach the `MALFORMED` outcome ADR-0028 already has words for; this parses,
unwraps, and is reported to the spawning cortex as the subtask's answer.

The counts are 1 of 58 draws sending `reasoning_budget_tokens: 0` across the raw wire and the
shipped adapter, and 0 of 20 of the identical request against a tier using `--reasoning-budget 0` on
its argv, which is how every subagent server this repo ships is started. Those two set the same
sampler and at these sizes the counts do not separate, so this is a rare engine behaviour the
per-request key inherits rather than introduces. No repair shipped: removing the tag means knowing
the start sequence, a per-pick token (`<|channel>thought` on the gemma-4 family, `<think>` on the
Qwen one) that the port exists not to know, and a rule over the answer's shape cannot stand in,
since the probe's own detector calls a one-word answer a leak, which is wrong for a subtask that
asked for a number.

## History

- 2026-08-29: opened by the close of
  [R-474](474-the-ports-thinking-switch-could-be-sent-as-a-request-value.md), which shipped the count that
  forces the end of a thought, reproduced the leak once in 58 budgeted draws, and found it arrives
  inside the payload rather than in front of it.
- 2026-08-29: [R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md) records the other
  place the same forced close reaches, a mangled marker read as a channel switch on a flagged
  server.
- 2026-08-30: that link is half withdrawn by the close of
  [R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md), which measured that marker on
  a server setting no reasoning budget anywhere and got it anyway. So the two are not one mechanism:
  that one is a model closing a thought the template never opened, and this one is still the forced
  close. What survives of the link is the instrument, since a probe that counts leaks and one that
  reads what a trace opens with need the same column.
- 2026-09-02: the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) drew 80 GPU draws of
  `--reasoning-budget 0` alone on the E4B pick across both request shapes, the case where the forced
  close happens on every draw, and no reply began with a leaked tag or was the channel name alone;
  nor did any of the pair's 40. The rate stays under one in a hundred.
- 2026-09-07: the trigger was answered, and its second clause was already true on the day the entry
  was written, so it is narrowed above: the opening run's own leak count was 1, so "any draw whose
  leak count is not zero" could never come out false. Measured again on both builds this host can
  start, the committed probe at a hundred draws a cell on the shipped subagent pick at `-ngl 99` and
  a cap of 256. Neither build leaked once, in the budgeted cell or in either of the other two:
  `b10680-d7bd3bfca`, which the stack starts today, and `b10666-4e97ac86e`, the build the leak was
  seen on, still cached here under its fixed tag. Six hundred draws, no leak. The budgeted cell now
  stands at 1 leak in 258 draws against 0 in the 140 flag draws, and the two still do not separate.
  No delegated run recorded in this repo has reported a one-word answer. Cells and builds: ADR-0049.
  Quoting the 258 turned up
  [R-598](598-the-leaks-denominator-is-53-in-one-place-and-58-in-three.md).
- 2026-09-13: neither clause of the trigger has fired, and the change that looked like it reached
  this entry does not. The sentence the constrained path appends to every subtask was rewritten, and
  the probe holding these counts,
  [test_trace_budget_live.py](../../../brain/packages/inference/tests/test_trace_budget_live.py),
  imports `REPLY_ENVELOPE` alone and composes its own request, so the counts are still readings of
  the request the probe sends.
- 2026-09-15: checked again and still open, and the three shapes were put through the shipped reader
  rather than argued about from the parser. `settle_reply` on a constrained attempt reports
  `{"reply": "thought"}` as the answer `thought` with no failure, and reports
  `<|channel>{"reply": "42"}`, `<think>{"reply": "42"}` and `<|channel>` alone as `MALFORMED`. So
  the account of which shape is dangerous is exact. The adapter's chunk reader passes a bare
  `<|channel>` through as reply content, since it routes on the key llama.cpp put the text under and
  never on what the text says. Neither clause of the trigger has fired and no cell has been drawn,
  so the counts stand where the last review left them (thinking-switch readings).
