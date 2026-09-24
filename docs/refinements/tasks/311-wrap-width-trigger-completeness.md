# A wrap width change with no resize event behind it

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Trigger:** the panel's width ceasing to be derived from the viewport, whether by a user-resizable
panel, a width read from the appearance record, or a layout that gives the log a width of its own.
In the tree that reads as the `.panel` rule's `width: min(560px, 92vw)` in
`body/app/src/overlay.css` changing, or as a script writing a width to anything but a whisper bubble
or its text. This search finds four writes today, all in `whisper/useWhisperClock.ts`:
`grep -rnE 'style\.(max|min)?[wW]idth|setProperty\("(max-|min-)?width"' body/app/src --exclude='*.test.*'`.
**Verified:** 2026-09-24

The whisper re-measures its wrap width and re-lays the letter DOM when the width changes. It
listens for the window's own `resize` event (`whisper/metrics.ts`, `watchWrap`), which is a
complete account of when the wrap can change only while the log's width is a function of the
viewport and nothing else. Today it is: `.panel` is `width: min(560px, 92vw)`, so every width the
log can take comes from the viewport.

If anything else moves the panel's width, the wrap changes with no `resize` behind it and the
letters stay laid out for the old width. The candidates are ordinary: a drag handle on the panel, a
width in the appearance record beside the theme and the window edge, or a screen-sized transparent
window whose log is inset by something other than a percentage of the viewport.

The general instrument is a `ResizeObserver` on the log, rejected once for a reason that still
holds: the log's height follows the posed bubble every frame of every stream, so the callback would
run per frame, and writing the letter DOM's width inside an observation of an ancestor raises the
"loop completed with undelivered notifications" error `overlay/panelWatch.ts` already hit once. The
way through is the one that hook found: stop observing for the frame the write happens in and
resume on the next, and compare the width before calling anything, so a bubble's own pose is not
read as a wrap change. Either way the change is contained to `watchWrap`, which is one function
with one caller.

## History

- 2026-08-18: Opened by the close of [159](159-streamed-bubble-wrap-width.md), whose fix is
  complete under an assumption about the panel's width that is true today and is written down here
  rather than assumed silently.
- 2026-09-11: Read against the tree and not fired. `.panel` is still `width: min(560px, 92vw)`
  (`overlay.css` line 269) and `watchWrap` in `whisper/metrics.ts` still subscribes to the window's
  `resize` and nothing else. The three candidates are all absent: no drag handle or resizable panel
  exists under `body/app/src`, the preferences record in `overlay/usePreferences.ts` and
  `overlay/overlayState.ts` has no width, and the log is still inset by the panel rule alone. Two
  `ResizeObserver`s run in the overlay, `overlay/measured.ts` publishing a watched element's height
  as a custom property and `components/PanelEdge.tsx` measuring the edge box, and both read a size
  rather than set one. The 16 tests in `useWhisperClock.test.ts`, one of which resizes the window
  mid-stream and asserts the letters re-lay, pass.
- 2026-09-17: Read against the tree and not fired, and the trigger restated as the readings that
  decide it. No commit since 2026-09-11 touched `.panel`'s width or `whisper/metrics.ts`, and
  `watchWrap` still listens to the window's `resize` alone. The 2026-09-11 entry undercounted the
  overlay's `ResizeObserver`s: there are three, the third being `watchSize` in
  `overlay/panelWatch.ts`, which observes the panel and re-runs its placement. That placement sets
  no width (`panelPlacement.ts`, `panelGeometry.ts`, `panelMemory.ts` and `usePanelMotion.ts` never
  mention `width`), so none of the three can move the wrap. The preferences record still has no
  width. The 16 tests in `useWhisperClock.test.ts` pass.
- 2026-09-24: Read against the tree and not fired, and the script reading widened. `.panel` is
  still `width: min(560px, 92vw)` (`overlay.css` line 135), `watchWrap` in `whisper/metrics.ts`
  still listens to the window's `resize` alone, and the preferences record has no width. The old
  search, `style.width`, missed a `maxWidth` or `minWidth` write and a `setProperty("width", ...)`,
  so the trigger now reads all three forms; it finds the same four writes. The 2026-09-17 list of
  placement files left out `panelEdge.ts` and `panelRoll.ts`, both renamed since, and neither
  mentions `width`. The 16 tests in `useWhisperClock.test.ts` pass.
