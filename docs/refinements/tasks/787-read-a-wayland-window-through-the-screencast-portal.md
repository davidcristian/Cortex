# Read a Wayland window through the ScreenCast portal

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-05

On a Wayland session the shell captures through the portal's `Screenshot`, whose picture is the
whole output with no window list, so `HiddenOverlayCapture` refuses every capture while the overlay
is shown and for 1 s after it hides ([body-os-linux](../../modules/body-os-linux.md)). The overlay
is shown for most of a turn, so a model's `capture_screen` is refused unless the user hid the
overlay first. A focus capture is `NoTarget` there as well.

`org.freedesktop.portal.ScreenCast` with a window source streams one window's own buffer over
PipeWire, which a compositor renders without the windows above it, so the overlay cannot be in it.
The user picks the window in a dialog, and `persist_mode` with a restore token can keep that choice
across calls. A monitor source does not help, since it is the whole output, overlay included.

**Which backends offer a window source**
([wayland-screencast-portal](../../readings/wayland-screencast-portal.md)). `xdg-desktop-portal-wlr`
0.7.1 on sway 1.9 does not: its `AvailableSourceTypes` is 1, monitor only, and sway 1.9 lists no
protocol that copies one window's buffer. So on sway the overlay refusal stays. This distribution's
`xdg-desktop-portal-kde` 5.27.11 does (3), and it runs from a userspace prefix on a headless
`kwin_wayland --virtual`, where a window session reaches the chooser dialog and waits there.
GNOME's backend was not read.

**The next step is a probe on that KWin stack, before any body code.** It needs a way past the
chooser that needs no person: input into the dialog through `org_kde_kwin_fake_input`, which
KWin is assumed to offer any client while its permission checks are off, or a restore token from one
such choice. It needs a window to pick, such as a `qmlscene` window, and a consumer that reads one
frame from the stream's PipeWire node through the descriptor `OpenPipeWireRemote` returns, such as
GStreamer's `pipewiresrc`, which the prefix does not have yet. The probe decides whether a window
frame arrives at all, and whether a second `Start` with the restore token skips the dialog, which an
unattended capture needs.

**What the body would need after it.** A PipeWire client in `os_linux`, a new crate dependency
that also changes the Tauri shell's lock file; a store for the restore token; and a frame kind of
its own in body core. `ScreenCapture::capture` fits as it is, but `CapturedFrame::window` places a
window inside a display frame, and `covers_display()` would read a frame that is the window alone
as the whole display, so the receipt and the model would both say display. The window would be the
one the user picked, not the topmost one that decision 16 of the origin ADR defines as focus, so
that decision changes with it.

## History

- 2026-10-04: Filed when the shell started serving the portal capture under
  [752](752-wayland-screen-capture-through-the-portal.md) with the overlay refusal.
- 2026-10-05: Read the property on two backends. The wlr backend on sway offers monitor sources
  only (1), with cursor modes 3 and interface version 4 under a frontend at 5; the KDE backend
  offers monitor and window (3), with cursor modes 7, and ran headless under KWin. That answer
  closes the sway path the premise asked about; the task stays open for the probe on KWin.
