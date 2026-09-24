# The window size sentence is unmeasured

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-24

Since 2026-09-24 the text beside a window capture says "downscaled from the window's WxH" or "at
the window's own size", from the reply's `target_width` and `target_height`. No draw has shown
whether that changes what the cortex reads. Two captions over a shrunk screen changed nothing:
offered "unreadable" as an answer, the cortex declined 3 of 47 strings and invented 38. So no change
is the expected result. The row that could show one is the 2400 px spreadsheet window of 2026-08-10
in [vision-capture](../../readings/vision-capture.md), which is wider than the edge and so
resampled.

`window_crop_probe.py` now builds its captures with the target size, as the body does, so its focus
rows include the sentence. A redraw of those rows is therefore not the input of the 2026-08-10 rows,
and a comparison with them must say so. The draw is a GPU question: pair the resampled window with
and without the sentence at the deployed budget and edge, and pre-register the depth and the
deciding count before any row is drawn.

## History

- 2026-09-24: Opened by the close of [R-253](253-reply-says-window-resampled.md), which added the
  sentence without a measurement.
