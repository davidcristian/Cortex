# The budget bounds a section's content, not its frame

**Status:** done 2026-08-08
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Each section is a bordered, padded card that cannot be shorter than 14px whatever its cap says,
and it has 6px of air beneath it, so two of them cost 40px that no cap can reach. Below a certain
viewport with both open there is nothing left to give: at 640x240, where the budget floors at
zero, the hint strip was 34px past the panel's edge, and at 640x300 everything was inside.

**Shipped 2026-08-08**, checked against the code and a running build first
([ADR-0035](../../adr/ADR-0035-console-and-motion.md)). Driven by hand in headless Chromium
against the demo bridge at 640 wide, with the switcher opened over the demo's reminder stack so
both sections stand open, reading the used height off the computed style.

The 14px is exact, and `box-sizing: border-box` is what does it: `max-height` under 1px of border
plus 6px of padding on each side floors the content box at zero and leaves the border box at
14px, while the card's 6px of air is outside the card's cap, so each section costs 20px and the
pair cost 40px wherever the shares floor. The 34px at 640x240 reproduced exactly, and so did
everything being inside at 640x300. The "roughly 260px" boundary did not: walked viewport by
viewport, the strip is inside at 286px, exactly level at 284px and 2px out at 282px, so the
boundary was 24px higher than the entry guessed.

The fix is not the one the entry named, and its fix would not have closed this. A section leaving
when its share cannot hold a row still leaves the other one drawn as an empty frame, since a share
of zero is a share of zero for both, and at 640x240 the two together are what escapes. What the
tree needed was the cap applied where nothing floors it. The share is now the outer allowance and
it bounds the section's wrapper, which has no border, no padding and no margin of its own and
holds the card's air inside its own clip, so a share of zero costs zero. The card keeps a cap of
its own at the share less that air, which is what still makes a long list scroll rather than clip.

After, at 640x240 the two wrappers cost 0px against 40px, the hint strip clears the panel's edge
by 1px where it was 34px outside, and the same 1px of clearance holds at every viewport from 220px
up. The shortest viewport everything fits in went 286px to 220px, level at 218px and 3px out at
214px.

The residue below 218px is the reserved furniture and is a decision rather than a deferral. At
200px the strip is 14px out with both sections costing nothing: what is left in the column is the
header, a history already at its 10px floor, and the composer on its 84px pill floor. Yielding
that floor is what the whole reserve ordering exists to prevent, so there is no further design
here, only a screen the panel cannot be used on.

Proved able to fail twice. The 284px boundary and the 34px were read off the tree as it stood, the
change stashed away and the whole ladder walked again from a cold start. And taking only the
wrapper's cap away with a live override, in the same browser session as the fixed reading, puts
the 40px and the escape straight back: 20px per section wherever the shares floor, with the strip
8px out at 640x260, 24px at 640x240 and 54px at 640x200, against 1px inside at all three with the
cap present. Those three are smaller than the cold-start figures because the panel keeps the edge
it was placed on for the shorter column. Removing the override returns every number to the fixed
reading. At 640x720 nothing moves either way, the two shares (141.14 and 105.86) being exactly
what the two outer boxes already measured.

## History

- 2026-08-03: Opened with the section budget of [R-141](141-sections-outrun-the-panel.md).
- 2026-08-08: Shipped. The area went ten to nine, one out and none in.
