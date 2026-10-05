# Pixel-level screening in the body

**Status:** open, waiting for a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-05
**Trigger:** A capture that has to go ahead with part of the screen removed rather than be refused,
over a window or a region Cortex does not own, since the body's own windows are the OS's to exclude
on Windows, the X11 capture's own fill on X11, and a refusal while the overlay is shown on Wayland.

The body is the only side holding the pixels before they cross the wire, so it is the only side
that could redact a region (a password field, a specific window) rather than refuse a whole
capture. Nothing in the design prevents it: the policy already lives in pure core, where a
screening pass would join it. On Windows one window is already excluded, by the OS rather than by
Cortex: the overlay sets `WDA_EXCLUDEFROMCAPTURE` on itself at setup, and the shell wires the
refusing backend if that call fails. X11 has no such call, so the X11 capture paints every window
of the body's process black, the body's first pixel pass, in `os_linux/src/exclude.rs`
([753](753-keep-the-overlay-out-of-a-linux-capture.md)). A Wayland capture goes through the
screenshot portal, whose picture says where no window is, so nothing can be painted out of it:
`HiddenOverlayCapture` in `os_linux/src/overlay.rs` refuses the capture while the overlay is shown
or has just been hidden. All three cover windows Cortex owns, which is why the trigger names one it
does not. A pass for those would sit beside the X11 fill, and on Wayland it would first need a
source for where another program's window is, which the portal does not give.

## History

- 2026-07-18: Recorded when the vision slice was finished.
- 2026-07-19: Recorded as one of three vision surfaces nothing reads, beside the content-addressed
  `AttachmentStore` and multi-monitor and DPI reporting.
- 2026-09-13: Checked against the code, and the trigger written for the first time. The body still
  holds the pixels alone, and the capture policy is still pure core, in `body_core`'s
  `screen_policy`, `screen_target` and `screen_image`. The overlay's own
  `WDA_EXCLUDEFROMCAPTURE` exclusion is the partial answer that already exists, and it covers
  windows Cortex owns and nothing else. `screen_policy.rs` is 289 lines against the 300-line cap,
  so a screening pass arrives as its own module.
- 2026-09-19: Checked again and unchanged. No commit since touched the capture path in `body/`, and
  nothing in the body crates or the shell masks, blurs or redacts pixels. The overlay's exclusion
  is still requested in the shell's `setup`, through `body_server::exclude_overlay`, which serves
  the refusing backend when `SetWindowDisplayAffinity` fails, and `screen_policy.rs` is still 289
  lines. The trigger has not occurred.
- 2026-09-30: Corrected, because the entry assumed Windows only. Since 2026-09-28 `os_linux` has
  an X11 backend that reads the primary monitor, and the shell's Linux `start` still serves
  `DeniedScreenCapture`, since `exclude_overlay` returns `false` off Windows (`body_server.rs` line
  130). Nothing masks pixels yet: the masks in `os_linux` are colour channel masks. `screen_policy.rs`
  is 213 lines. The trigger has not fired: nothing asks for a capture with another program's window
  or a region removed.
- 2026-10-01: Checked again. The X11 capture now fills the body's own windows black, which the
  entry described as future work, and the shell serves it on an X11 session. That fill finds
  windows by `_NET_WM_PID`, so it still covers only windows Cortex owns. The trigger has not
  fired.
- 2026-10-05: Not fired, and the entry corrected for Wayland. Since 2026-10-04 the shell serves a
  Wayland capture through the screenshot portal inside `HiddenOverlayCapture`, which refuses while
  the overlay is shown or within `OVERLAY_SETTLE` (1 s) of a hide, because a portal picture cannot
  leave a window out. The entry named only Windows and X11. Nothing in the body crates or the shell
  masks or redacts pixels of a window Cortex does not own.
