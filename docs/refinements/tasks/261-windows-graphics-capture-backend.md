# A `Windows.Graphics.Capture` backend

**Status:** open, feature breadth
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

GDI renders hardware-overlay and DRM-protected
surfaces **black, silently**, with no `CaptureError` to distinguish that from a genuinely dark
screen. WGC also brings a free yellow OS capture border, which is the best privacy affordance
on offer and the one thing consciously given up. It costs async frame arrival against a
deliberately synchronous port, WinRT interop, a D3D11 staging copy, and a Windows 11 22H2 floor
to control the border. Behind the unchanged `ScreenCapture` trait either way.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index grouped it with the Linux and macOS `ScreenCapture` backends and called it
  the one of the three that buys something GDI cannot.
- 2026-08-09: a costing pass against the tree re-read it and left it parked exactly as written, its
  Windows argument untouched.
