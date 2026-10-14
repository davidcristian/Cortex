# A pressed Deny is asked again in the same turn

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-10-14

After the person presses Deny, the call returns `USER_DECLINED_MSG`, which ends "Do not retry
unless they ask again." The cortex called the same tool with the same arguments again in the same
turn, and the dispatcher showed a second, identical card. `RepeatSalience` admits a second identical
call per loop on purpose (a retry after a transient failure), and nothing in `_refused_by` or
`ToolDispatcher._dispatched` reads whether the first one was declined. The person has to press Deny
twice for one request, and the second card looks like the first one never went away.

## Reproduce

On the overlay, send "Please forget the memories derived from untrusted content." and press Deny
on the `forget_untrusted_memories` card. About 10 s later the same card is back; Deny again ends
the turn with a reply saying it was declined. Seen in 2 of 2 turns on 2026-10-14, one on a
recall-tainted turn and one on a clean one: [overlay repeat and forget
flows](../../readings/overlay-repeat-and-forget-flows.md#forgetting-from-the-overlay).

## What to do

Refuse, without a card, a call identical to one the person declined earlier in the same loop,
returning a typed text that says it was declined and is not asked again in this turn. A different
call (other arguments, another tool) still shows its card. Build it in `dispatch_round.py` next to
`REDUNDANT`, with a dispatcher test for both cases and the overlay flow above run again.

## History

- 2026-10-14: filed from the overlay flows of that night.
