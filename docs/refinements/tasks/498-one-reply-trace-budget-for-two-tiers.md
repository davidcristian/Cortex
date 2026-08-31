# One reply trace budget reaches the deep phase as well as the cortex turn

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** the first deployment that sets `CORTEX_REPLY_TRACE_TOKENS` on a stack with
`CORTEX_ESCALATION` on, which is when one count starts binding two tiers picked on opposite
arguments.

Opened 2026-08-29 by the close of
[R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which gave a user's reply a
per-request trace budget and put it on the bounds both phases of a turn already share.

`ReplyBoundsConfig.bounds()` builds one `GenerationBounds`, the root hands it to `StreamEngines`,
and `BrainPhase` carries the same value into the deep model's completion. That sharing is
deliberate for the two knobs that were already there: a handoff is one turn continued, so a
deployment that capped a reply did not ask for the cap to lapse the moment the question got hard
enough to escalate (ADR-0005 capped-reply addendum). The new count inherits it.

The inheritance is less obviously right than the cap's, and that is the whole of this entry. The
**server** flags for the same setting are deliberately two, `CORTEX_REASONING_BUDGET` and
`CORTEX_REASONING_BUDGET_BRAIN`, on the argument that the two tiers are read on opposite ones: the
cortex answers while somebody watches, and the deep model was chosen over faster artifacts for
reaching an answer inside its trace at all (ADR-0004). A deployment that shortens the cortex's
think has no reason to have shortened the deep model's, and with one request-level count it does
both. The request wins where both are named, since the tier flag is only the fallback.

**Why it was left.** Nothing ships set: `CORTEX_REPLY_TRACE_TOKENS` is unset by default, so no
deployment is currently in this position, and the two tier flags still express the split for one
that wants it. Splitting the request-level count means either a second env field the deep phase
reads instead, which is one more knob for a case nobody has hit, or a second `GenerationBounds`
on `TurnCapabilities`, which is the wider change and would need the cap and the switch to split
with it or explain why they did not.

**What would close it.** Either `CORTEX_REPLY_TRACE_TOKENS_BRAIN` beside the tier flag it mirrors,
defaulting to the cortex's own value so a deployment that names one knob still gets one behaviour,
or a sentence in the reply-bounds module and the GPU runbook saying the count is deliberately one
for both phases and pointing at the tier flags for a deployment that wants two. The second is
honest and cheap; the first is what the trigger above asks for.

## Trail

- 2026-08-29: opened by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which added a per-request
  trace count to the bounds a turn and its deep continuation already share, where the same setting
  at the server is two knobs on purpose.
