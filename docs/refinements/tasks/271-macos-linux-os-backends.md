# macOS and Linux OS backends

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** none, this area is the old catch-all list and has no single origin decision record
**Verified:** 2026-10-04

Real backends behind the existing OS traits where they are still `unimplemented!()` stubs. No
Linux stub is left, and four macOS ports still are:

- **macOS `Hotkey`, `AudioControl` and `Notify`.** All three are stubs in `os_macos`, which has no
  `cfg` attribute yet and compiles on every platform. A real macOS backend takes
  `cfg(target_os = "macos")` as `os_windows` takes `cfg(windows)`, which also leaves it out of the
  Linux coverage run.
- **`ScreenCapture` on both** is [263](263-linux-and-macos-capture-backends.md).

Linux `Notify`, `AudioControl`, an X11 `ScreenCapture` and an X11 `Hotkey` are built. The shell's
body server serves the first two, with every capture refused, and the shell registers the hotkey
except on a Wayland session, which needs the portal
([765](765-a-wayland-hotkey-through-the-globalshortcuts-portal.md)). How a Linux backend is
structured so the 100% coverage rule holds, a covered core over a port of its own plus an adapter
tested against a peer the test controls, is [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 13,
and every Linux backend follows it.

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
- 2026-09-28: The Linux X11 capture backend was built under
  [263](263-linux-and-macos-capture-backends.md), which leaves the Linux `Hotkey` as the one Linux
  stub.
- 2026-10-01: Built the X11 `Hotkey`: `LinuxHotkey` over a `KeyGrab` port, and `X11Keys` tested
  against a fake X server, at 100% line and branch coverage. Against `Xvfb` 21.1.12 the live test
  grabbed `ctrl+alt+space`, and XTEST presses of it ran the callback once with Num Lock off and once
  with it on, while `ctrl+space` did not run it. Holding the chord for 1.5 s first ran the callback
  22 times on Xvfb and on WSLg's Xwayland, one per auto-repeat, which Windows avoids with
  `MOD_NOREPEAT`; the backend now skips a press with the time of the release before it, and the same
  hold runs it once on both servers, three runs out of three on WSLg. The first WSLg run, before
  that change, missed the first press of the chord and the next four did not. The shell's Linux
  `hotkey::register` grabs the configured chord through it and grabs nothing when `WAYLAND_DISPLAY`
  is set, and both `just check-shell` halves passed on this host from a userspace prefix built
  without sudo ([readings](../../readings/shell-clippy.md)). Filed
  [765](765-a-wayland-hotkey-through-the-globalshortcuts-portal.md).
- 2026-10-04: Checked again. The four macOS ports are still `unimplemented!()` stubs, and
  `os_macos` still has no `cfg(target_os)` in its source or manifest, so it compiles and is measured
  here. None of it can be built or checked on this Linux host. The X11 window target was built under
  [263](263-linux-and-macos-capture-backends.md), so no Linux capture part is left in either entry.
