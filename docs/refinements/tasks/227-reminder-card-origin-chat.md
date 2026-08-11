# The reminder card's origin chat

**Status:** landed 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 origin
addendum](../../adr/ADR-0025-scheduling-reminders.md). "Open the conversation this came from",
which this entry correctly predicted needed no wire change: `session_id` has ridden every
`DueReminder` since the seam was designed, and the overlay already loads a chat on demand,
so the card gained a control and nothing else did (no proto field, no transport method, no
reducer action, no brain change). It reuses `Panel`'s existing `onSelectSession`
(`useOverlay.openSession`), so a reminder and the switcher load a chat by one path with one
set of semantics, and no new prop crosses `Overlay` → `Panel`. Three decisions are worth
more than the diff. The control is a **sibling of the reminder text, never the text
itself**: making the card body clickable is the switcher's own shape and is the one thing
this surface may not do, because reminder text is the string no output guardrail inspected,
so an attacker who lands a reminder writes the label on whatever control it becomes.
**Opening is not acking**, since an ack destroys the reminder and navigation does not, so a
mis-click on the way to the context may not clear what it came to explain. And the control
is **absent, not disabled**, both for a session-less row (`""`) and for a card whose origin
is already on screen, where opening would change nothing while cancelling the turn running
in that chat. CI-gated at 100% with four guards mutation-proven, and browser-validated in
headless Chromium against the demo bridge in both themes (the adopted chat's own card offers
no control, clicking one swaps title and history while all three cards stay, and the
now-current chat's cards drop their controls in the same render). The pass also settled the
resting treatment, the same correction the taint badge needed: at the meta row's `--dim` the
label read as more metadata, so it rests at `--muted` and grows the switcher's pill on hover.
