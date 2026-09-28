# macOS and Linux OS backends

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** none, this area is the old catch-all list and has no single origin decision record
**Verified:** 2026-09-28

Real backends behind the existing OS traits where they are still `unimplemented!()` stubs. Two
ports are left on Linux and four on macOS:

- **Linux `Hotkey`.** `LinuxHotkey` is a stub. A global shortcut needs the XDG desktop portal's
  `GlobalShortcuts` interface on Wayland and a key grab on X11, and the shell's
  `hotkey::register` is a stub off Windows.
- **macOS `Hotkey`, `AudioControl` and `Notify`.** All three are stubs in `os_macos`, which has no
  `cfg` attribute yet and compiles on every platform. A real macOS backend takes
  `cfg(target_os = "macos")` as `os_windows` takes `cfg(windows)`, which also leaves it out of the
  Linux coverage run.
- **`ScreenCapture` on both** is [263](263-linux-and-macos-capture-backends.md).

Linux `Notify` and `AudioControl` are built, and the shell's body server serves both, with every
capture refused. How a Linux backend is structured so the 100% coverage rule holds, a covered core
over a port of its own plus an adapter tested against a peer the test controls, is
[ADR-0011](../../adr/ADR-0011-body-v1.md) decision 13, and a Linux `Hotkey` follows it.

This stays a refinement rather than moving to [docs/host/](../../host/index.md), which holds work
needing a Win32 desktop session or a 24 GB GPU: a Linux or macOS backend needs neither.

## History

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as one clause of the
  "Later, unordered" list.
- 2026-08-09: A costing pass found the coverage problem above, which is the reason the entry reads
  cheaper than it is, and wrote it down rather than changing the entry.
- 2026-09-13: Checked again and every substantive claim holds, while four cited pointers had moved.
  `os_linux` and `os_macos` are 70 lines each rather than 71, the coverage run is at
  `justfile:233` rather than 95 and still passes `--workspace`, the two halves of the collision are
  at [body-os.md](../../modules/body-os.md) line 51 rather than 42 and at the crate header lines 7
  to 8 rather than 7 to 9, and the origin decision still describes `os_macos` as `cfg(macos)`.
- 2026-09-28: Checked again and the coverage problem holds as written: `os_linux` was a plain
  workspace member measured by `cargo llvm-cov --workspace`, and ADR-0011 decision 3 described
  `cfg` attributes neither stub crate had. Resolved it as ADR-0011 decision 13, made `os_linux`
  `cfg(target_os = "linux")`, corrected decision 3, and built Linux `Notify` over the session bus
  (`zbus`) and `AudioControl` over `pactl`, both at 100% coverage. Both live tests passed on this
  host, against a real session bus with `dunst` 1.9.2 serving notifications and against the WSLg
  PulseAudio 17.0 server. The shell's Linux `start` now serves both through `BodyService`, and a
  run of that composition outside Tauri showed a reminder on `dunst` and changed and restored the
  volume over gRPC. What remains is listed above, and a linked Linux build of the shell is
  [751](751-the-shell-has-never-been-linked-or-run-on-linux.md).
