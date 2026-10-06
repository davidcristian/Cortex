# Readings: a pasted picture on a Wayland session

What the shell's paste gets on a Wayland desktop that runs `XWayland`: when the compositor copies a
picture on the Wayland clipboard to the X `CLIPBOARD` selection that `clipboard_picture` reads,
what `Ctrl+V` into the composer shows, and what a WebKitGTK page gets from a paste as a Wayland
client. Cited by
[805](../refinements/tasks/805-read-a-pasted-picture-from-the-wayland-clipboard.md), the task for a
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
| KWin | Wayland client | no owner while no X window was active | no file in the page, see below |

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
  never emitted its `paste-clipboard` signal. The KWin run below reached the page.
- **KWin 5.27 has no virtual keyboard** for `wtype` ("Compositor does not support the virtual
  keyboard protocol"), and XTEST reaches X clients only, so no key reached the Wayland-client
  shell there. The run below pressed keys through `org_kde_kwin_fake_input` instead, as
  [globalshortcuts-portal](globalshortcuts-portal.md) did.
- **Frames.** `grim` read sway's output. KWin's rootless `Xwayland` root window reads black, so
  `ffmpeg -f x11grab -window_id <id>` read the shell's X window by its id.

Method: `measurements/wayland-clipboard-2026-10-06/`, with the compositor and shell scripts, the
sway configuration, the GTK entry probe, the compositor and shell logs and frames in `shots/`.

## The Wayland-client paste on KWin

**2026-10-06**, a second run on the KWin stack above, with `KWIN_WAYLAND_NO_PERMISSION_CHECKS=1`
and the socket named `wayland-0`. A Python client of about 70 lines that writes the Wayland wire
format itself bound `org_kde_kwin_fake_input` version 4 and sent `keyboard_key` with the evdev
codes of left Ctrl (29) and V (47). Started outside the compositor's user and mount namespace,
that client was offered none of the restricted globals (`org_kde_kwin_fake_input`,
`org_kde_plasma_window_management`) even with the variable set; started through
`nsenter -U -m -t <kwin pid> --preserve-credentials`, it was offered both. A KWin script loaded
through `org.kde.kwin.Scripting` listed the windows with their active state and frame.

Each client ran as a Wayland client (`GDK_BACKEND=wayland`) on the libraries of the shell's
prefix, WebKitGTK 2.52.6. The probe page was a `textarea` whose `paste` handler posted the event's
`files`, `types`, `items` and text to a script message handler. The shell was the debug build of
the tree this record was committed with, summoned through its X grab with `xdotool` on
`XWayland`. `xdotool search --name Cortex` on `XWayland` found no window, and KWin listed the
shell's window as the active one.

| Client | Clipboard before `Ctrl+V` | What the press gave |
| --- | --- | --- |
| GTK 3 `Gtk.Entry` | text from `wl-copy` | `paste-clipboard`, the entry holds the text |
| WebKitGTK probe page | text from `wl-copy` | `types` `text/plain`, one `string` item, no file |
| WebKitGTK probe page | `wl-copy --type image/png` | `files`, `types` and `items` all empty |
| the shell | that PNG, and the same PNG owned on X by `xclip` | `xclip` served one `image/png` request |
| the shell | that PNG from `wl-copy` only | X `CLIPBOARD` without an owner before and after |

- **The input path works for GTK as a Wayland client** on KWin: the entry took the paste that
  `wtype` could not give it on sway.
- **WebKitGTK as a Wayland client gives the page no `File` for a pasted picture**, and no type
  either. That is the paste the composer hands to `clipboard_picture`, and the `xclip` request at
  the press shows the call.
- **With only the Wayland copy, that read finds no owner**, since KWin copies to X only while an
  X window is active and here the shell's own Wayland window was. A Wayland-client shell on KWin
  therefore attaches nothing from a picture a Wayland client copied.
- **KWin 5.27.11 lists `zwlr_data_control_manager_v1` version 2** to an ordinary client, and no
  `ext_data_control_manager_v1`.
- **No frame was taken**: KWin's rootless `Xwayland` root reads black and this run had no capture
  of a Wayland window, so the composer's thumbnail in the `xclip` row was not seen.

Method: `measurements/wayland-clipboard-2026-10-06/wayland-client/`, with the compositor, client,
key and window-list scripts and each client's log.

## The Wayland read

**2026-10-06**, on both stacks above with no X client: `cargo test -p os-linux --test wayland_live
-- --ignored` with `WAYLAND_DISPLAY` naming the compositor's socket. `wl-copy --foreground --type
image/png` served 300,000 bytes, and `WAYLAND_DEBUG=1` logged the read's requests.

| Stack | Manager bound | Read |
| --- | --- | --- |
| sway | `zwlr_data_control_manager_v1`, listed at version 2, bound at 1 | `image/png` listed, all bytes |
| KWin | `zwlr_data_control_manager_v1`, listed at version 2, bound at 1 | `image/png` listed, all bytes |

- **Neither lists `ext_data_control_manager_v1`**, so both reads used the `wlr` protocol.
- **`wl-copy` answers every type with its data**, as `xclip` does: a read that asked for
  `text/plain` still received the picture, so the live test checks the listed types instead.

**The shell on KWin.** The debug shell built from the commit that wired this read ran on the KWin
stack as a Wayland client with `WAYLAND_DISPLAY` unset and `WAYLAND_DEBUG=1`, summoned through its
X grab. The 14,145-byte PNG of `LIGHTHOUSE` went on the clipboard with `wl-copy --type image/png`,
and `Ctrl+V` went through `org_kde_kwin_fake_input` as above. At the press the shell connected to
`wayland-0`, bound `zwlr_data_control_manager_v1` at version 1, was offered `image/png` and sent
`receive` for it, and logged no error. No frame was taken, so the thumbnail was not seen, and no
shell ran on sway.
