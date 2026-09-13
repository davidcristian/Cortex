# A `Windows.Graphics.Capture` backend

**Status:** open, feature breadth
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-13

GDI renders hardware-overlay and DRM-protected
surfaces **black, silently**, with no `CaptureError` to distinguish that from a genuinely dark
screen. WGC also brings a free yellow OS capture border, which is the best privacy affordance
on offer and the one thing consciously given up. It costs async frame arrival against a
deliberately synchronous port, WinRT interop, a D3D11 staging copy, and a Windows 11 22H2 floor
to control the border. The GDI backend's own header names two more costs this entry did not:
WGC needs a COM apartment, which GDI was picked partly to avoid, because two backends already
initialize COM on the body's blocking-pool threads without balancing it; and WGC holds a
persistent capture device, where the body server hands each capture to an arbitrary
blocking-pool thread as an `FnOnce + Send + 'static` closure. One thing a swap does not cost is
the overlay's self-exclusion: `WDA_EXCLUDEFROMCAPTURE` is set at DWM level, so it holds for WGC
exactly as it holds for GDI. Behind the unchanged `ScreenCapture` trait either way.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index grouped it with the Linux and macOS `ScreenCapture` backends and called it
  the one of the three that buys something GDI cannot.
- 2026-08-09: a costing pass against the tree re-read it and left it parked exactly as written, its
  Windows argument untouched.
- 2026-09-13: re-derived against the backend and two costs added. The silent-black limitation is
  still the reason to want WGC and is still recorded in `body/crates/os_windows/src/screen.rs`,
  which also gives the rest of the GDI argument: no COM apartment, no persistent device, and the
  smallest `unsafe` surface. Those last two are costs on the WGC side that this entry never
  named, so it now does. The self-exclusion is the one cost a reader would expect and it is not
  one, the display-affinity call being DWM level. The backend header also records that no blit in
  it has ever run: it is compiled and clippy-linted for the Windows target from Linux, which
  type-checks it against the port and nothing more. So whoever weighs WGC against GDI is weighing
  two descriptions, not a measurement against a description.
