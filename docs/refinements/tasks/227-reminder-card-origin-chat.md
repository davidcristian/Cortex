# The reminder card's origin chat

**Status:** done 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

Decided in [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md) decision 9. "Open the
conversation this came from" needed no wire change, as the entry predicted: `session_id` has been on
every `DueReminder` since the interface was designed, and the overlay already loads a chat on
demand, so the card gained a control and nothing else changed. It reuses `Panel`'s existing
`onSelectSession` (`useOverlay.openSession`), so a reminder and the switcher load a chat by one path
with one set of semantics.

Three decisions are worth more than the diff. The control is a sibling of the reminder text and
never the text itself: making the card body clickable is the switcher's shape and is the one thing
this surface may not do, because reminder text is the string no output guardrail inspected, so an
attacker who plants a reminder writes the label on whatever control it becomes. Opening is not
acknowledging, since an acknowledgement destroys the reminder and navigation does not, so a mis-click
on the way to the context may not clear what it came to explain. And the control is absent rather
than disabled, both for a row with no session (`""`) and for a card whose origin is already on
screen, where opening would change nothing while cancelling the turn running in that chat.

Four guards are mutation-proven, and it was checked in headless Chromium against the demo bridge in
both themes: the adopted chat's own card offers no control, clicking one swaps title and history
while all three cards stay, and the now-current chat's cards drop their controls in the same render.
The pass also settled the resting treatment, the same correction the taint badge needed: at the meta
row's `--dim` the label read as more metadata, so it rests at `--muted` and grows the switcher's
pill on hover.

## History

- 2026-07-14: Closed with the overlay's reminder surface.
