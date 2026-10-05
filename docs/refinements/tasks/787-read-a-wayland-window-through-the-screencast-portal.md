# Read a Wayland window through the ScreenCast portal

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-05

On a Wayland session the shell captures through the portal's `Screenshot`, whose picture is the
whole output with no window list, so `HiddenOverlayCapture` refuses every capture while the overlay
is shown and for 1 s after it hides
([body-os-linux-capture](../../modules/body-os-linux-capture.md)). The overlay is shown for most of
a turn, so a model's `capture_screen` is refused unless the user hid the overlay first. A focus
capture is `NoTarget` there as well.

[ADR-0073](../../adr/ADR-0073-wayland-window-capture.md) is the design: on a backend with a window
source, focus reads the window the user chose once, through a fresh `ScreenCast` session per
capture and a restore token kept in the body's memory; the chooser opens only while the overlay is
hidden; `gst-launch-1.0` reads the frame with the PipeWire descriptor as its standard input; and
`CapturedFrame::window_only` in body core reports it as one window of a display never read. The
frame kind is built and covered, the wire and the brain read its zero source size, and
the shell serves `LinuxWindowCapture` over `DbusScreenCast` and `GstLaunch` behind a
`TargetRouter` when the portal offers a window source, with its chooser opened at the overlay's
next hide. The probes
behind each step are in [wayland-screencast-portal](../../readings/wayland-screencast-portal.md),
whose headless KWin stack the live test reuses.

**What remains.** The live test and the runbook.

1. **The live test.** `cargo test -p os-linux --test screencast_live -- --ignored` on the headless
   KWin stack: a first focus capture refused with the message, a hide that opens the chooser, a
   click, then a frame of that window alone with a covering window over it. The same run answers
   the one open question: whether a chooser opened while a GTK window is hidden lists that window.
2. **The runbook.** The vision runbook names the runtime packages of decision 4 and the model's
   sentence for a window read alone.

## History

- 2026-10-04: Filed when the shell started serving the portal capture under
  [752](752-wayland-screen-capture-through-the-portal.md) with the overlay refusal.
- 2026-10-05: Read the property on two backends. The wlr backend on sway offers monitor sources
  only (1), with cursor modes 3 and interface version 4 under a frontend at 5; the KDE backend
  offers monitor and window (3), with cursor modes 7. On headless KWin a window session, answered
  by injected input, gave a frame without the window covering it, and its restore token skipped
  the dialog the second time.
- 2026-10-05: Made the target, client and frame decisions in ADR-0073 and built the frame kind,
  `CapturedFrame::window_only`, in body core. On headless KWin `gst-launch-1.0` read the window
  with the PipeWire descriptor as its standard input and wrote the PNG to its standard output,
  `persist_mode` 1 returned a token that restored the session, and a token whose window had closed
  left `Start` unanswered. The task stays open for the steps above.
- 2026-10-05: Documented in `proto/body.proto` that a zero source size with
  `CAPTURE_TARGET_FOCUS` is a window read alone, kept that 0 in the brain's gateway, which fell back
  to the image's size, and had `describe` say the window was read on its own with no display size.
  The body's conversion already sent the 0. The task stays open for the steps above.
- 2026-10-05: Built the `ScreenCastPortal` and `FrameReader` ports and `LinuxWindowCapture`, the
  covered core with its restore token, `RESTORE_LIMIT` and `choose`, tested over fakes of both
  ports, and moved the capture backends of `body-os-linux.md` into `body-os-linux-capture.md`. The
  task stays open for the steps above.
- 2026-10-05: Decided what a restored session answering nonzero does. Its token was already
  forgotten and a choice wanted, so the chooser opens at the next hide. Since the spec shows the
  chooser for a token that cannot be restored, 1, cancelled, now fails as `NoTarget` with the
  fixed message, and 2 stays `Backend` naming the code, recorded in ADR-0073 decision 2.
- 2026-10-05: Built `GstLaunch`, the `FrameReader` adapter, which runs `gst-launch-1.0` with the
  pipeline of ADR-0073 decision 4 and kills it at `FRAME_LIMIT` (5 s), tested with a shell script
  in place of the program. The shell reads no new setting: the program is a constant, as `pactl`
  is. The task stays open for the steps above.
- 2026-10-05: Built `DbusScreenCast`, the `ScreenCastPortal` adapter, over the request module,
  tested against a fake portal over a socket pair. On headless KWin, with the chooser answered by injected
  input, `start` returned node and descriptor, `choose` kept a token, and a focus capture through
  `GstLaunch` read the window alone. The task stays open for the steps above.
- 2026-10-05: Built the chooser at the hide and the shell path. `OverlayWatch` implements the new
  `HideSignal` port, and `watch_hides` starts the one thread that calls `choose(CHOOSER_LIMIT)` at a
  hide while a choice is wanted and ends when its `WatchedWindowCapture` is dropped. A kept token
  now clears the wanted flag, which a capture refused during the chooser had set. `TargetRouter`
  sends focus to the window capture and display to the screenshot capture, and the shell serves it
  when `offers_window` is true. `just check-shell` passed on both targets. The task stays open for
  the steps above.
