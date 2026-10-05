# What WebView2 paints under the fenced scroll rule

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 22

[R-784](../../refinements/tasks/784-a-fitting-box-reserves-the-wrong-rail-on-webkitgtk.md) proposes
this block, so that WebKitGTK reserves the 6 px rail in a scroll box that fits as well as in one that
overflows:

```css
@supports selector(::-webkit-scrollbar) {
  .stage :is(.history, .thoughts-body, .confirm-draft, .field, .rows, .switcher, .reminders) {
    overflow-y: scroll;
  }
}
```

## What only this proves

The block was read on WebKitGTK and on Chromium under Linux
([scrollbar-gutter readings](../../readings/scrollbar-gutter.md)). On Chromium a fitting box paints
nothing in its band under it, and the one change in the built overlay is the reminder stack's
bottom border moving to the row nearest its layout edge, where an overflowing stack already paints
it. WebView2 is the engine the overlay ships on, and it runs on Windows, often at a display scale
above 100 %. Only a WebView2 read says whether it paints the same.

## Bring-up

The [windows-desktop](../index.md#windows-desktop) bring-up, unchanged, with at least two fired but
undelivered reminders, so the reminder stack shows, and one chat long enough to scroll.

## Do, and what to write down

1. Open the overlay in `npm run tauri dev` and open WebView2's DevTools on it.
2. With the reminder stack showing and a short chat open, take a screenshot of the panel. Add the
   block above as a new style rule in DevTools and take a second one. Compare the two pixel by
   pixel and write down every region that differs.
3. Repeat with the long chat, so `.history` overflows, and with a draft in the composer long enough
   to reach the field's cap, so `.field` overflows.
4. Do steps 2 and 3 at the display's own scale and at 100 %.

## Pass looks like

No box that fits paints a track or a thumb in its 6 px band under the block, no overflowing box
paints differently, and the only regions that differ are a fitting box's edges moving by one row.

## Fail, and what each failure means

- **A fitting box shows a track or a thumb.** WebView2 paints a disabled scrollbar where Chromium
  under Linux does not. The block stays out, and R-784 records what was seen.
- **Text or a row moves.** The block changes layout on WebView2, which it does not on Chromium.
  The block stays out until the cause is found.

## Record it

Put the counts in the [scrollbar-gutter readings](../../readings/scrollbar-gutter.md). On a pass,
R-784 ships the block. Then delete this section, per the exit contract in [index.md](../index.md).

## History

- 2026-10-05: Filed when Chromium's one paint change under the block was traced to the reminder
  stack's fractional height, which left WebView2 as the last engine to read.
