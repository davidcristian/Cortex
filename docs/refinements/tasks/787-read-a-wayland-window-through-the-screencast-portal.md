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

[ADR-0073](../../adr/ADR-0073-wayland-window-capture.md) is the design: on a backend with a window
source, focus reads the window the user chose once, through a fresh `ScreenCast` session per
capture and a restore token kept in the body's memory; the chooser opens only while the overlay is
hidden; `gst-launch-1.0` reads the frame with the PipeWire descriptor as its standard input; and
`CapturedFrame::window_only` in body core reports it as one window of a display never read. The
frame kind is built and covered. The probes behind each step are in
[wayland-screencast-portal](../../readings/wayland-screencast-portal.md), whose headless KWin stack
the live test reuses.

**The remaining steps, in order.**

1. **The wire and the brain.** Document on `ImageBlob.source_width` and `source_height` in
   `proto/body.proto` that 0 with `CAPTURE_TARGET_FOCUS` is a window read alone, regenerate the
   stubs (`just proto`), and keep that 0 in `cortex_body_client/gateway.py`, which today falls
   back to the image's size. `describe` in `cortex_core/screen_tool.py` then says one window was
   read on its own, with no display size, for a focus capture whose source is 0. Covered tests in
   both packages.
2. **The ports and the covered core in `os_linux`.** A `ScreenCastPortal` port (the source mask,
   one session's `Start` with an optional token under a limit returning the node, the token and
   the `OpenPipeWireRemote` descriptor, and `Close`) and a `FrameReader` port (descriptor and node
   in, PNG bytes out). `LinuxWindowCapture<P, R>` keeps the token in a `Mutex<Option<String>>`:
   no token is `NoTarget` with the fixed message of ADR-0073 decision 2 and records that a choice
   is wanted; a token runs `Start` under `RESTORE_LIMIT` (2 s), and at the limit sends `Close`,
   forgets the token and answers `NoTarget`; a frame is `decode_png` into
   `CapturedFrame::window_only`. A display request is not its job. Tests over fakes of both ports.
3. **`GstLaunch`**, the `FrameReader` adapter: runs `GST_LAUNCH_PROGRAM` (`gst-launch-1.0` on
   `PATH`) with the pipeline of ADR-0073 decision 4, the descriptor as standard input, standard
   output read whole, `LC_ALL=C`, killed at its limit; a missing program, a nonzero exit or no PNG
   is `Backend`. Tested with `sh` run in place of the program, as `PactlCommand` is.
4. **`DbusScreenCast`**, the portal adapter, through the request module `DbusPortal` and
   `DbusShortcuts` use (the `Response` match before the call, the returned handle checked, one
   limit), with `SelectSources` options as in ADR-0073 decision 1 and `OpenPipeWireRemote` read
   with its descriptor. Tested against a fake portal over a socket pair.
5. **The chooser at the next hide.** `OverlayWatch` signals each recorded hide; when a choice is
   wanted, a thread of the window capture opens a session with no token, waits `CHOOSER_LIMIT`
   (1 min), sends `Close` at the limit, and keeps the token only from a code 0 answer. Covered
   with the fakes and a fake clock or limit.
6. **The router and the shell.** A `ScreenCapture` that sends a focus request to the window capture
   and a display request to the current `HiddenOverlayCapture` over `LinuxPortalCapture`; the
   shell's `body_server.rs` reads `AvailableSourceTypes` once and serves the router when bit 2 is
   set, else what it serves today. Run `just check-shell`.
7. **The live test and the docs.** `cargo test -p os-linux --test screencast_live -- --ignored` on
   the headless KWin stack: a first focus capture refused with the message, a hide that opens the
   chooser, a click, then a frame of that window alone with a covering window over it. The same run
   answers the one open question: whether a chooser opened while a GTK window is hidden lists that
   window. `body-os-linux.md` is at its 250-line limit, so move its capture backends into a
   `body-os-linux-capture.md` first; the vision runbook names the runtime packages of decision 4.

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
