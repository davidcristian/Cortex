# One reply trace budget reaches the deep phase as well as the cortex turn

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-12
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
- 2026-09-07: the trigger has not fired, and it is precise enough to leave as written.
  Both settings it names would have to be on together and neither is on at all.
  `CORTEX_REPLY_TRACE_TOKENS` is set by no compose file, justfile recipe or workflow here, and
  there is no `.env` at the repo root. `CORTEX_ESCALATION` is off by default in `config_swap.py`,
  and the GPU override names it only in a comment saying what a deployment would add; the one place
  in the tree that spells it as a setting is a host task's compose snippet, which is work waiting
  on hardware rather than a deployment that runs. The sharing this entry is about is unchanged:
  `ReplyBoundsConfig.bounds()` still builds one `GenerationBounds`, and `brain_phase.py` still
  carries `self._caps.bounds` into the deep model's completion, so the first deployment to set both
  gets one count over two tiers.
- 2026-09-12: the trigger has not fired and the premise holds line for line.
  `ReplyBoundsConfig.bounds()` builds one `GenerationBounds`; `wiring.py` hands it to
  `StreamEngines` as `bounds`; `engine.py` puts it on the cortex turn's `ToolLoopContext` and
  `brain_phase.py` puts the same `self._caps.bounds` on the deep continuation's. Neither setting the
  trigger names is on: `CORTEX_REPLY_TRACE_TOKENS` is set by no compose file, recipe or workflow and
  there is no `.env`, and `CORTEX_ESCALATION` is `False` by default in `config_swap.py`, named in a
  comment in the GPU override, spelled as an operator instruction in the model-swap runbook, and
  spelled as a setting only in a host task's compose snippet. One reading is worth adding to the
  split this entry rests on: the two tier flags express it, but their **default** does not, and
  `crosscheck` holds those two defaults as one set on the argument that both tiers ship unbounded.
  So the first deployment to set the request count on an escalating stack bounds two traces that
  nothing else bounds, which is a wider first step than the entry's wording implies.
