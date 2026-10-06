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

**The build.**

1. **The adapter.** A `WaylandSelection` in `os_linux` implements `SelectionRead` through a pure
   Rust Wayland client. It binds `ext_data_control_manager_v1` where the compositor lists it, else
   `zwlr_data_control_manager_v1` (KWin 5.27 lists version 2 and no `ext` one), takes the device
   for the seat, and keeps the last `selection` offer with the types its `offer` events listed.
   `offered()` returns those types, empty with no selection. `convert(target, limit)` sends
   `receive` with a pipe and reads its far end to the end, `Over` past `limit` and `Silent` after
   `SELECTION_LIMIT`, as `X11Selection` does. A compositor with neither protocol is `Failed`
   with that reason.
2. **The connection.** Connect to `WAYLAND_DISPLAY`, else to `wayland-0`, where GDK connects when
   the variable is unset.
3. **The choice.** `clipboard_picture` takes the calling window and reads through
   `WaylandSelection` when that window's GTK display is a `GdkWaylandDisplay`, else through
   `X11Selection`. `WAYLAND_DISPLAY` alone cannot choose, as it does for the hotkey and capture
   backends, because a shell forced onto `XWayland` with `GDK_BACKEND=x11` reads X and works.
4. **Tests.** The `LinuxClipboardPicture` tests over a fake `SelectionRead` stay. The adapter is
   tested against a fake compositor, as `X11Selection` is against a fake X server, and an
   `integration` test reads a `wl-copy --type image/png` picture on headless KWin and sway with
   the readings' recipe.
5. **Docs.** The `WaylandSelection` entry and the shell's choice in
   [body-os-linux](../../modules/body-os-linux.md), decision 5 of ADR-0070, and a row in
   [wayland-clipboard](../../readings/wayland-clipboard.md) showing the thumbnail from a
   Wayland-client shell on both compositors.

## History

- 2026-10-06: filed when the Linux shell's paste was built, since it reads the X clipboard and
  was checked on `Xvfb` only.
- 2026-10-06: run on headless sway and KWin with `XWayland`: the X-client shell pasted a
  `wl-copy` PNG on both, and the X copy depends on an X window having focus.
- 2026-10-06: the Wayland-client paste reached on headless KWin, with `Ctrl+V` sent through
  `org_kde_kwin_fake_input` after a plain GTK 3 entry pasted text the same way. The page got no
  `File`, so the check became the build above and the task was renamed to it.
