# macOS OS backends

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** none, this area is the old catch-all list and has no single origin decision record
**Verified:** 2026-10-06

Real macOS backends behind the five OS ports in `body_core`: `Hotkey`, `AudioControl`, `Notify`,
`ScreenCapture` and `ClipboardPicture`. The Linux half is done. `os_linux` has a real backend
behind each port and no stub, and the shell serves or registers every one of them on X11 and on
Wayland ([body-os.md](../../modules/body-os.md)). What is left is macOS, in three parts:

- **`MacosHotkey`, `MacosAudioControl`, `MacosNotify` and `MacosClipboardPicture`**, which are
  `unimplemented!()` stubs in `os_macos`. The shell's `clipboard_picture` command answers with
  `NoClipboardPicture` off Linux, so the last one is needed only if the macOS webview gives the
  page no file for a pasted picture, as WebKitGTK does.
- **`MacosScreenCapture`**, also a stub, which is [263](263-linux-and-macos-capture-backends.md).
- **The crate and the shell around them.** `os_macos` has no `cfg` attribute in its source or
  manifest, so it compiles on every platform and the Linux coverage run measures it. A real backend
  takes `cfg(target_os = "macos")` as `os_windows` takes `cfg(windows)` (ADR-0011 decision 3). The
  shell does not depend on `os_macos`: off Windows and Linux, `body_server::start` and
  `hotkey::register` only print that the platform has no backend, so a macOS backend also adds a
  `cfg(target_os = "macos")` dependency table to the shell and both functions.

How the 100% coverage rule holds for a Linux backend, a covered core over a port of its own plus an
adapter tested against a peer the test controls, is [ADR-0011](../../adr/ADR-0011-body-v1.md)
decision 13. Every CI job runs on Ubuntu. `os_windows` is clippied for its own target from Linux
(decision 9), and a macOS adapter can be type-checked the same way, measured in
[macos-cross-check.md](../../readings/macos-cross-check.md): `os_macos` passes clippy for
`aarch64-apple-darwin` on this host with no SDK and no system package, and so do calls into the
`objc2` framework crates, `global-hotkey`, `xcap` and `arboard`. The `screencapturekit` crate
fails, since its build scripts run `swift`, while `objc2-screen-capture-kit` passes. A test binary
for that target fails to link without the SDK, so testing and running one needs a Mac.

The check costs little to add, but adds nothing yet: `os_macos` has no `cfg`, so the workspace
clippy already checks the same code on Linux. Once it takes `cfg(target_os = "macos")` and compiles
to nothing here, `check-body` takes a line beside the `os_windows` one, inside `just check` because
it needs no system library. That is one `cargo clippy` line, `aarch64-apple-darwin` in the
`targets` of the CI job that runs `check-body`, the `rustup target add` step in
[local-dev-wsl.md](../../runbooks/local-dev-wsl.md), and a sentence in ADR-0011 decision 9. Each
machine pays a 127 MB target download, and a cold run took under a twentieth of a warm `just check`.

This stays a refinement rather than moving to [docs/host/](../../host/index.md), which holds work
needing a Win32 desktop session or a 24 GB GPU: a macOS backend needs neither, only a Mac.

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
- 2026-10-05: Checked again after the Wayland work, and narrowed to macOS. Two Linux claims were
  wrong. The shell serves a capture when `CORTEX_HOST_CAPTURE=1`, `LinuxScreenCapture` on X11 and
  `LinuxPortalCapture` on Wayland with a focus request sent to `LinuxWindowCapture`, rather than
  refusing every capture. And on Wayland it registers the hotkey through `LinuxKdeHotkey` where
  `kglobalaccel` runs, else `LinuxPortalHotkey`, so
  [765](765-a-wayland-hotkey-through-the-globalshortcuts-portal.md) is done. The capture bullet named
  both platforms, while 263 now holds only `MacosScreenCapture`. The shell wiring a macOS backend
  also needs was never named and is added. A live test of the portal hotkey on a real backend is
  [788](788-test-the-portal-hotkey-on-a-kde-wayland-session.md).
- 2026-10-06: Corrected after the paste path moved. `body_core` has a fifth OS port,
  `ClipboardPicture`, with `LinuxClipboardPicture` behind it in `os_linux` and a
  `MacosClipboardPicture` stub in `os_macos`, and the entry named four ports and three stubs. The
  Linux reader reads the Wayland clipboard in a Wayland-client shell and the X selection otherwise.
- 2026-10-06: Measured whether a macOS backend can be checked here, which the entry left open. With
  the `aarch64-apple-darwin` target added, clippy passes on `os_macos` and on a scratch crate per
  likely dependency except `screencapturekit`, whose build scripts need `swift`; linking needs the
  SDK. Wrote the results and what wiring the check into `just check` costs, without adding it.
