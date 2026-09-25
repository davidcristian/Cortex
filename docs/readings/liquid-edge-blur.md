# Readings: the liquid edge's backdrop blur

The measurement behind [ADR-0036](../adr/ADR-0036-window-edge.md) decisions 5 and 7. Every reading
is pixels in a browser at a stated viewport, so it depends on the engine rather than on the machine.

**Method:** headless Chromium (Playwright's `chromium-1228` build) driving the real overlay over the
demo bridge at 640x720 with reduced motion, so the liquid holds one shape. `.stage`, the window's
ground, is replaced by a busy pattern of red and blue stripes over a 24px black and white
checkerboard, which stands in for the desktop behind a transparent window. Each variant is compared
with the same page with the glass slab hidden: the mean absolute channel difference over four 9px
squares at the corners of the slab's box (outside the rounded outline), and over a 12x80px band
just inside its left edge, where only glass paints.

## Clip, mask and the wrapper's filter

**2026-09-25**, both themes, the slab set to `--panel` with `blur(30px) saturate(140%)`:

| Variant | Outside the outline (dark, light) | Inside the band (dark, light) | Seen |
| --- | --- | --- | --- |
| `path()` clip, wrapper `drop-shadow` filter on | 4.43, 4.54 | 90.26, 77.06 | pattern sharp through a tint |
| `mask-image` of the same path, filter on | 4.44, 4.54 | 90.26, 77.06 | the same |
| `path()` clip, filter off | 0, 0 | 98.88, 93.94 | frosted, exactly inside the outline |
| `mask-image`, filter off | 0, 0 | 98.88, 93.94 | the same |

The outside difference with the filter on is the drop shadow itself. With it off, nothing outside
the outline changes, so the `path()` clip bounds the blur in this engine and a mask adds nothing.
The filter makes the wrapper the backdrop root, the element whose painting a `backdrop-filter`
reads, so with it on the glass had nothing behind it to blur. WebView2's engine is unmeasured.
