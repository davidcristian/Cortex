# Read a pasted picture from the Wayland clipboard

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md) decision 5
**Verified:** 2026-10-06

The shell's `clipboard_picture` command reads the X `CLIPBOARD` selection through
`LinuxClipboardPicture<X11Selection>` ([body-os-linux](../../modules/body-os-linux.md)). On a
Wayland session it opens `DISPLAY`, which is `XWayland` where the compositor runs one, and sees a
picture copied by a Wayland client only when the compositor copies it to X. On headless sway and
KWin ([wayland-clipboard](../../readings/wayland-clipboard.md)) the shell run as an X client
(`GDK_BACKEND=x11`) showed the thumbnail on both. Both compositors copy only around an X window:
sway once an X window has had focus in that `XWayland`'s life, KWin only while one is active.

GTK runs the shell as a Wayland client by default on a Wayland session, and WebKitGTK 2.52.6 as a
Wayland client gives the page no `File` for a pasted picture: the paste event's `files`, `types`
and `items` are all empty, as on X. The composer then calls `clipboard_picture`, and on KWin, where
the shell's own Wayland window is the active one, the X `CLIPBOARD` has no owner after a
`wl-copy`, so the paste attaches nothing. The shell needs a Wayland reader for this case.

`WaylandSelection` in `os_linux` is that reader, over `ext_data_control_manager_v1`, else
`zwlr_data_control_manager_v1`. It is tested against a fake compositor serving either protocol,
and its live test read a `wl-copy` picture whole on headless sway and KWin
([wayland-clipboard](../../readings/wayland-clipboard.md#the-wayland-read)). The shell reads
through it when the overlay's GTK display is a `GdkWaylandDisplay`, connecting where GDK does
([body-os-linux](../../modules/body-os-linux.md)).

**What remains.** See the thumbnail. On headless KWin the Wayland-client shell sent the read at
`Ctrl+V` ([wayland-clipboard](../../readings/wayland-clipboard.md#the-wayland-read)), but no frame
of a Wayland window was taken there: KWin's `Xwayland` root reads black, and its screenshot
interface was not tried. On sway, `grim` reads the output, but `wtype` reached no Wayland-client
paste, so the press needs another route. A row in the readings with the thumbnail on both closes
this task.

## History

- 2026-10-06: filed when the Linux shell's paste was built, since it reads the X clipboard and
  was checked on `Xvfb` only.
- 2026-10-06: run on headless sway and KWin with `XWayland`: the X-client shell pasted a
  `wl-copy` PNG on both, and the X copy depends on an X window having focus.
- 2026-10-06: the Wayland-client paste reached on headless KWin, with `Ctrl+V` sent through
  `org_kde_kwin_fake_input` after a plain GTK 3 entry pasted text the same way. The page got no
  `File`, so the check became the build above and the task was renamed to it.
- 2026-10-06: built `WaylandSelection` with its fake-compositor and live tests, and the shell's
  choice of reader. The Wayland-client shell on KWin read the clipboard at `Ctrl+V`; the
  thumbnail remains unseen.
