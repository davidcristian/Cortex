# A reminder card's age stops while the panel is open

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

`Reminders.tsx` reads `Date.now()` once per render and passes it to `relativeTime`, and nothing
renders the stack again while the panel stays open and its state does not change. A card that
says "2m ago" keeps saying it for as long as the person leaves the panel open without typing.

Reproduction ([readings](../../readings/overlay-idle-and-expiry-flows.md#the-brain-frozen-across-a-reply-and-a-reminders-due-time)):
on the Linux shell, with a fired reminder waiting, summon the panel on a new chat and take two
screenshots 131 s apart with no input. Both read "9m ago" (04:40:30 and 04:42:41, fired 04:30:42).

## What to do

1. Give the relative ages one shared minute tick while the panel is visible (none while hidden),
   and check whether the chat list's ages use the same once-per-render reading.
2. Test with fake timers that an open card's age advances and that a hidden panel sets no timer.

## History

- 2026-10-26: filed from the idle and expiry flows on the `cortexn8` stack.
