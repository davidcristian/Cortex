# ADR-0073: A Wayland window capture through the ScreenCast portal

**Status:** Accepted (2026-10-05)

## Context

On a Wayland session the shell captures through the portal's `Screenshot`, whose picture is the
whole output and lists no windows, so `HiddenOverlayCapture` refuses every capture while the
overlay is shown and for 1 s after it hides ([ADR-0029](ADR-0029-vision-screen-capture.md)
decision 10). The overlay is shown for most of a turn, so a model's capture is refused unless the
user hid it first, and a focus capture is `NoTarget`.

`org.freedesktop.portal.ScreenCast` with a window source (bit 2 of `AvailableSourceTypes`) streams
one window's own buffer over PipeWire. On headless KWin 5.27.11 a window session gave a frame of
the picked window alone while another window covered it, a second session given the first one's
`restore_token` started with no dialog, and a token whose window had closed opened the chooser
again ([wayland-screencast-portal](../readings/wayland-screencast-portal.md)).
`xdg-desktop-portal-wlr` 0.7.1 offers monitor sources only, and a monitor source is the whole
output with the overlay in it.

Three things had to be decided before any body code: what `focus` means there, which PipeWire
client reads the frame, and how body core describes a frame that is one window with no display
around it.

## Decision

### 1. On Wayland, focus is the window the user chose

When the portal reports a window source, a `CAPTURE_TARGET_FOCUS` request reads the window the
user picked in the portal's chooser, not the topmost window of ADR-0029 decision 16, because a
Wayland client cannot learn which window is on top. Each capture opens its own session
(`CreateSession`; `SelectSources` with `types` 2, `multiple` false, `cursor_mode` 1 and
`persist_mode` 1 plus the kept `restore_token`; `Start`; `OpenPipeWireRemote`), reads one frame,
and closes the session, so the compositor shows that a window is shared only during a capture and
no stream stays open between turns. A `CAPTURE_TARGET_DISPLAY` request is unchanged: the
`Screenshot` portal behind `HiddenOverlayCapture`. Without a window source, as on sway, focus stays
`NoTarget`.

### 2. The chooser opens only while the overlay is hidden

With no token, a focus capture fails at once as `NoTarget` with a fixed body message: no window is
chosen, and the user is asked to choose one when the overlay next hides. The body opens the chooser
at the next hide the shell reports to `OverlayWatch`, waits up to `CHOOSER_LIMIT` (1 min, as
`SHORTCUTS_LIMIT`), then sends `Close`. A cancelled or unanswered chooser keeps nothing, so the
next focus capture asks again.

- **A person does not fit a capture call.** The brain waits `CORTEX_BODY_CAPTURE_TIMEOUT_S` (10 s
  by default) and the portal call the same, and at that limit `Close` ends the dialog.
- **The overlay must not be choosable.** While it is shown the chooser lists it, and a stream of
  the overlay is the picture decision 10 forbids. A hidden GTK window is unmapped, so a chooser
  opened after a hide is assumed not to list it (not run).
- **A token whose window has closed** opens the chooser inside the capture call. A restored
  session's `Start` therefore waits only `RESTORE_LIMIT` (2 s; a restored `Start` answered at once
  in the probe), then sends `Close`, forgets the token and fails as `NoTarget` as above.
- **A restored session that answers nonzero** gave no stream from its token, and it is closed and
  its token forgotten as well, because a kept token would fail every later focus capture the same
  way and the chooser opens only when there is none. The portal shows the chooser when a token
  cannot be restored, so 1, cancelled, means that chooser was closed, and the capture fails as
  `NoTarget` as above. 2, ended in another way, is a portal failure: `Backend` with the code, then
  the same sentence.

### 3. The restore token lives in the body's memory for one run

`persist_mode` 1 keeps the grant while the body runs, and the adapter keeps the token in a field:
never on disk, in an environment variable or in the brain. A restart asks once more.

- The token is state the portal returns, not configuration, so the rule that configuration comes
  from the environment does not apply to it, and the body has no store of its own.
- The brain's stores hold conversation state behind the gRPC boundary. A token there would let the
  brain side hold a grant to read a window.
- On the 1.18 frontend an unsandboxed app has no app id, so a token in a file would let any process
  of the user restore the session without the chooser (assumed from the frontend, not run).
