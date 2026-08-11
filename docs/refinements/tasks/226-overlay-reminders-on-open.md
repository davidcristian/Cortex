# The overlay's reminders-on-open surface

**Status:** landed 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 overlay
addendum](../../adr/ADR-0025-scheduling-reminders.md). The second of the three in-slice
remainders, and the one that gives the two pull RPCs a consumer: the `BrainBridge` port
grows `listDueReminders`/`ackReminder` (+ a `DueReminder` mirror), `src-tauri/src/reminders.rs`
implements them over the same resilient transport as the session reads, and a card stack
renders above the history. The fetch is latched on the **rising edge of visibility**, not on
mount: the body sits resident in the tray, so a mount-time read would deliver into a window
nobody is watching and the ack-on-dismiss contract would be describing a card that was never
seen; the latch re-arms on hide (one read per summon) and absorbs StrictMode's double-fired
effect, which the tests assert under a real `<StrictMode>` wrapper since that is how
`main.tsx` renders. Dismissal is **optimistic and the ack is never retried**, which is the
layer that pays for the transport addendum's split: recovery is a re-read on the next open,
so a lost reply can never be misread as a stale dismissal. Two properties are written down
because they are invisible in the diff that would break them: reminder text is the one string
the overlay shows that **no output guardrail inspected** (ADR-0015 filters streamed replies,
not store rows), so nothing in the card may ever become a link, and a recurring card says
`repeats` because acking clears the occurrence while the series re-arms, so an unmarked card
would make dismissal read as cancellation. CI-gated at 100% over the fake bridge with ten
guards mutation-proven (the visibility check, the re-arm, the latch, the optimistic dispatch,
the failed-pull no-op, the wholesale replace, the dismissal filter, both badges, and the
stack's placement outside the scrolling history; each reverted individually turns a distinct
test red). Remaining of the in-slice remainder: only the body-side `Notify` OS trait + the
Tauri toast (host-validated). Remaining behind this surface: **overlay badge/UX polish for
tainted reminders** (the ADR-0025 deferral, now that a real badge exists to polish).
