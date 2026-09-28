# Linux and macOS `ScreenCapture` backends

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-28

`LinuxScreenCapture` and `MacosScreenCapture` are `unimplemented!()` stubs that satisfy the trait.
A host with capture switched off already runs the covered `DeniedScreenCapture` on every platform,
and the shell's Linux body server always serves it. The Windows shell wires its real backend only
after hiding the overlay from capture, and `exclude_overlay` returns `false` off Windows, so a Linux
backend also needs a way to keep the overlay out of its pictures before the shell can serve it.

On Linux, a capture on Wayland goes through the XDG desktop portal's `Screenshot` or `ScreenCast`
interface over the session bus, and on X11 through the X server. The coverage question this entry
used to raise is answered: [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 13 structures a Linux
backend as a covered core over a port of its own plus an adapter holding only the calls, and the
Linux `Notify` backend already reaches the session bus that way through `zbus`. The backend returns
raw BGRA pixels and the resolved target rectangle; every size decision stays in `body_core`
(ADR-0029). On macOS, `os_macos` takes `cfg(target_os = "macos")` first, since it compiles on
every platform today.

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
