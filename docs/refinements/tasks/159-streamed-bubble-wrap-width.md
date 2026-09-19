# A streamed bubble's wrap width measured once

**Status:** done 2026-08-18
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)

The whisper laid out its letters at the wrap width measured when the bubble mounted (ADR-0037
decision 4), so a window resized mid-stream kept the old wrap until the next message. This was
invisible in the v1 body, whose 640x720 window cannot be resized; only the browser dev flow could
see it.

Fixed by re-measuring on a resize and laying the letters out again. `whisper/metrics.ts` now holds
the measurement, the box arithmetic that both a frame and a resize use, and `watchWrap`; the clock
lays out again on a real wrap change, and re-positions immediately when its loop has already
stopped. ADR-0037 decision 11 says why the trigger is the window rather than a `ResizeObserver` on
the log.

## History

- 2026-07-21: Filed when the streaming redesign was committed.
- 2026-08-09: A trigger review found `body/app/src-tauri/tauri.conf.json:20` still declares
  `"resizable": false`, so nothing had changed.
- 2026-08-18: Closed, and the entry had understated the problem twice. The cost was not confined to
  the bubble that was streaming: every bubble that had ever streamed kept its letter DOM and its
  fixed pixel box, so a resized window left the whole conversation laid out for a width that no
  longer existed. And the letters cannot be held in place during the re-layout, because a real
  re-wrap moves visible letters too; that is harmless because a letter's visibility is its own
  inline opacity rather than a fact about where it sits. The assumption that makes the window a
  complete trigger is filed as [311](311-wrap-width-trigger-completeness.md).
