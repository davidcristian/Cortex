# A streamed bubble's wrap width measured once

**Status:** landed 2026-08-18
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)

The whisper lays its letter DOM at the
final wrap width measured when the bubble mounts (ADR-0037 decision 4), so a window resized
mid-stream keeps the old wrap until the next message. Invisible in the v1 body, whose 640x720
window cannot resize; only the browser dev flow can see it. The fix is re-measuring on a
resize and re-laying the letters, which moves only invisible ones if the front is held during
the re-lay.
Placed here 2026-07-21.

## Trail

- 2026-07-21: Joined the fix-when-it-bites bucket when the streaming redesign landed.
- 2026-08-09: A trigger sweep of that bucket ran against the tree and fired nothing. This entry was
  checked at the site that would have to have moved, and `body/app/src-tauri/tauri.conf.json:20`
  still declares `"resizable": false`.
- 2026-08-18: Landed, and the re-derivation found the entry had undercounted itself twice. The cost
  is not confined to the bubble that was streaming: every once-streamed bubble keeps its letter DOM
  and the hard px box the clock left it on, and nothing else revisits either, so a resized window
  left the whole conversation laid for a width that no longer existed. And the re-lay cannot hold
  the front the way the text above hoped, because a genuine re-wrap moves visible letters too;
  what makes that harmless is that a letter's paint is its own inline opacity rather than a fact
  about where it sits, which is a plain text bubble's behaviour beside it. `whisper/metrics.ts` now
  holds the measurement, the box arithmetic both a frame and a resize pose from, and `watchWrap`;
  the clock re-lays on a real wrap change and re-poses at once when its loop has already stopped.
  ADR-0037 carries the dated addendum, including why the trigger is the window rather than a
  `ResizeObserver` on the log. The assumption that makes the window a complete trigger is filed as
  [311](311-wrap-width-trigger-completeness.md).
