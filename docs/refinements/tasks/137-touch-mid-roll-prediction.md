# A touch mid-roll fixes the session to a prediction

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

The summon's hold on the panel's geometry ends the moment the user touches it
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 8). If that touch comes while a
section is still rolling in, the last arrival-time placement is the one the summon made, which
places the panel for the height it predicts the roll will reach, and that prediction's error
becomes the session's fixed edge. The entry priced it at 2.1px, measured 2026-07-20 at a 900px
viewport: the reminder stack predicts 550px where it ends at 546, and a switcher round trip
started 100 ms or 300 ms after the summon leaves the panel's bottom edge 725px down the viewport
against a true centre of 722.9, where one started after the roll had finished ends at 723
exactly.

**Shipped 2026-08-03, and the entry was wrong about the cause, the size and the fix**
([ADR-0035](../../adr/ADR-0035-console-and-motion.md)). The prediction cannot be wrong in the way
described: the rolling section's current height cancels out of it (the panel will be as tall as it
is now, less what the section takes now, plus what it is about to take), and a roll is announced
at its start, where both readings are taken in the same frame.

What the arrival placement got wrong was the aside. It asked whether the section that is rolling
is the reminder stack, where `centringHeight` asks whether the view being placed has one, so a
stack merely present in the panel while something else rolled was counted into the arrival's
centring and out of the placement's. Measured at 900x1000 over the demo with Ctrl+N pressed while
the switcher list is open, which summons the panel and rolls that list shut in one commit with the
stack present through both: the summon fixed the edge at 227 and the placement at the end of the
roll re-centred it to 324, so the panel's bottom edge travelled 97px down the viewport across the
roll and came back at the end of it. A key pressed inside the arrival window, which is what stops
that placement re-centring, left the session 97px low for the rest of it. That is a visible
excursion rather than 2.1px of stable error.

The arrival placement now counts its prediction through `centringHeight` itself, bounded at
`openHeight` before the aside comes off, because that is the order the measurement happens in, so
the arrival and the placement agree. The bottom edge holds at 676 for every frame of that roll and
settles there whether the panel is touched mid-roll or not, at 900x900 (edge 274, the panel on its
ceiling) and 900x1000 (edge 324) alike. The `ResizeObserver` the entry expected to retire it had
nothing to do with it, and the aside's own roll behind a summon never had the defect, the two
readings being the same number for that case.

## History

- 2026-07-20: Measured at a 900px viewport, filed at 2.1px of stable error, and blamed on the
  arrival placement's prediction.
- 2026-08-03: Shipped by something other than what it asked for and at 97px rather than 2.1. The
  index recorded the three panel-motion entries that closed together as the ones the backlog had
  described as one pickup, of which two were, and read this entry and the stale-placement one as
  wrong about themselves in opposite directions: this one priced 2.1px against a 97px excursion,
  while that one asked for an observer that could also retire the roll's end event.
