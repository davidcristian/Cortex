# The port's thinking switch could be rendered as a lever that holds

**Status:** landed 2026-08-29
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-28 by the close of
[R-464](464-why-a-grammar-restores-the-trace.md), which went looking for the cause of a switch that
does nothing under a schema and came back with a lever that works.

`GenerationBounds(thinking=False)` renders as `chat_template_kwargs: {"enable_thinking": false}` and
nothing else, which is a hint to the deployment's chat template. On a request carrying a
`response_format` that hint is overruled by the grammar llama.cpp builds, so on the shipped subagent
pick the switch holds only sometimes: 4 draws in 5 deliberate through it and spend the whole of a paired
cap on the trace, which is a deleted reply rather than a short one.

Measured on `ghcr.io/ggml-org/llama.cpp` `b10644-d7a207411`, that same request can carry
`reasoning_budget_tokens` (or `thinking_budget_tokens`), which the server reads off the body and
falls back to the tier's `--reasoning-budget` for only when the request says `-1`. Sent as `0` on
the exact cell that fails, the subagent pick's constrained request with the switch, it holds on **5
draws of 5**, each returning the envelope. It is a sampler rather than a prompt or a grammar: it
detects the thought's start sequence and forces its end tag, so it reaches every request shape
by construction. The name this repo tried and recorded, `reasoning_budget`, is genuinely ignored
on the same build in the same minute (4 draws in 5 still deliberated, and the server logged
`reasoning budget: tokens=-1` for every one of them), so the earlier reading was right about the
name it sent and is no longer right about the engine.

**What this would be.** `build_payload` renders `thinking=False` as the budget key as well as the
template kwarg, so the field the port already documents as advisory becomes one that holds wherever
the engine reads the key. The port's own wording is what changes with it: the switch-is-advisory
addendum's decision that `thinking` is a request and not a guarantee was argued from an engine that
gave a request no lever, and this is that argument's premise moving.

**What has to be decided rather than typed.** Three things, none of them settled here.

- **The floor a build has to meet.** A server that does not recognize the key ignores it with
  nothing reported, which is the failure this repo most wants to avoid: the flag half of the same
  lever fails a tier at startup instead. So sending it unconditionally buys a setting that has no
  effect on an older build and reports nothing, and the
  honest shapes are a deployment setting or a probe of the running server, not a constant.
- **What it does to the trace a user reads.** The cortex turn renders its trace as the thinking
  status the overlay shows, so a budget of zero attached to every `thinking=False` request is only
  right for the calls that discard the trace unread. Those are the three side calls, and the turn's
  own bounds are not one of them.
- **One draw showed the seam.** Of the five holding draws, one returned a reply whose text began
  with the leaked word `thought`: the forcing lands after the start sequence, and what the model had
  already written of the tag can survive into the answer. A repair that ships has to say what
  happens to that, since the envelope's `reply` is what a delegated run reports.

**Its sibling.** [R-295](295-per-request-trace-budget.md) records the other half of the same engine
fact, a positive count per request rather than a zero, and names this build as the trigger it was
waiting for. Whichever lands first should carry the other: they are one key on one payload.

**Landed as the [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) request-lever addendum**, which
carried R-295 with it. `GenerationBounds` gained `trace_tokens`, rendering as
`reasoning_budget_tokens`; the three side calls whose trace `drain_text` destroys each name a zero,
and a user's own reply names nothing unless `CORTEX_REPLY_TRACE_TOKENS` says so. The port's
switch-is-advisory wording moved with it, and the shared contract list gained an eleventh check: a
trace that arrived despite a budget of zero crosses all the same, which is a separate obligation
from the switch's, because a count is a stronger instruction than a hint.

**The three open questions, answered.** The **floor** is a probe of the running server
(`CORTEX_INFERENCE_TRACE_LEVER=auto|on|off`, the shape `CORTEX_VISION` already has), not a
deployment setting alone, because the images this repo names are mutable tags and the right value
therefore moves under an operator who did nothing: the build under this repo had already gone from
`b10644-d7a207411` to `b10666-4e97ac86e` between the entry and its close. The probe is the engine's
own range check, one call, free of the model. The **trace a user reads** is protected by a rule
rather than by care: nothing derives a count from the switch, and two tests hold it. The **leak**
reproduced, once in 58 budgeted draws, and it is worse than this entry supposed: it lands
**inside** the envelope (`{"reply": "thought"}`), so nothing rejects it and a delegated run reports
the leaked tag as the answer. The same sampler as a tier flag did not do it in 20 draws, so the
honest reading is a rare engine behaviour the request key inherits rather than adds. No repair
ships, one needing the core to know a per-pick template token, and
[R-495](495-the-forced-thought-can-leak-its-own-start-tag.md) carries it with both counts.

**Two things this entry was sharper about than its close first was.** Its failing cell is recorded
at 4 draws in 5, and the first five draws of this close read 5 of 5, which was written down as "the
entry understated it" before twenty draws said **17 of 20**. The entry was right and the small
sample was not. And its account of the leak's shape, a reply that "began with" the leaked word, is
the one of the two shapes that did **not** appear; the shape that did leaves the payload well
formed, which is why both of this close's own leak detectors were wrong before one of them was
right.

## Trail

- 2026-08-29: landed as the ADR-0005 request-lever addendum, which carried
  [R-295](295-per-request-trace-budget.md) with it, both being one key on one payload. The floor is
  a capability probe of the running engine rather than a constant or a declaration, because the
  tags this repo names are mutable and the build under it had already moved; the user-visible trace
  is protected by never deriving a count from the switch; and the leak did not reproduce at 53
  draws. It opened three narrower entries:
  [R-495](495-the-forced-thought-can-leak-its-own-start-tag.md), the leak on a build that brings it
  back; [R-496](496-the-trace-lever-is-answered-once-per-boot.md), the cached answer when an image
  is replaced under a running brain; and
  [R-497](497-nothing-reports-a-trace-budget-that-went-unread.md), a count nothing reports as
  unread; and [R-498](498-one-reply-trace-budget-for-two-tiers.md), one reply count reaching two
  tiers whose server flags are deliberately two.
