# Two cards use their whole inset for the rail

**Status:** declined 2026-08-18
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 22, scrollbars as reserved chrome ([overlay-ux.md §2](../../design/overlay-ux.md))

Both cards have a 6px pad, which is exactly the rail, so their inline-end padding goes to 0 and
the reserved gutter becomes the inset. That keeps the resting geometry (measured 2026-07-20: rows
at x 190, width 520, whether or not the list scrolls) and it costs the one thing using a whole
inset can cost: a row's box now reaches the reserved band. The painted thumb clears the right-most
child box by 1px (card inner right edge 716, thumb painted 711 to 714, row box ending at 710).

Only the box gets that close, and the box is not what the eye sees: the hairline between two
reminders is a border-top on a 12px-radius row, so its straight run ends at 697 (698 in the light
theme) and its corner curve's last tinted pixel is 701, leaving nine untouched columns before the
thumb's first at 711. Read off the border row's pixels in both themes at deviceScaleFactor 1. Text
and controls are still 9px to 11px clear, because each row pads itself.

**Declined 2026-08-18, because this entry describes a measured design and names no work.** Every
number still holds: `--rail` is 6px, both cards pay `padding: 6px 0 6px 6px` with
`scrollbar-gutter: stable`, and the rows still pay their own 11px and 9px
([overlay.css](../../../body/app/src/overlay.css)). Building it would mean putting the 6px back on
the card and accepting an inline-end inset of twice the left one, which is a regression of a
geometry that was measured in both themes and that nobody has complained about. Both of its
triggers are edits to other rules that have not happened, and the warning about them belongs where
whoever drops a row's padding is already reading, which is the comment on each card, and both
comments have the arithmetic in more detail than this file did.

One thing the close had to fix: both card comments, and two other comments in the same stylesheet,
pointed at `docs/refinements/body-overlay.md`, a file deleted when the backlog became one file per
task. No check reads a bare path inside a CSS comment, so four dead pointers had sat there
unreported. They now name the decision, the rail-width entry
([R-146](146-reserved-rail-assumed-width.md)) and the host work for the transparent-window pass.

## History

- 2026-07-20: Measured in both themes at deviceScaleFactor 1 and filed when scrollbars became
  reserved chrome.
- 2026-08-09: A trigger review read it against the tree and fired nothing:
  `body/app/src/overlay.css:37` still declared `--rail: 6px`, with the sheet's geometry note at
  line 31 still recording both surfaces at 6px.
- 2026-08-18: Declined after reading the tree again. The declaration has moved three lines since
  that review and is otherwise unchanged, both cards and both row paddings are as measured, and no
  pixel moved in this change. The reasoning is recorded at the origin decision.
