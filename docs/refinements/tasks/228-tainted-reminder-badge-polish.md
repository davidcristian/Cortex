# Overlay badge and UX polish for tainted reminders

**Status:** satisfied 2026-07-16
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 badge addendum](../../adr/ADR-0025-scheduling-reminders.md). The deferral
was recorded before any badge existed, and by the time one did the overlay surface and its browser
pass had already paid for the polish it names, so it was re-read against the tree rather than acted
on. Each property it asks for holds in `body/app/src/components/Reminders.tsx`: a `tainted` row
carries the fixed app-authored label `untrusted source` in the meta row beside the `repeats` tag,
every field is a plain text node with nothing linkified, and the one control on the card keeps its
own fixed label and sits beside the reminder text instead of becoming it. The badge's *treatment* is
the specific thing "polish" would have meant here, and the overlay addendum's browser pass had
already corrected it: a dashed neutral pill read as a third tag, so it took the error bubble's tint
at a lower alpha while keeping the dashed border, which is why the signal does not rest on hue
(`overlay.css`, `.reminder-tag.untrusted`). The gated tests assert behaviour rather than styling,
including a hostile-text case proving the card renders an anchor tag as visible text and contains no
anchor element. Nothing under the card changed after it shipped: every later overlay edit landed on
the confirm card, the draft value, the reducer, or the demo bridge's confirm fixture, none of them
on the reminder component, its styling, or its row type.
**Two landings the same day were checked for whether they reopen it, and neither does.** The native
toast badges a tainted reminder with its own fixed body-authored attribution, so push delivery is
not an unbadged route around the card that pull delivery badges. Structured provenance widened the
*turn* stamp, not the stored item: `ScheduledItem` still keeps the taint bit and no sources and
`DueReminder` carries no source field, so naming *which* source tainted a reminder is not available
to display here; that is the separately recorded **provenance across the stores** entry
([untrusted-content.md](../index.md#untrusted-content)) and would be a store plus proto change
rather than overlay work. What would reopen this: a named defect in the rendered card, most
plausibly from the host Windows pass on the real overlay, which is the one look no gate reaches.

## Trail

- 2026-07-14: Named as remaining behind the overlay's reminders-on-open surface, now that a real
  badge existed to polish.
- 2026-07-16: Read against the tree and closed with no code change, the first entry in this
  backlog to close that way rather than by landing something; the area's count went from 10 to 9.
  The grouped "remaining scheduling deferrals" line that used to name it stopped doing so on the
  same day.
