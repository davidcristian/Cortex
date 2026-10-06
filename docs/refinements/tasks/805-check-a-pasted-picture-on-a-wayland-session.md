# Check a pasted picture on a Wayland session

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md) decision 5
**Verified:** 2026-10-06

The shell's `clipboard_picture` command reads the X `CLIPBOARD` selection through
`LinuxClipboardPicture<X11Selection>` ([body-os-linux](../../modules/body-os-linux.md)), and it
was checked only on an X server. On a Wayland session it opens `DISPLAY`, which is `XWayland`
where the compositor runs one, and reads the clipboard only as far as the compositor copies a
Wayland selection to X. With no `DISPLAY` every read fails, and the composer says the clipboard's
picture could not be read.

Not known yet: whether WebKitGTK as a Wayland client also gives the page no `File` for a pasted
picture, and whether sway's and KWin's copy to `XWayland` includes image types. Both stacks run
headless here without sudo ([wayland-screencast-portal](../../readings/wayland-screencast-portal.md)).

**The check.** Run the shell on headless sway and on `kwin_wayland --virtual`, each with
`XWayland`, put a PNG on the Wayland clipboard with `wl-copy --type image/png`, and paste it with
`Ctrl+V`. If no thumbnail shows, add a Wayland reader behind `ClipboardPicture`: the
`ext-data-control` protocol, or `wlr-data-control` where only that runs, through a pure Rust
client, chosen when `WAYLAND_DISPLAY` is set as the capture and hotkey backends choose theirs.

## History

- 2026-10-06: filed when the Linux shell's paste was built, since it reads the X clipboard and
  was checked on `Xvfb` only.
