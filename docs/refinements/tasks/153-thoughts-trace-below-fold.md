# A Thoughts trace pushing the reply below the fold

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

The
disclosure rolls open in place and nothing touches the history's `scrollTop`, which is the right
default: the row stays exactly under the pointer that clicked it and the trace unfolds beneath,
where native `<details>` and every other disclosure put it. Where the panel can still grow that is
the whole story, and nothing scrolls at all. Where it cannot, the growth is absorbed by the
scroll box instead, and everything below the trace slides down by the height of it. Measured
2026-07-20 at 60Hz at 640x720 (the body's own window) with the reminder stack up, so the panel
was already at its 547px ceiling: the disclosure's top edge held at 360px for every frame of the
roll and `scrollTop` never moved, while the distance from the tail grew 0 to 76px, leaving two
lines of the answer visible above the composer. With a trace long enough to hit its own `28vh`
cap the growth is 206px and the answer goes entirely. The reader can scroll, and the state is
exactly reversible by closing the trace, so this is a comfort item rather than a defect. The fix
is not "follow the tail": that scrolls the trace's own top edge off the screen as it grows and
leaves the reader reading its bottom half. It is to scroll the history by the same curve and over
the same 300ms, by as much as the growth that falls below the fold and no more, so the trace ends
fully visible with as much of the reply below it as still fits. That wants a scroll animation
alongside `Collapse`'s height animation (`components/Collapse.tsx` owns the only clock either
could share), and it wants a rule for what "as much as fits" means when the trace alone is taller
than the visible history. Deferred because it is a second motion to keep in step with the roll,
and the roll itself is the thing the maintainer asked for.

That animation has a second job now. `.history` turned scroll anchoring off
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 15) because the engine's version of it
lurched the log 76px on the way open, and closing a trace that sits above the fold was the one
thing it had been getting right: it eased `scrollTop` down with the shrink so the visible content
never moved. A deliberate scroll on the roll's clock covers both directions with one rule, where
the engine had one good half and one bad one.

**LANDED 2026-08-03 ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)), and the entry
was wrong about its own setup and about the shape of the fix.** The rule is the tail pin held
across a roll: while the reader is at the end of the log, `overlay/logRide.ts` holds their distance
from it for every frame of the roll, so the growth comes out of the scroll rather than out of the
reply. Traced at 60Hz at 640x720 after: that distance reads 3px on every frame of both directions
where it had run 3 to 79, `scrollTop` goes 408 to 484 and back, the largest single frame is 12px,
and the movement spans t=44ms to t=311ms, which is the roll's own 300ms with no second beat after
it. The entry's own setup does not reproduce: the reminder stack is gated on an empty log and rolls
away on the first message, so a full history never has it up, and the ceiling at that viewport
reads 450px rather than 547px, the panel's budget having moved it. Everything the entry was
actually about does reproduce on a history long enough to hold the panel at its ceiling by itself,
which is the condition that always mattered.
- **There is no second animation and no shared clock, which is what the entry asked for.** It
  wanted "a scroll animation alongside `Collapse`'s height animation" because `Collapse` "owns the
  only clock either could share". A second animation would have had to predict how much of the
  growth the panel was about to absorb. The scroll is recomputed from the box on every frame of
  the roll instead, and the box is being resized by the roll's own height animation, so it
  inherits the roll's timing by construction; neither `MORPH_ROLL_MS` nor `EASING` is read in the
  file and `Collapse.tsx` is untouched. Below the ceiling the arithmetic returns the position the
  box is already at, so the uncontended case scrolls nothing at all: traced at 900x900, the panel
  goes 390.97 to 466.97 and `scrollTop` reads 0 on every frame of both directions.
- **"As much as fits" needed a rule about WHO, not only about how much.** For a reader who has
  scrolled up nothing they are looking at moves, since a section growing pushes only what is below
  it, so the ride does nothing and the row stays under the pointer that opened it. And that claim
  is measured on the roll's first frame rather than taken from the log's remembered copy of it,
  which a roll falsifies without a scroll event: built on the remembered answer, the ride at
  640x460 did nothing on the way open (correctly capped) and then eased the log 76px on the way
  shut on a claim that had been false since the open, turning a reversible round trip into a 76px
  drift. The height rule is the one the entry guessed at: the ride stops where the rolling
  section's own top edge reaches the top of the window, which at 640x600 is 58px of a 206px window,
  spent by t=181ms, with the last 21px of growth going into the scroll as before.
- **The second job is done and `overflow-anchor: none` gives up nothing now.** Traced with a trace
  scrolled off the top of the window and closed: `scrollTop` eases 487 to 411 across the shrink and
  the oldest visible bubble holds its place to under a pixel on every frame, which is the 498 to 422
  the engine used to do and the reason decision 15 was recorded as a trade. A reader who takes the
  scroll back outranks the ride and ends it in the frame their wheel lands. Under
  `prefers-reduced-motion` there is no roll to ride and the log holds still, which
  `Collapse.test.tsx` now pins by asserting that no start event is announced at all.

## Trail

- 2026-07-20: Opened when the disclosure learned to roll.
- 2026-08-03: Landed as the tail pin held across a roll, and the area's count held because the same
  pass opened one entry behind it, the panel's own chrome shrinking the log from outside the box.
  The ledger reads the entry as wrong twice in this file's two usual ways, its measured setup no
  longer existing and its prescribed second animation having to predict what the panel was about to
  absorb, where recomputing the scroll from the box inherits the clock and the curve by
  construction.
