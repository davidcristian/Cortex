# Keep the overlay out of a Linux capture

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-28

The shell's Linux `start` in `body/app/src-tauri/src/body_server.rs` serves `DeniedScreenCapture`,
although `LinuxScreenCapture<X11Root>` in `os_linux` works. ADR-0029 decision 10 allows a real
capture only when the overlay is kept out of every picture, since text an attacker gets into a
reply would otherwise be read back as screen content, and `exclude_overlay` returns `false` off
Windows. X11 has no equivalent of `WDA_EXCLUDEFROMCAPTURE`.

Three ways to keep it out on X11:

- Under `GrabServer`, read the root, then fill black every top-level window whose `_NET_WM_PID`
  is this process. The overlay's text never leaves the body, and the pixels under it are lost.
  The fill belongs in the covered core, the window list in `RootGrab`.
- With the Composite extension, build the picture from every mapped top-level window except the
  body's own. It keeps what lies under the overlay, but needs a compositing manager and many more
  requests.
- Hide the overlay around the capture. It flickers, and the capture races the repaint of what was
  under it.

The first is the smallest and fails closed. With one in place, the Linux `start` serves
`LinuxScreenCapture<X11Root>` when `CORTEX_HOST_CAPTURE=1`, `x11rb::connect(None)` succeeds and the
exclusion works, and `DeniedScreenCapture` otherwise, as the Windows `start` does. Running it in
the real shell waits on [751](751-the-shell-has-never-been-linked-or-run-on-linux.md).

## History

- 2026-09-28: Filed when the Linux X11 capture backend was built under
  [263](263-linux-and-macos-capture-backends.md).
