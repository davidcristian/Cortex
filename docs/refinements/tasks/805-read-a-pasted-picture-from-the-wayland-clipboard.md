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

`WaylandSelection` in `os_linux` is that reader: it implements `SelectionRead` over
`ext_data_control_manager_v1`, else `zwlr_data_control_manager_v1` (KWin 5.27 lists only version
2 of the `wlr` one), and is tested against a fake compositor serving either protocol
([body-os-linux](../../modules/body-os-linux.md)). The shell does not use it yet.

**What remains.**

1. **The connection.** The shell connects to `WAYLAND_DISPLAY`, else to `wayland-0`, where GDK
   connects when the variable is unset, under `XDG_RUNTIME_DIR` unless the name is absolute.
   `wayland_client::Connection::connect_to_env` fails when the variable is unset, so the shell
   opens the socket and passes it to `Connection::from_socket`, once per paste.
2. **The choice.** `clipboard_picture` reads through `WaylandSelection` when the shell's GTK
   display is a `GdkWaylandDisplay`, else through `X11Selection`. GTK objects are read on the
   main thread, so the shell records the display's type at setup and the command reads that
   record. `WAYLAND_DISPLAY` alone cannot choose, as it does for the hotkey and capture backends,
   because a shell forced onto `XWayland` with `GDK_BACKEND=x11` reads X and works.
3. **The live test.** An `integration` test in `os_linux` reads a `wl-copy --type image/png`
   picture through `WaylandSelection` on headless KWin and sway, with the readings' recipe.
4. **Docs.** The shell's choice in [body-os-linux](../../modules/body-os-linux.md), decision 5 of
   ADR-0070, and a row in [wayland-clipboard](../../readings/wayland-clipboard.md) showing the
   thumbnail from a Wayland-client shell on both compositors.

## History

- 2026-10-06: filed when the Linux shell's paste was built, since it reads the X clipboard and
  was checked on `Xvfb` only.
- 2026-10-06: run on headless sway and KWin with `XWayland`: the X-client shell pasted a
  `wl-copy` PNG on both, and the X copy depends on an X window having focus.
- 2026-10-06: the Wayland-client paste reached on headless KWin, with `Ctrl+V` sent through
  `org_kde_kwin_fake_input` after a plain GTK 3 entry pasted text the same way. The page got no
  `File`, so the check became the build above and the task was renamed to it.
- 2026-10-06: built `WaylandSelection` and its fake-compositor tests. The shell's connection and
  choice, the live test and the remaining docs are the steps above.
