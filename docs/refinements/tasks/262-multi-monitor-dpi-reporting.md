# Multi-monitor and DPI reporting

**Status:** open, waiting for a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** The first code in the body or the overlay that enumerates monitors, or a request to
capture a display other than the primary one.

v1 captures the primary display only, in physical pixels. Nothing enumerates monitors, which is why
no field names one. A display index takes the next free field number when it arrives, and it
arrives together with a body that honours it, which is the rule that put the capture target and its
Z-order walk in one commit. The focus target already gives this entry one observable consequence: a
focused window on a second monitor resolves to a rectangle with nothing on the captured display, so
it returns `NoTarget` rather than a wrong picture.

## History

- 2026-07-18: Recorded when the vision slice was finished.
- 2026-07-19: Recorded as one of three vision surfaces nothing reads, beside the content-addressed
  `AttachmentStore` and pixel-level screening in the body, with its consumer named as the one
  region capture was already waiting for.
- 2026-08-10: Corrected. The entry used to say `CaptureScreenRequest` reserves field 2 for a
  display index. Field 2 was held by a comment rather than by a protobuf `reserved` statement, and
  the capture target took it, on the argument that a target covers what the number was being kept
  for. `display_index` is counted here rather than on the region and window capture entry, which
  stopped naming it the same day.
- 2026-09-13: Checked against the code and unchanged. Nothing enumerates monitors: the Windows
  backend sizes its blit from `GetSystemMetrics`, which reports the primary display and nothing
  else, and no other call in the body asks the OS for a monitor list. `CaptureScreenRequest` now
  uses fields 1, 2 and 3 for `max_edge`, the target and `max_bytes`, so a display index takes 4.
  `CapturedFrame::region` clamps a focused window into the captured display and returns `NoTarget`
  when nothing is left, with no fallback to the whole screen. The trigger has not occurred.
- 2026-09-19: Checked again, with the trigger restated and the physical-pixel claim traced to where
  it is really set. Nothing enumerates monitors, and `CaptureScreenRequest` still uses fields 1 to
  3. The physical pixels depend on the process being per-monitor DPI aware, which the doc comment
  on `display_size` in `os_windows/src/screen.rs` credited to the manifest. No manifest in this
  tree says so: the shell's is tauri-build 2.6.3's default, which declares only the Common Controls
  dependency. The awareness is set at run time by tao 0.35.3, whose Windows event loop calls
  `SetProcessDpiAwarenessContext` with the per-monitor V2 context when it is created (its
  `dpi_aware` attribute defaults to true and Tauri does not change it), which is before the shell's
  `setup` starts the body server and so before any capture. The comment says that now. Nothing in
  this tree asserts it, so a tao release that dropped the call would turn every size into logical
  points with no check failing; the per-monitor DPI row of the display capture host task (H-012) is
  where that would be seen.
