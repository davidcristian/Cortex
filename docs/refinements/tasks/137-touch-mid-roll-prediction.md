# A touch mid-roll pins the session to a prediction

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

The summon's
hold on the panel's geometry ends the moment the user touches it
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 8), and if that touch lands while a section
is still rolling in behind the summon, the last arrival-time placement was the ride-along, which
places the panel for the height it PREDICTS the roll will reach. The measurement that would have
corrected it (`cortex:morphend`, at the end of the roll) is no longer an arrival, so the
prediction's own error becomes the session's pinned edge. Measured 2026-07-20 at a 900px viewport:
the reminder stack predicts 550px where it lands on 546, and a switcher round trip started 100ms
or 300ms after the summon leaves the panel's bottom edge 725px down the viewport against a true
centre of 722.9, where one started after the roll had finished lands on 723 exactly. It is 2.1px, it is stable rather than
drifting, and it is the same 4px prediction error that the entry below is about from the other
end. The fix is the same `ResizeObserver` that entry needs, which would make the roll's real
height available continuously rather than at its end.
- **LANDED 2026-08-03, and the entry was wrong about the cause, the size and the fix**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The prediction cannot be wrong in
  the way this describes: the rolling section's current height cancels out of it (the panel will
  be as tall as it is now, less what the section takes now, plus what it is about to take) and a
  roll is announced at its START, where both readings are taken in the same frame. What the
  ride-along got wrong was the ASIDE. It asked whether the section that is ROLLING is the reminder
  stack, where `centringHeight` asks whether the view being placed HAS one, so a stack merely
  standing in the panel while something else rolled was counted into the arrival's centring and
  out of the placement's. Measured at 900x1000 over the demo with Ctrl+N pressed while the
  switcher list is open, which summons the panel and rolls that list shut in one commit with the
  stack standing through both: the summon pinned the edge at 227 and the placement at the end of
  the roll re-centred it to 324, so the panel's bottom edge travelled 97px down the viewport
  across the roll and came back at the end of it, and a key pressed inside the arrival window,
  which is what stops that placement re-centring, left the session pinned 97px low for the rest of
  it. That is 97px and a visible excursion rather than 2.1px of stable error. The ride-along now counts
  its prediction through `centringHeight` itself, bounded at `openHeight` before the aside comes
  off because that is the order the measurement happens in, so the arrival and the placement agree
  by construction: the bottom edge holds at 676 for every frame of that roll and settles there
  whether the panel is touched mid-roll or not, at 900x900 (edge 274, the panel on its ceiling)
  and 900x1000 (edge 324) alike. The `ResizeObserver` the entry expected to retire it had nothing
  to do with it, and the aside's own roll behind a summon never had the defect, the two spellings
  being the same number for that case.

## Trail

- 2026-07-20: Measured at a 900px viewport, filed at 2.1px of stable error, and blamed on the
  ride-along's prediction.
- 2026-08-03: Landed by something other than what it asked for and at 97px rather than 2.1. The
  prediction is exact by construction, the rolling section's current height cancelling out of it,
  and what was wrong was the aside: the ride-along asked whether the section that is rolling is the
  reminder stack where the placement asks whether the view being placed has one. The
  `ResizeObserver` the entry expected to retire it had nothing to do with it. The index recorded the
  three panel-motion entries that closed together as the ones the backlog itself had described as
  one pickup, of which two were, and read this entry and the stale-placement one as materially wrong
  about themselves in opposite directions, this one pricing 2.1px against a 97px excursion while
  that one asked for an observer that could also retire the roll's end event.
