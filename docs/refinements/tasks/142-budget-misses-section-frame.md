# The budget bounds a section's content, not its frame

**Status:** landed 2026-08-08
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-03 with the budget
above. Each section is a bordered, padded card that cannot be shorter than 14px whatever its cap
says, and carries 6px of air beneath it, so two of them cost 40px that no cap can reach. Below
roughly 260px of viewport with both open there is nothing left to give: measured at 640x240, where
the budget floors at zero, the hint strip is 34px past the panel's edge, and at 640x300 everything
is inside. What makes it a deferral rather than a defect is that the body's window is 720px tall
and the overlay has no smaller size; the fix, if a screen that small ever exists, is for a section
whose share cannot hold one row to leave rather than to stand there as a frame.
- **LANDED 2026-08-08, re-derived from the code and from a running build first, and the entry's
  mechanism is real while one of its three numbers was not**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). Driven by hand in headless Chromium
  against the demo bridge at 640 wide, with the switcher opened over the demo's own reminder stack
  so both sections stand open, reading the used height off the computed style. The 14px is exact
  and it is `box-sizing: border-box` doing it: `max-height` under 1px of border plus 6px of padding
  on each side floors the content box at zero and leaves the border box standing at 14px, and the
  card's 6px of air is outside the card's cap altogether, so each section costs 20px and the pair
  cost 40px at every viewport where the shares floor. The 34px at 640x240 reproduced exactly, and
  so did everything being inside at 640x300. **The "roughly 260px" did not:** walked viewport by
  viewport the strip is inside at 286px, exactly level at 284px and 2px out at 282px, so the
  boundary was 24px higher than the entry's guess at it and the harm starts a whole 720p-quarter
  window earlier than the entry's own reader would have looked.
- **The fix is not the one the entry named, and the entry's fix would not have closed it.** A
  section leaving when its share cannot hold a row still leaves the OTHER one standing as a frame
  (a share of zero is a share of zero for both), and at 640x240 the two together are what escapes,
  not either alone. What the tree wanted was the cap applied where nothing floors it. The share
  is now the outer allowance and it bounds the section's WRAPPER, which has no border, no padding
  and no margin of its own and holds the card's air inside its own clip, so a share of zero costs
  zero. The card keeps a cap of its own at the share less that air, which is what still makes a
  long list scroll rather than clip. After, at 640x240: the two wrappers cost 0px against 40px,
  the hint strip clears the panel's edge by 1px where it was 34px outside, and the same 1px of
  clearance holds at every viewport from 220px up. The shortest viewport everything fits in went
  286px to 220px, level at 218px and 3px out at 214px.
- **The residue below 218px is the reserved furniture and is a decision rather than a deferral.**
  At 200px the strip is 14px out with both sections costing nothing at all: what is left in the
  column is the header, a history already at its 10px floor, and the composer standing on its own
  84px pill floor. Yielding that floor is the one thing the whole reserve ordering exists to
  prevent (the conversation gives up room before the chrome, the chrome before the composer), so
  there is no further design here, only a screen the panel cannot be used on.
- **The arm was proved able to fail before it was trusted, twice over.** The 284px boundary and the
  34px are read off the tree as it stood, the change stashed away and the whole ladder walked
  again from a cold start. And taking only the wrapper's cap away with a live override, in the same
  browser session as the fixed reading, puts the 40px and the escape straight back: 20px per
  section wherever the shares floor, with the strip 8px out at 640x260, 24px at 640x240 and 54px at
  640x200 against 1px INSIDE at all three with the cap standing. Those three are smaller than the
  cold-start figures because the panel keeps the edge it was placed on for the shorter column, which
  is the same defect measured from a taller panel. Removing the override in the same session returns
  every number to the fixed reading. At 640x720 nothing moves under either arm, the two shares
  (141.14 and 105.86) being exactly what the two outer boxes already measured, so the size the body
  actually opens at is bit-identical.

## Trail

- 2026-08-03: Opened with the section budget that landed above it.
- 2026-08-08: Landed, re-derived from the code and from a running build first as this file's own
  warning demands. The 40px reproduced exactly and so did the 34px at 640x240, while the entry's
  "roughly 260px" boundary was really 284px, and its proposed fix would not have closed it, a
  section leaving when its share cannot hold a row leaving the other one standing as a frame. The
  share now bounds the section's wrapper, which has nothing to floor it, and the shortest viewport
  everything fits in went 286px to 220px. The area went ten to nine, one out and none in.
