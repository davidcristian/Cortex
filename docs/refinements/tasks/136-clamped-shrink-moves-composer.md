# A shrink against the ceiling moves the composer

**Status:** satisfied 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

The entry claimed two of the panel's fixes pull in opposite directions once the panel is tall
enough to be clamped. Leaving the panel's held bottom edge unclamped is what makes the switcher's
round trip exactly reversible ([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 4),
and it was also what pulled the bottom edge back toward that held edge the moment a shrink gave it
room, which is the one thing the maintainer asked never to happen. The entry offered the user a choice
between that and a design that moves the held edge to the clamped one on every content change.

**Closed 2026-08-06 as moot: HEAD delivers both at once, so there was never anything to pick.**
The premise died thirty two minutes after it was filed. The entry was committed at 20:25 on
2026-07-20, and four commits later at 20:57 the panel's second bound was deleted. The clamp moved
off the edge and onto the height: `clamped(pinned, viewport, height)`, which was
`max(0, min(pinned, 0.88v - h))` and is the whole mechanism this entry describes, became
`clamped(pinned) = max(0, pinned)`, a no-op for any chat holding a positive edge, and
`maxHeight(viewport, bottom)` caps the height instead. At the ceiling the panel stops getting
taller and the history scrolls.

Measured by hand in headless Chromium against the demo bridge at 640x720, where the three
reminders on the empty chat put the panel against its ceiling on arrival: `offsetHeight` 450
equals its `max-height` of 450 equals the `--ceiling` the panel publishes equals
`round(0.88 x 720 - 184)`, top edge 86, bottom edge 184px, and the composer's own bounding box
top at 445. Every number below is that composer box read per painted frame.

- Acking one reminder gives back 58px of real content (the stack measures 188 then 130, and the
  history's box grows 99 to 158). The panel holds 450 tall at a 184px edge on all 75 frames and
  the composer reads 445 on every one of them, travel 0px.
- A switcher round trip while clamped opens a 135px list inside the panel and rolls the stack to
  100, then hands both back at 0 and 188. The panel reads 450 at 184px before, during and after,
  and the composer 445 throughout, so the round trip is exactly reversible and the composer never
  moves, which is the pair the entry says cannot be had together.
- Acking all three takes the panel off its ceiling: the top edge moves 86 to 184 and the height
  450 to 352 with the bottom edge at 536 and the composer at 445 on every frame, so the shrink is
  taken entirely at the top.
- At 900x900, where the panel also arrives clamped (518 tall at a 274px edge), the ack drops the
  top edge 108 to 138.5 with the composer at 535 on all 76 frames, and the switcher round trip
  returns the panel to the identical 274px edge with the composer at 535 throughout.

The measurement was proved able to fail first. Restoring the deleted clamp at the one line that
applies it, `edge = max(0, min(wanted, 0.88v - height))`, and re-running the same scenario: the
panel arrives 546 tall at an 88px edge with the composer at 541, and acking one reminder settles
it at 483. That is the 58px the entry describes, through a 96px excursion (541 down to 445 across
the roll, back up to 483), with the edge walking 88 to 184 to 146. The change was reverted and
every number above was re-taken afterwards and reproduced.

**Why it stood for seventeen days.** Nobody re-read the entry against the code after the same
evening's fix, and two later measurements found the answer and read it as nothing. The panel-watch
measurement of 2026-08-03 recorded that "the composer holds its bottom edge at 493 through an ack
and a switcher round trip either way", and the chat-floor measurement the same day that the
composer held still "through an ack, a switcher round trip and the pencil at both viewports". 493
is this panel's composer bottom at 640x720 exactly, and both readings are this closure. Each
concluded only that the undecided preference was not settled by accident.

**The rarity number the entry was restated with is wrong.** It said a correctly placed panel has
to grow 615px at a 900px viewport before the ceiling binds at all, reading 615 as a growth delta
when it is the ceiling's value for a 546px panel centred at 900px. Headroom is `ceiling - h`, and
for a centred panel that is `0.88v - (v - h)/2 - h`, which at 900px is `342 - h/2`: 69px for that 546px
panel, at most 342px for any panel, and 0 at `openHeight(900) = 684`. Measured live at 900px, the
demo's arriving chat has 0px of headroom before the user has touched anything. The ceiling is not
rare; what is gone is the composer moving when the panel meets it.

## History

- 2026-07-20: Measured at a 900px viewport and filed with both designs put to the user. Centring
  the summon (decision 8) had already taken the symptom from constant to rare, acking a reminder,
  the pencil on a chat with a full reply, and a switcher round trip all moving the composer 0px
  where they moved it 40, 13 and 3 before.
- 2026-08-03: Two measurements in this area read the closure and recorded it as nothing, each
  asking whether its own change had moved the composer rather than whether anything still did.
- 2026-08-04: Restated from its own text and put to the user again, deliberately left unpicked.
- 2026-08-06: Closed as moot with no code written. The area went 13 to 12, and this closed the
  last entry here whose blocker was a preference rather than work. It was also a new way for an
  entry to be wrong: entries here had been wrong about a cause, a size, a fix and a cost, and this
  one was wrong about whether its subject was still in the tree.
