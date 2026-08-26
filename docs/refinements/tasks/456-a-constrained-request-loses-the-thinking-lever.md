# A constrained request loses the thinking lever the subagent tier is held off by

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-26 by the close of
[R-431](431-the-token-cap-fires-on-the-shape-that-ships.md), whose paired run found where the
envelope's tokens actually go.

Both subagent lineup families are reasoning models, and unbounded thinking on this CPU tier is
minutes per call, so ADR-0010 turns it off **per server**: every subagent `llama-server` this repo
ships starts with `--chat-template-kwargs '{"enable_thinking": false}'`. `PlacedAttempt` therefore
sends no per-request thinking key on purpose, and `build_payload` only emits
`chat_template_kwargs` when a bound explicitly asks for it, the argued reason being that saying it
again per request would change the request for a deployment whose template spells the flag
differently.

**Measured, that server-side lever holds on a plain request and stops holding once the request
carries a `response_format`.** On the same body, the same server and the same session, the raw
arm's first reply token arrives 13.1 to 14.2 s in, immediately after prompt eval, and the
constrained arm's arrives 210.9 to 505.0 s in. A probe at a cap of 200 on the constrained shape
decoded **200 tokens of which none were reply text and 763 characters were reasoning**, opening
`Here's a thinking process to ensure all details are captured accurately`. Read off the wire, the
same request is 200 SSE lines over 156.3 s with not one content delta among them and a longest gap
of 3.46 s, so nothing is wedged and the 600 s stall ceiling never comes near it;
`stream_tool_loop` simply drops every reasoning delta unread.

The consequence is the whole of R-431. The shipped tool-less shape spends most of a cap sized on
reply length on text no reader ever sees, which is exactly the pairing ADR-0038 insists on being
broken: a cap on a reasoning model with thinking left on deletes the reply rather than shortening
it. One narrow summarization in three reached the cap and came back a refusal, and the two that
finished returned **shorter** replies than the same bodies raw, 158 and 1176 characters against
1559 and 2211.

**What would close it.** The lever `build_payload` already has: give a constrained subagent attempt
a `GenerationBounds` with `thinking=False`, so the request carries
`chat_template_kwargs: {"enable_thinking": false}` itself rather than trusting a server flag that a
`response_format` overrides. Three things have to be settled rather than assumed. The decision it
reverses is argued in a comment on `PlacedAttempt._generation` and belongs in a dated addendum, not
in a diff. `UNBOUNDED_ATTEMPT` currently sends no bounds at all, so the change has to decide whether
an unbounded attempt starts sending a key it never sent. And it wants the same live proof the defect
got: one constrained run at a small cap, through
`brain/packages/orchestrator/tests/test_envelope_cost_live.py`, showing the reasoning gone and the
reply arriving at once. Whether the fix belongs per request or per tier is the open half; a server
flag that a request silently overrides is not a lever this repo can keep relying on either way.

## Trail

- 2026-08-26: opened by the close of
  [R-431](431-the-token-cap-fires-on-the-shape-that-ships.md), whose paired run traced the
  envelope's cost to a reasoning trace the shipped constrained request re-enables.
