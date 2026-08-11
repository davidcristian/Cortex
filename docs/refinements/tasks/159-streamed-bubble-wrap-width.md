# A streamed bubble's wrap width measured once

**Status:** open, fix when it bites
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Trigger:** The transparent-window pass or any resizable overlay window.

The whisper lays its letter DOM at the
final wrap width measured when the bubble mounts (ADR-0037 decision 4), so a window resized
mid-stream keeps the old wrap until the next message. Invisible in the v1 body, whose 640x720
window cannot resize; only the browser dev flow can see it. The fix is re-measuring on a
resize and re-laying the letters, which moves only invisible ones if the front is held during
the re-lay. Trigger: the transparent-window pass or any resizable overlay window.
Placed here 2026-07-21.

## Trail

- 2026-07-21: Joined the fix-when-it-bites bucket when the streaming redesign landed.
- 2026-08-09: A trigger sweep of that bucket ran against the tree and fired nothing. This entry was
  checked at the site that would have to have moved, and `body/app/src-tauri/tauri.conf.json:20`
  still declares `"resizable": false`.
