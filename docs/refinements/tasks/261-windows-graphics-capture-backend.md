# A `Windows.Graphics.Capture` backend

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-13

GDI renders hardware-overlay and DRM-protected surfaces black with no message, and no
`CaptureError` distinguishes that from a genuinely dark screen. WGC also draws a yellow OS capture
border for free, which is the best privacy signal on offer and the one thing deliberately given up.
It costs async frame arrival against a deliberately synchronous port, WinRT interop, a D3D11
staging copy, and a Windows 11 22H2 minimum to control the border. Two more costs are recorded in
the GDI backend's own header: WGC needs a COM apartment, which GDI was picked partly to avoid,
because two backends already initialize COM on the body's blocking-pool threads without balancing
it; and WGC keeps a persistent capture device, where the body server hands each capture to an
arbitrary blocking-pool thread as an `FnOnce + Send + 'static` closure. One thing a change does not
cost is the overlay's self-exclusion: `WDA_EXCLUDEFROMCAPTURE` is set at DWM level, so it applies
to WGC exactly as to GDI. Behind the unchanged `ScreenCapture` trait either way.

## History

- 2026-07-18: Recorded when the vision slice was finished.
- 2026-07-19: Grouped with the Linux and macOS `ScreenCapture` backends, as the one of the three
  that buys something GDI cannot.
- 2026-08-09: A costing pass left it as written, its Windows argument untouched.
- 2026-09-13: Checked against the backend and two costs added. The silent-black limitation is still
  the reason to want WGC and is still recorded in `body/crates/os_windows/src/screen.rs`, which
  also gives the rest of the GDI argument: no COM apartment, no persistent device, and the smallest
  `unsafe` surface. Those last two are costs on the WGC side that this entry never named. The
  self-exclusion is the one cost a reader would expect and it is not one. The backend header also
  records that no blit in it has ever run: it is compiled and clippy-linted for the Windows target
  from Linux, which type-checks it against the port and nothing more. So whoever weighs WGC against
  GDI is weighing two descriptions, not a measurement against a description.
