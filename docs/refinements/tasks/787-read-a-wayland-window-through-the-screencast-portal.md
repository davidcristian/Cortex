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
`xdg-desktop-portal-kde` 5.27.11 does (3). On a headless `kwin_wayland --virtual` run from a
userspace prefix, a window session gave one frame of the picked window alone: a window opened over
it and made active left no pixel in the frame. After one choice in the dialog, a second session
given the `restore_token` started with no dialog. The 5.27.11 chooser does not select a lone window
by itself, so the first choice always takes a click. GNOME's backend was not read.

**The next step is the design, in the origin ADR, before any body code.** Three decisions:

- **The target.** On a Wayland session the focus target would be the window the user picked once
  and the restore token keeps, not the topmost window that decision 16 defines. The first capture
  opens the chooser, which a person must answer, so the decision says whether that call waits
  within the brain's capture deadline or fails at once and asks the user to pick, and where the
  body stores the token.
- **The PipeWire client.** The `pipewire` crate binds `libpipewire-0.3` at build time (assumed from
  the crate, not built here), which would add its headers to every `os_linux` build and change the
  Tauri shell's lock file. The alternatives are GStreamer's `pipewiresrc`, which the probe used, or
  a client of PipeWire's native protocol written in the crate. A live test also needs a session
  manager such as WirePlumber running, since without one the stream never reached `streaming`.
- **The frame.** `ScreenCapture::capture` fits as it is, but `CapturedFrame::window` places a
  window inside a display frame, and `covers_display()` would read a frame that is the window alone
  as the whole display, so the receipt and the model would both say display. Body core needs a
  frame kind of its own for it.

## History

- 2026-10-04: Filed when the shell started serving the portal capture under
  [752](752-wayland-screen-capture-through-the-portal.md) with the overlay refusal.
- 2026-10-05: Read the property on two backends. The wlr backend on sway offers monitor sources
  only (1), with cursor modes 3 and interface version 4 under a frontend at 5; the KDE backend
  offers monitor and window (3), with cursor modes 7. On headless KWin a window session, answered
  by injected input, gave a frame without the window covering it, and its restore token skipped
  the dialog the second time. The task stays open for the design above.
