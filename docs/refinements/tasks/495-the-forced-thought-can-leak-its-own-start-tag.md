# A forced end of thought can deliver its own start tag as the answer

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a delegated run whose answer is one word, or any draw of the committed probe whose
leak count is not zero, on any tier that ends a thought at the engine.

Opened 2026-08-29 by the close of
[R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which shipped the per-request
trace budget, measured the leak that entry had recorded, and found a worse shape than the one it
described.

A trace budget is a sampler: it watches for the thought's start sequence and forces its end tag, so
the forcing necessarily lands **after** the start has been written. What the model had already
emitted of that tag can therefore end up in the answer. The shape is visible even without a budget:
a completion capped at one token on the shipped subagent pick returns `"<|channel>"` as its reply,
an unterminated start marker the parser had nowhere else to put.

**The shape that actually appears is the dangerous one.** Measured on `b10666-4e97ac86e`, the
shipped subagent pick, a constrained reply into the fixed envelope: one draw returned

```
{"reply": "thought"}
```

a whole, valid envelope whose entire answer is the channel name. It is **not** the prefix the
opening entry described, and that difference is the whole of the risk: a prefix would break the
JSON and reach the `MALFORMED` outcome ADR-0028 already has words for, where this parses, unwraps,
and is reported to the spawning cortex as the subtask's answer. Nothing downstream can tell it from
a real one.

**What the counts are, and what they are not.** 1 of 58 draws carrying `reasoning_budget_tokens: 0`
across the raw wire and the shipped adapter. 0 of 20 of the identical request against a tier
carrying `--reasoning-budget 0` on its argv instead, which is how every subagent server this repo
ships is started. Those two set the same sampler and at these sizes the counts do not separate, so
this is a rare engine behaviour the per-request key **inherits** rather than one it introduced, and
it is already reachable in the shipped stack. What nobody has is a rate good enough to act on.

**Why no repair shipped.** Stripping it means knowing the start sequence, a per-pick token
(`<|channel>thought` on the gemma-4 family, `<think>` on the Qwen one) that the port exists to not
know and that a core reading a chat template it cannot see would be guessing at. A shape rule
cannot stand in either: the probe's own detector calls a one-word answer a leak, which is sound for
a prompt whose answer cannot be one word and wrong for a subtask that asked for a number.

**What would close it.** Get a rate first, on a build that shows it: the committed probe
(`brain/packages/inference/tests/test_trace_budget_live.py`) prints a leak count reading both
shapes, and a hundred draws either side of the flag-and-key comparison would say whether the two
differ at all. If a build leaks often enough to act on, the honest repair is at the **decode** seam
rather than in the core, `decode.py` already reading llama.cpp's own reasoning split, so a fragment
the engine failed to route is an engine fact that could be recognised against what that server
reports about its own template; and the alternative worth pricing first is an upstream report,
since a sampler that emits half a tag into content is a bug wherever it is fixed.

## Trail

- 2026-08-29: opened by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which shipped the count that
  forces the end of a thought, reproduced the leak once in 58 budgeted draws, and found it lands
  inside the payload rather than in front of it, where no existing defence sees it.
