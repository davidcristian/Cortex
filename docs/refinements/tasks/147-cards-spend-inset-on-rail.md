# Two cards spend their whole inset on the rail

**Status:** open, fix when it bites
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 22, scrollbars as reserved chrome ([overlay-ux.md §2](../../design/overlay-ux.md))
**Trigger:** A row that ever drops its own horizontal padding, or the maintainer reading the rail as touching the chrome.

Both cards carry a
6px pad, which is exactly the rail, so their inline-end padding goes to 0 and the reserved gutter
becomes the inset. That keeps the resting geometry (measured 2026-07-20: rows at x 190, width
520, whether or not the list scrolls) and it costs the one thing spending a whole inset can cost:
a row's box now reaches the reserved band. The painted thumb clears the right-most child box by
1px (card inner right edge 716, thumb painted 711 to 714, row box ending at 710). Only the box
gets that close, which is worth stating precisely because the box is not what the eye sees: the
hairline between two reminders is a border-top on a 12px-radius row, so its straight run ends at
697 (698 in the light theme) and its corner curve's last tinted pixel is 701, leaving nine
untouched columns before the thumb's first at 711. Read off the border row's pixels in both
themes at deviceScaleFactor 1, 2026-07-20. Text and controls are
still 9px to 11px clear, because each row pads itself, and the row ends exactly where it ended
before this change, so nothing regressed. Two things bring it back: a row that ever drops its own
horizontal padding (the 6px has to go back on the card, and the inline-end inset becomes 12px
against a 6px left unless the rail is narrowed for these two cards), or the maintainer reading the
rail as touching the chrome. Either way it is a padding line, and both cards are already
commented with the arithmetic.

## Trail

- 2026-07-20: Measured in both themes at deviceScaleFactor 1 and filed when scrollbars became
  reserved chrome.
- 2026-08-09: A trigger sweep read it against the tree and fired nothing:
  `body/app/src/overlay.css:37` still declares `--rail: 6px`, with the sheet's geometry note at line
  31 still recording both surfaces at 6px.
