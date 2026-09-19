# Overlay badge and UX polish for tainted reminders

**Status:** satisfied 2026-07-16
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

Recorded before any badge existed, and by the time one did the overlay surface and its browser pass
had already done the polish it asks for, so it was read against the tree rather than acted on.

Each property holds in `body/app/src/components/Reminders.tsx`: a `tainted` row has the fixed
app-authored label `untrusted source` in the meta row beside the `repeats` tag, every field is a
plain text node with nothing turned into a link, and the one control on the card keeps its own fixed
label and sits beside the reminder text instead of becoming it. The badge's treatment is what
"polish" would have meant here, and the overlay's browser pass had already corrected it: a dashed
neutral pill read as a third tag, so it took the error bubble's tint at a lower alpha while keeping
the dashed border, which is why the signal does not rest on hue (`overlay.css`,
`.reminder-tag.untrusted`). The tests assert behaviour rather than styling, including a hostile-text
case proving the card renders an anchor tag as visible text and contains no anchor element.

Two changes made the same day were checked for whether they reopen it, and neither does. The native
toast marks a tainted reminder with its own fixed body-authored attribution, so push delivery is not
an unmarked route around the card that pull delivery marks. Structured provenance widened the turn
stamp, not the stored item: `ScheduledItem` still keeps the taint bit and no sources and
`DueReminder` has no source field, so naming which source tainted a reminder is not available to
display here. That is the separately recorded provenance-across-the-stores entry
([untrusted-content.md](../index.md#untrusted-content)) and would be a store plus proto change.

It reopens on a named defect in the rendered card, most plausibly from the host Windows pass on the
real overlay, which is the one look no automated check reaches.

## History

- 2026-07-14: Named as remaining behind the overlay's reminders-on-open surface.
- 2026-07-16: Read against the tree and closed with no code change, the first entry in this backlog
  to close that way rather than by building something.
