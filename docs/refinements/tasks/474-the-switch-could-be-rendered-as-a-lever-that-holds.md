# The port's thinking switch could be rendered as a lever that holds

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-28 by the close of
[R-464](464-why-a-grammar-restores-the-trace.md), which went looking for the cause of a switch that
does nothing under a schema and came back with a lever that works.

`GenerationBounds(thinking=False)` renders as `chat_template_kwargs: {"enable_thinking": false}` and
nothing else, which is a hint to the deployment's chat template. On a request carrying a
`response_format` that hint is overruled by the grammar llama.cpp builds, so on the shipped subagent
pick the switch is a coin toss: 4 draws in 5 deliberate through it and spend the whole of a paired
cap on the trace, which is a deleted reply rather than a short one.

Measured on `ghcr.io/ggml-org/llama.cpp` `b10644-d7a207411`, that same request can carry
`reasoning_budget_tokens` (or `thinking_budget_tokens`), which the server reads off the body and
falls back to the tier's `--reasoning-budget` for only when the request says `-1`. Sent as `0` on
the exact cell that fails, the subagent pick's constrained request with the switch, it holds on **5
draws of 5**, each returning the envelope. It is a sampler rather than a prompt or a grammar: it
watches for the thought's start sequence and forces its end tag, so it reaches every request shape
by construction. The spelling this repo tried and recorded, `reasoning_budget`, is genuinely ignored
on the same build in the same minute (4 draws in 5 still deliberated, and the server logged
`reasoning budget: tokens=-1` for every one of them), so the earlier reading was right about the
name it sent and is no longer right about the engine.

**What this would be.** `build_payload` renders `thinking=False` as the budget key as well as the
template kwarg, so the field the port already documents as advisory becomes one that holds wherever
the engine reads the key. The port's own wording is what changes with it: the switch-is-advisory
addendum's decision that `thinking` is a request and not a guarantee was argued from an engine that
gave a request no lever, and this is that argument's premise moving.

**What has to be decided rather than typed.** Three things, none of them settled here.

- **The floor a build has to meet.** A server that does not know the key ignores it silently, which
  is the failure mode this repo dislikes most: the flag half of the same lever fails a tier at
  startup instead. So sending it unconditionally buys a knob that lies on an older build, and the
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
