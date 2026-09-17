# A wrap change the window never announces

**Status:** open, fix when it bites
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Trigger:** the panel's width ceasing to be derived from the viewport, whether by a user-resizable
panel, a width read from the appearance record, or a layout that gives the log a width of its own.
In the tree that reads as the `.panel` rule's `width: min(560px, 92vw)` in
`body/app/src/overlay.css` changing, or as a script writing a width to anything but a whisper bubble
or its text: `grep -rn 'style.width' body/app/src --exclude='*.test.*'` finds four writes today, all
in `whisper/useWhisperClock.ts`.
**Verified:** 2026-09-17

Opened 2026-08-18 by the close of [159](159-streamed-bubble-wrap-width.md), which taught the
whisper to re-measure its wrap width and re-lay the letter DOM when it changes. The trigger it
listens for is the window's own `resize` (`whisper/metrics.ts`, `watchWrap`), and that is a
complete account of when the wrap can change for exactly as long as the log's width is a function
of the viewport and nothing else. Today it is: `.panel` is `width: min(560px, 92vw)`, so every
width the log can take is a viewport width, and no other input reaches it.

The day something else moves the panel's width, the wrap changes with no `resize` behind it and the
letters stay laid for the old one, which is the defect the close removed, reappearing from a
different cause. The candidates are ordinary rather than exotic: a drag handle on the panel, a width
in the appearance record beside the theme and the window edge, or a screen-sized transparent window
whose log is inset by something other than a percentage of the viewport.

**What would close it.** The general instrument is a `ResizeObserver` on the log, and the close
rejected it for a reason that survives this change: the log's own height follows the posed bubble
every frame of every stream, so the callback would run per frame, and writing the letter DOM's width
inside an observation of an ancestor re-gathers at the same depth and raises the "loop completed
with undelivered notifications" error `overlay/panelWatch.ts` already paid for once. The way through
is the one that hook found, so read it first: drop the observation for the frame the write happens
in and take it back up on the next, and compare the width before calling anything, since a bubble's
own pose must not read as a wrap change. Whichever instrument wins, the watch is already one
function with one caller, so the change is contained to `watchWrap`.

## Trail

- 2026-08-18: opened by the close of [159](159-streamed-bubble-wrap-width.md), whose fix is
  complete under an assumption about the panel's width that is true today and is written down here
  rather than trusted silently.
- 2026-09-11: read against the tree and not fired. `.panel` is still `width: min(560px, 92vw)`
  (`overlay.css` line 269) and `watchWrap` in `whisper/metrics.ts` still subscribes to the window's
  `resize` and nothing else. The three candidates the trigger names are all absent: no drag handle or
  resizable panel exists under `body/app/src` (the composer's comment names a resizable window as a
  hypothetical), the preferences record in `overlay/usePreferences.ts` and `overlay/overlayState.ts`
  carries no width, and the log is still inset by the panel rule alone. Two `ResizeObserver`s do run
  in the overlay, `overlay/measured.ts` publishing a watched element's height as a custom property
  and `components/PanelEdge.tsx` measuring the edge box, and both read a size rather than set one,
  so neither can move the wrap. `overlay/panelWatch.ts` still carries the undelivered-notifications
  lesson the body points at. The 16 tests in `useWhisperClock.test.ts`, one of which resizes the
  window mid-stream and asserts the letters re-lay, pass.
- 2026-09-17: read against the tree and not fired, and the trigger restated as the readings that
  decide it. No commit since 2026-09-11 touched `.panel`'s width or `whisper/metrics.ts`, and
  `watchWrap` still listens to the window's `resize` alone. The 2026-09-11 line above undercounted
  the overlay's `ResizeObserver`s: there are three, the third being `watchSize` in
  `overlay/panelWatch.ts`, which observes the panel and re-runs its placement. That placement sets
  no width (`panelPlacement.ts`, `panelGeometry.ts`, `panelMemory.ts` and `usePanelMotion.ts` spell
  `width` nowhere), so none of the three can move the wrap. The preferences record still carries no
  width. The 16 tests in `useWhisperClock.test.ts` pass.