- The hard rule does not apply: no model process holds the token, and nothing in a turn depends
  on it surviving. `persist_mode` 2 with a token file under `XDG_STATE_HOME` is the alternative if
  one choice per run is asked too often.

### 4. GStreamer reads the frame as a child process

The body runs `gst-launch-1.0 -q pipewiresrc fd=0 path=<node> num-buffers=1 always-copy=true !
videoconvert ! video/x-raw,format=RGB ! pngenc ! fdsink` with the `OpenPipeWireRemote` descriptor
as its standard input, reads the PNG from its standard output, and decodes it with the existing
`decode_png`. It sets `LC_ALL=C`, as `PactlCommand` does for `pactl`, and kills the child at the
capture limit. On headless KWin this exact command gave a 400 by 300 frame of the picked window, from a
first and from a restored session.

- **No new native dependency.** No crate is added, neither lock file changes, CI is unchanged, and
  no `unsafe` is needed, since the descriptor reaches the child as a standard stream.
- **The `pipewire` crate** generates its bindings with bindgen at build time, which needs libclang
  and the `libpipewire-0.3` and `libspa-0.2` headers on every machine that builds `os_linux`; this
  one has none of the three. It also links `libpipewire-0.3`, so the shell would not start on a
  Linux machine without it, where a missing `gst-launch-1.0` fails only the capture as `Backend`.
- **A client of PipeWire's native protocol** written in the crate would be a protocol
  implementation, buffers passed by descriptor included, kept up to date by this repo.
- The runtime needs `gst-launch-1.0` with the `pipewiresrc`, `videoconvert` and `pngenc` elements
  (`gstreamer1.0-tools`, `gstreamer1.0-pipewire`, `gstreamer1.0-plugins-good` on Ubuntu) and a
  session manager such as WirePlumber, without which the stream never started.

### 5. Body core has a frame for a window read alone

`CapturedFrame::window_only(frame)` is one window's pixels with no display around them. The whole
frame is encoded; `covers_display()` is false, so the receipt says one window was sent and the
reply says `CAPTURE_TARGET_FOCUS`; and `source_width` and `source_height` are 0, proto3's unset,
because the display was never read. A window placed in a frame of its own size with
`CapturedFrame::window` would cover the frame and be reported as the display, in the receipt and in
the model's sentence. A body before this decision never sends `FOCUS` with a zero source size, so
the brain reads that pair as a window with no known display: the proto comment says so, the
gateway keeps the 0 rather than the image's size, and the model's sentence says the window was read
on its own and that the display's size is unknown.

## Consequences

- The frame kind is pure core and covered in CI. The adapter is a covered core over a portal port
  and a frame-reader port, with its D-Bus side tested against a fake portal over a socket pair and
  a live test on headless KWin, as for `DbusShortcuts`.
- The tool's description is unchanged, since the brain does not know which session the body runs.
  On Wayland `focus` reads the chosen window whether or not it is in front, and the `NoTarget`
  message tells the model why a first capture failed.
- **Accepted risks.** A pick made within `RESTORE_LIMIT` of an unexpected chooser can still name
  the overlay. The 5.27.11 chooser does not select a lone window by itself, so the first choice
  always takes a click. GNOME's backend was not read.

## Alternatives rejected

- **A monitor source**: the whole output, overlay included.
- **The chooser inside the capture call**: a person against a 10 s deadline, with the overlay
  listed. **A control in the overlay to choose a window** needs interface work and changes nothing
  above; it can be added later beside the hide.
- **One session kept open across captures**: the compositor would show sharing for the whole run.
- **The token on disk or in the brain's store**, and **the `pipewire` crate**, for the reasons above.

## Related

- [ADR-0029](ADR-0029-vision-screen-capture.md) (decisions 10 and 16),
  [ADR-0011](ADR-0011-body-v1.md); modules [body-core-capture](../modules/body-core-capture.md),
  [body-os-linux-capture](../modules/body-os-linux-capture.md); readings
  [wayland-screencast-portal](../readings/wayland-screencast-portal.md),
  [wayland-screenshot-portal](../readings/wayland-screenshot-portal.md); task
  [787](../refinements/tasks/787-read-a-wayland-window-through-the-screencast-portal.md).
