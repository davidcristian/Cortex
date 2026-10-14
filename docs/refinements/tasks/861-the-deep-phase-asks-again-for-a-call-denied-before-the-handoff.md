# The deep phase asks again for a call denied before the handoff

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-14

A call identical to one the person pressed Deny on earlier in the same turn returns
`ALREADY_DECLINED_MSG` with no card (`ToolLoopContext.declined`, filled in `run_round`). That list
lives on the cortex phase's loop context only. `HandoffRecord` has no field for it, and
`BrainPhase.run` builds a new `ToolLoopContext`, so the deep phase starts with an empty list.

In one turn the person can deny a `send_email` card and then approve the `escalate_to_brain`
card; when the deep model calls `send_email` with the same arguments, the dispatcher shows a second
card for the action the person already declined in this turn, which `ALREADY_DECLINED_MSG` itself
says does not happen. Reproduction: `_drive` of `test_brain_phase.py` with a loop tail holding a
call and its `USER_DECLINED_MSG` result, a dispatcher whose policy confirms that tool and a
`RecordingConfirmer(answer=False)`, and a deep backend calling it again with the same arguments:
the confirmer receives one request, where the cortex phase would have made none.

## What to do

Store the declined calls (name and arguments) in `HandoffRecord` beside `budget_remaining`, so
they survive the model swap with the rest of the turn state, and seed the deep phase's
`ToolLoopContext.declined` from them. Test it with a fake handoff: a call declined in the cortex
phase is refused in the deep phase with no confirmer request.

## History

- 2026-10-14: filed by the closing audit of the declined call check, from the probe above; no
  live turn drawn.
