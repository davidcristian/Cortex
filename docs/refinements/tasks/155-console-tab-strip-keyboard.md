# The console tab strip's missing keyboard half

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

The console tab strip had `role="tablist"`, a `role="tab"` per face and `aria-selected`, but no
keyboard navigation: both tabs were separate tab stops and Left/Right did nothing, where the ARIA
practice is one tab stop for the whole strip with arrows moving along it. A pane on its way out was
`aria-hidden` but still focusable, so Tab pressed during a crossing could move focus into it.

Both are fixed. The strip is one tab stop, using a roving `tabIndex` that is 0 on the selected face
and -1 on the others; no extra state is needed because selection follows focus. `overlay/tabStrip.ts`
maps the keys: arrows step along the strip and wrap, Home and End go to the ends without wrapping,
the vertical arrows are left to the chat-cycling shortcuts, and the four handled keys call
`preventDefault` because the panel clips its overflow. The leaving pane is `inert` as well as
`aria-hidden`, from one function (`overlay/withdrawn.ts`) used in all three places the overlay keeps
something mounted but off screen, the third being the dismissed panel itself.

The entry's stated blocker, that React types `inert` only from version 19, was wrong: only the type
is missing. Against react-dom 18.3.1, `inert=""` renders `<div inert="">` and `inert={undefined}`
removes it; only `inert={true}` is dropped. One module augmentation adds the type, narrowed to `""`.
Nothing was upgraded.

Measured in Chromium at 900x900 before and after: the strip went from two tab stops to one, five
arrow and Home/End presses from doing nothing to moving focus and selection together, the leaving
view from three reachable stops to zero, the tab crossing from six to zero, and the dismissed panel
from six to zero.

## History

- 2026-07-20: Opened when the two settings views became one console.
- 2026-08-03: Both halves closed. The same pass opened the chat switcher's role mismatch, whose
  `role="listbox"` disagrees with its own rows. The entry's blocker was reasoning from a version
  number to a capability, which one `renderToStaticMarkup` call disproved.
