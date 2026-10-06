# Check a pasted picture on a Wayland session

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
sway once an X window has had focus in that `XWayland`'s life, KWin only while one is active. GTK
runs the shell as a Wayland client by default on a Wayland session, and then its own window is the
active one, so on KWin the X reader finds no owner and on sway it finds one only if some X window
had focus earlier.

Not known yet: whether WebKitGTK as a Wayland client gives the page a `File` for a pasted picture.
No `Ctrl+V` reached the Wayland-client shell: `wtype` on sway types text but its `Ctrl+V` did not
paste even into a plain GTK 3 entry, and KWin 5.27 has no virtual keyboard for it.

**The check.** Paste into the shell run as a Wayland client, through an input path GTK takes a
paste from: on KWin, a small client of `org_kde_kwin_fake_input`, as
[globalshortcuts-portal](../../readings/globalshortcuts-portal.md) used. If the page gets a
`File`, the composer attaches it with no shell read and only the X client case needs the X reader.
If it gets none, add a Wayland reader behind `ClipboardPicture`: the `ext-data-control` protocol,
or `wlr-data-control` where only that runs, through a pure Rust client, chosen when the window's
GDK backend is Wayland. The choice cannot rest on `WAYLAND_DISPLAY` alone, as the capture and
hotkey backends' does, because a shell forced onto `XWayland` reads X and works.

## History

- 2026-10-06: filed when the Linux shell's paste was built, since it reads the X clipboard and
  was checked on `Xvfb` only.
- 2026-10-06: run on headless sway and KWin with `XWayland`: the X-client shell pasted a
  `wl-copy` PNG on both, and the X copy depends on an X window having focus. The Wayland-client
  paste was not reached, so the check and remedy above were rewritten to that evidence.
