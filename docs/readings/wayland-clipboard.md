# Readings: a pasted picture on a Wayland session

What the shell's paste gets on a Wayland desktop that runs `XWayland`: when the compositor copies a
picture on the Wayland clipboard to the X `CLIPBOARD` selection that `clipboard_picture` reads, and
what `Ctrl+V` into the composer shows. Cited by
[805](../refinements/tasks/805-check-a-pasted-picture-on-a-wayland-session.md), the task for a
Wayland clipboard reader.

## Method

**2026-10-06.** Two headless stacks from the Ubuntu 24.04 archive, unpacked by `apt-get download`
and `dpkg-deb -x` into userspace prefixes as in
[wayland-screencast-portal](wayland-screencast-portal.md), each with `Xwayland` 23.2.6 and
`wl-clipboard` 2.2.1:

- **sway** 1.9 on wlroots 0.17.1, with `WLR_BACKENDS=headless`, `WLR_RENDERER=pixman`, no input
  device and `xwayland enable`.
- **KWin**: `kwin_wayland --virtual --xwayland` 5.27.11, with `XWAYLAND_NO_GLAMOR=1`. Without
  it, `Xwayland` stopped at start on a segmentation fault.

Each compositor ran in a user and mount namespace with an empty `tmpfs` of mode 1777 on
`/tmp/.X11-unix`: wlroots refuses an X socket directory without the sticky bit, and the one here
has none. Clients reached `Xwayland` through its abstract socket, which `x11rb` and `libxcb` try
first.

The debug shell of [the headless recipe](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless),
built from the commit that added the drop, ran on each stack as an X client (`GDK_BACKEND=x11`) and
as a Wayland client (`GDK_BACKEND=wayland`, the compositor's socket under the default name
`wayland-0`). `DISPLAY` named the compositor's `Xwayland` and `WAYLAND_DISPLAY` was unset, so the
hotkey was an X grab that `xdotool key ctrl+alt+space` pressed through XTEST. The picture was the
14,145-byte PNG of `LIGHTHOUSE`, put on the Wayland clipboard with `wl-copy --type image/png`, and
`xclip -o -t TARGETS` read what the X side offered. `Ctrl+V` went through `wtype` 0.4 on sway and
through XTEST on KWin. No reading here is a timing.

## The answer

| Stack | Shell runs as | X `CLIPBOARD` after `wl-copy` | `Ctrl+V` |
| --- | --- | --- | --- |
| sway | X client | `TIMESTAMP`, `TARGETS`, `image/png` once the shell's window had focus | thumbnail |
| sway | Wayland client | no owner: no X window had had focus | nothing, and no X request |
| KWin | X client | no owner until the shell's window was active, then `image/png` | thumbnail |
| KWin | Wayland client | no owner while no X window was active | not reached |

- **sway copies to X only after an X window has had focus.** Until then wlroots logged
  `not handling selection events: no seat assigned to xwayland` for every selection event: sway
  gives `Xwayland` its seat when an X window first takes focus. `Xwayland` exits 10 s after its
  last client leaves and starts again with no seat.
- **KWin copies to X only while an X window is active.** With no window open, and after the press
  that summons the Wayland-client shell, `xclip` found no owner while `wl-paste --list-types`
  listed `image/png`. No frame confirmed that the Wayland window was shown. With the X-client
  shell active, `TARGETS` listed `image/png` and the paste showed the thumbnail.
- **The Wayland-client shell on sway** was sway's focused `xdg_shell` window. `wtype` typed text
  into the composer and `Ctrl+A` selected it, but `Ctrl+V` pasted nothing, neither text from
  `wl-copy` nor the PNG. With `xclip -verbose -loops 5` owning the X clipboard with the PNG, a
  `Ctrl+V` made no X request, so the page did not ask the shell.
- **The input failed there, not the clipboard.** A plain GTK 3 entry as a Wayland client on the
  same sway read the Wayland clipboard on a timer, `image/png` after the PNG copy and the text
  after a text copy, yet `wtype` with `-M ctrl` and `v` or `-k v`, or with `-P Control_L` added,
  never emitted its `paste-clipboard` signal. Whether WebKitGTK as a Wayland client gives the page
  a `File` for a pasted picture was not reached.
- **KWin 5.27 has no virtual keyboard** for `wtype` ("Compositor does not support the virtual
  keyboard protocol"), and XTEST reaches X clients only, so no key reached the Wayland-client
  shell there. `org_kde_kwin_fake_input`, which [globalshortcuts-portal](globalshortcuts-portal.md)
  pressed keys through, needs a client of its own that this run did not build.
- **Frames.** `grim` read sway's output. KWin's rootless `Xwayland` root window reads black, so
  `ffmpeg -f x11grab -window_id <id>` read the shell's X window by its id.

Method: `measurements/wayland-clipboard-2026-10-06/`, with the compositor and shell scripts, the
sway configuration, the GTK entry probe, the compositor and shell logs and frames in `shots/`.
