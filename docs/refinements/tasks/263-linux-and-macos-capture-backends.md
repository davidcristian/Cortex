# Linux and macOS `ScreenCapture` backends

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-04

`LinuxScreenCapture<X11Root>` in `os_linux` reads the primary RandR monitor of the X root window
through `x11rb`, built and covered under [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 13, and
answers both targets. The shell serves it on an X11 session when `CORTEX_HOST_CAPTURE=1`, with the
body's own windows painted black ([753](753-keep-the-overlay-out-of-a-linux-capture.md)); a Wayland
session needs the desktop portal, which is
[752](752-wayland-screen-capture-through-the-portal.md). One part remains here:

- **macOS.** `MacosScreenCapture` is an `unimplemented!()` stub. `os_macos` takes
  `cfg(target_os = "macos")` first, since it compiles on every platform today. It cannot be built
  or checked on this Linux host.

Every size decision stays in `body_core` (ADR-0029): a backend returns raw BGRA pixels and the
resolved target rectangle.

## History

- 2026-07-18: Recorded when the vision slice was finished.
- 2026-07-19: Grouped with the `Windows.Graphics.Capture` backend, as the same request as the macOS
  and Linux OS backends entry.
- 2026-08-09: A costing pass found the coverage problem above, which is why the entry reads cheaper
  than it is, and left the entry itself as written.
- 2026-09-13: Checked again. Every essential claim holds and three citations have moved. Both stub
  crates are 70 lines rather than 71, each capture stub is the `fn capture` at line 65, and the
  coverage half of the collision is now in [body-os.md](../../modules/body-os.md)'s escape-hatch
  section rather than at line 42. Neither stub crate has a `cfg(target_os)` attribute, in its
  source or its manifest, so both still compile and are measured on Linux while `os_windows` still
  builds to nothing there.
- 2026-09-28: Checked again. The coverage problem held and is now resolved by ADR-0011 decision 13,
  written while building the Linux `Notify` and `AudioControl` backends under
  [271](271-macos-linux-os-backends.md); `os_linux` is now `cfg(target_os = "linux")` and still
  measured on Linux CI, and `os_macos` still has no `cfg`. Rewrote the entry to what remains: the
  two capture backends themselves.
- 2026-09-28: The shell's Linux body server was wired with `DeniedScreenCapture`, and the overlay
  exclusion a Linux backend also needs was added above.
- 2026-09-28: Built the Linux X11 backend: `LinuxScreenCapture` over a `RootGrab` port, and
  `X11Root` tested against a fake X server. The display target reads one monitor, which
  `X11Root::layout` lists with RandR 1.5's `GetMonitors` (the primary flag and rectangle in one
  request, where `GetOutputPrimary` needs `GetOutputInfo` and `GetCrtcInfo` after it): the primary
  one, else the first listed, else the whole root, for the reasons in
  [body-os.md](../../modules/body-os.md). Against a real `Xvfb` 1280x720 display, RandR 1.6, it read
  a filled `ff8000` square back as blue 0, green 128, red 255; the one automatic monitor is not
  marked primary, so the first listed, the whole 1280x720, was read. With two 640x720 monitors added
  by `SetMonitor` and the right half filled `ff8000`, it returned the right one's 640x720 in that
  colour, and with neither marked primary the left one's, in black. WSLg's rootless Xwayland answers
  `GetImage` on its root with `BadMatch`. The shell still serves `DeniedScreenCapture`, because X11
  cannot keep the overlay out of a picture. Filed
  [752](752-wayland-screen-capture-through-the-portal.md) and
  [753](753-keep-the-overlay-out-of-a-linux-capture.md).
- 2026-10-01: Checked again. The shell's Linux `start` now serves `LinuxScreenCapture<X11Root>`,
  which paints the body's own windows black, so only the two parts above remain. The window target
  is still refused as `Backend`, and `MacosScreenCapture` is still a stub.
- 2026-10-04: Built the X11 window target, in `os_linux/src/focus.rs` over the window tree the grab
  already reads, rather than over `_NET_CLIENT_LIST_STACKING` as this entry proposed: that list
  exists only under an EWMH window manager, while the tree is there on every server and is read in
  the same server grab as the pixels. It takes the topmost viewable top-level window that is not
  `InputOnly` or override-redirect, has a non-empty `WM_NAME` on it or a window under it, and holds
  no window of this process and none whose `_NET_WM_WINDOW_TYPE` lists the EWMH dock or desktop
  type, with its frame and border, measured from the monitor's corner; none is `NoTarget`. Without
  that type check a panel would be picked, since EWMH stacks docks above normal windows. `X11Root`
  adds a zero-length `GetProperty` of `WM_NAME` and an `ATOM` `GetProperty` of
  `_NET_WM_WINDOW_TYPE` per window, and the Linux subject now runs the two focus checks of the
  screen check list. On `Xvfb` with no window manager the live test got no target over a titled
  desktop window and its own, then the 20 by 20 window at 10, 10 exactly, past an untitled window,
  the test's own titled one and a titled dock above it. Under `twm` 1.0.10, a reparenting manager
  run from a userspace extraction, it got that client's 26 by 46 frame, title bar and 3 pixel border
  included; the live tests place windows at fixed points, so both capture tests expect no window
  manager.
