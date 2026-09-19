# The overlay's reminders-on-open surface

**Status:** done 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

Decided in [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md) decisions 6 to 8, and the
consumer the two pull RPCs needed. The `BrainBridge` port gains `listDueReminders` and
`ackReminder` plus a `DueReminder` mirror, `src-tauri/src/reminders.rs` implements them over the
same resilient transport as the session reads, and a card stack renders above the history.

The fetch happens when the overlay becomes visible, not on mount: the body sits resident in the
tray, so a mount-time read would deliver into a window nobody is watching, and the
acknowledge-on-dismiss contract would describe a card that was never seen. The latch resets on hide,
giving one read per summon, and absorbs StrictMode's double-fired effect, which the tests assert
under a real `<StrictMode>` wrapper since that is how `main.tsx` renders.

Dismissal is optimistic and the acknowledgement is never retried, which is the layer that pays for
the unretried transport ack: recovery is a re-read on the next open, so a lost reply can never be
misread as a stale dismissal.

Two properties are written down because they are invisible in the diff that would break them.
Reminder text is the one string the overlay shows that no output guardrail inspected, since ADR-0015
filters streamed replies rather than store rows, so nothing in the card may ever become a link. And
a recurring card says `repeats`, because acknowledging clears the occurrence while the series is
scheduled again, so an unmarked card would make dismissal read as cancellation.

Ten guards are mutation-proven: the visibility check, the reset, the latch, the optimistic dispatch,
the failed-pull no-op, the wholesale replace, the dismissal filter, both badges, and the stack's
placement outside the scrolling history.

## History

- 2026-07-14: Closed, leaving the body-side `Notify` trait and the Tauri toast as the remaining part
  of the slice, and opening the badge and UX polish for tainted reminders now that a real badge
  existed.
