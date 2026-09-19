# Multi-monitor and DPI reporting

**Status:** open, dead until a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** The first code in the body or the overlay that enumerates monitors, or a request to
capture a display other than the primary one.

v1 is the primary display only, in physical pixels.
Nothing enumerates monitors yet, which is why no field names one.
**Corrected 2026-08-10:** this entry used to say `CaptureScreenRequest` *reserves field 2* for a
display index. It does not any more. Field 2 was held by a comment rather than by a protobuf
`reserved` statement, and the capture target spent it, on the argument that a target subsumes
the ask the number was being kept for. A display index needs the next free number when it
arrives, and it arrives with a body that honours it, which is the rule that put the target and
its Z-order walk in one commit. The focus target also gives this entry a first observable
consequence: a focused window on a second monitor resolves to a rectangle with nothing on the
captured display, so it answers `NoTarget` rather than a wrong picture.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index recorded it as one of three vision surfaces nothing reads, beside the
  content-addressed `AttachmentStore` and pixel-level screening in the body, and named its consumer
  as the one region capture was already waiting for.
- 2026-08-10: corrected. The clause naming `CaptureScreenRequest`'s unassigned field 2 as the
  evidence was wrong, since the capture target spent that number, a target subsuming the ask the
  comment was holding it for, so a display index takes the next free one and arrives with a body
  that honours it. `display_index` is counted here rather than on the region and window capture
  entry, which stopped naming it the same day.
- 2026-09-13: held against the code and unchanged. Nothing enumerates monitors: the Windows
  backend sizes its blit from `GetSystemMetrics`, which reports the primary display and nothing
  else, and no other call in the body asks the OS for a monitor list. `CaptureScreenRequest` now
  spends fields 1, 2 and 3 on `max_edge`, the target and `max_bytes`, so a display index takes 4,
  which is what the correction above predicted. The consequence this entry named is in the code
  as written: `CapturedFrame::region` clamps a focused window into the captured display and
  answers `NoTarget` when nothing is left, with no fallback to the whole screen. The trigger has
  not fired.
- 2026-09-19: re-derived, with the trigger restated and the physical-pixel premise traced to where
  it is really set. Nothing enumerates monitors: the Windows backend still sizes its blit from
  `GetSystemMetrics`, neither the overlay nor the shell asks Tauri for a monitor, and
  `CaptureScreenRequest` still spends fields 1 to 3, so a display index still takes 4. The physical
  pixels in this entry's first line depend on the process being per-monitor DPI aware, which the
  doc comment on `display_size` in `os_windows/src/screen.rs` credited to the manifest. No
  manifest in this tree says so: the shell's is tauri-build 2.6.3's default, which declares only
  the Common Controls dependency. The awareness is set at run time by tao 0.35.3, whose Windows
  event loop calls `SetProcessDpiAwarenessContext` with the per-monitor V2 context when it is
  created (its `dpi_aware` attribute defaults to true and Tauri does not change it), which is
  before the shell's `setup` starts the body server and so before any capture. The comment now
  says that. Nothing in this tree asserts it, so a tao release that dropped the call would turn
  every size into logical points with no gate failing; the per-monitor DPI row of the display
  capture host task (H-012) is where that would be seen. The old trigger carried a clause that was
  true the day it was written ("which nothing does yet") and a design rule rather than an event
  (the field arriving with a body that honours it, which the description above keeps).
