# Check the Linux capture under a window manager and a compositor

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-01

The X11 capture paints black every viewable window whose `_NET_WM_PID` is the body's process
([753](753-keep-the-overlay-out-of-a-linux-capture.md)). It was checked in the linked shell on a
bare `Xvfb`, with no window manager, no compositing manager, and WebKitGTK's compositing mode and
DMA-BUF renderer turned off. Three conditions of a real X11 desktop were not checked:

- **A reparenting window manager** puts a frame window between the root and the overlay. The walk
  covers the whole tree and a fake server test places a window inside a frame, but no real manager
  has done it.
- **A compositing manager** paints the screen from its own copy of each window. Under `GrabServer`
  it cannot repaint, so the picture is its last frame, which can still show the overlay where the
  window tree no longer reports it: a fade after a hide keeps an unmapped window on screen for the
  fade's length. If a capture taken then shows overlay pixels, the fill must also cover the
  process's windows that were viewable shortly before, and the reading decides how long.
- **WebKitGTK with compositing on.** Whether a window that a WebKit helper process creates, with
  that process's id, ever shows reply text on the root.

All three run on `Xvfb` from the userspace prefix in the
[shell clippy readings](../../readings/shell-clippy.md): a manager such as `openbox` and a
compositor such as `picom` fetched with `apt-get download`, the shell run as the
[overlay runbook](../../runbooks/body-overlay.md) says, and `CaptureScreen` called over gRPC. The
check: a capture over the shown overlay, and one taken within the fade after a hide, each come back
with no overlay pixel.

## History

- 2026-10-01: Filed when the X11 exclusion was built under
  [753](753-keep-the-overlay-out-of-a-linux-capture.md).
