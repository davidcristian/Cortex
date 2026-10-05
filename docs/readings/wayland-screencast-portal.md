# Readings: the ScreenCast portal's window source

Which of this distribution's `org.freedesktop.portal.ScreenCast` backends offer a window source,
and what a window session gives on a headless desktop. Cited by
[787](../refinements/tasks/787-read-a-wayland-window-through-the-screencast-portal.md), the task
for a Wayland capture while the overlay is open, and by
[ADR-0073](../adr/ADR-0073-wayland-window-capture.md).

## Method

**2026-10-05.** Two stacks from the Ubuntu 24.04 archive, unpacked by `apt-get download` and
`dpkg-deb -x` into userspace prefixes and run without sudo under `dbus-run-session`, each with
`pipewire` 1.0.5, `xdg-permission-store` and the `xdg-desktop-portal` 1.18.4 frontend:

- **sway**: the stack of [wayland-screenshot-portal](wayland-screenshot-portal.md), with
  `xdg-desktop-portal-wlr` 0.7.1 on `sway` 1.9.
- **KWin**: `kwin_wayland` 5.27.11 with `--virtual`, rendering through Mesa's llvmpipe, then
  `xdg-desktop-portal-kde` 5.27.11 with `qtwayland5` and the QML modules its window chooser
  imports, from `plasma-workspace` 5.27.12, `plasma-framework` and `qml-module-org-kde-pipewire`.
  `XDG_CURRENT_DESKTOP` was `KDE` and the portal file directory held `kde.portal`. For the frame,
  also `wireplumber` 0.4.17, `qmlscene` 5.15.13, and GStreamer 1.24.2 with `gstreamer1.0-pipewire`
  1.0.5.

`gdbus call` read `org.freedesktop.DBus.Properties.GetAll` on the frontend's
`org.freedesktop.portal.ScreenCast` and on the backend's `org.freedesktop.impl.portal.ScreenCast`.
A Python `Gio` client then called `CreateSession`, `SelectSources` with `types` 2 (window),
`multiple` false, `cursor_mode` 1 and `persist_mode` 2, and `Start` with no parent window, waiting
12 s for each `Response` and sending `Close` to a request that got none.

## The properties

| Backend | `AvailableSourceTypes` | `AvailableCursorModes` | backend `version` | frontend `version` |
| --- | --- | --- | --- | --- |
| `xdg-desktop-portal-wlr` 0.7.1, sway 1.9 | 1: monitor | 3: hidden, embedded | 4 | 5 |
| `xdg-desktop-portal-kde` 5.27.11, KWin 5.27.11 | 3: monitor, window | 7: hidden, embedded, metadata | 4 | 5 |

The source bits are 1 monitor, 2 window and 4 virtual; the cursor bits are 1 hidden, 2 embedded
and 4 metadata. The frontend reported each backend's two masks unchanged.

- **The wlr backend** binds only `wl_shm`, `wl_output`, `zxdg_output_manager_v1` and
  `zwlr_screencopy_manager_v1` of the globals sway lists, and its binary has no string naming a
  toplevel. sway 1.9 lists `zwlr_foreign_toplevel_manager_v1`, which lists windows, but no protocol
  that copies one window's buffer; `zwlr_screencopy_manager_v1` copies an output.
- **The KDE backend without a compositor**, run with `QT_QPA_PLATFORM=offscreen` and no Wayland
  display, still exported `ScreenCast` and reported 3 and 7. Its masks do not show whether the
  compositor can stream a window.
- **The KDE backend's `GlobalShortcuts`** reported `version` 1, read the same way under KWin.

## A window session on headless KWin

| Condition | `CreateSession` | `SelectSources` | `Start` |
| --- | --- | --- | --- |
| backend run from the prefix | 2 | `AccessDenied`, invalid session | not called |
| `KWIN_WAYLAND_NO_PERMISSION_CHECKS=1`, chooser modules missing | 0 | 0 | 1 at once |
| the same, with the chooser modules, nobody choosing | 0 | 0 | no `Response` in 12 s |
| the same, a click on the window's card, then Enter | 0 | 0 | 0, one stream, `source_type` 2 |
| a second session given the first one's `restore_token`, no input | 0 | 0 | 0 at once, no dialog |

- **From the prefix** the backend logged `zkde_screencast_unstable_v1 does not seem to be
  available`. KWin offers that protocol only to a client whose executable a desktop file names
  with the interface in `X-KDE-Wayland-Interfaces`. The backend's file names
  `/usr/lib/x86_64-linux-gnu/libexec/xdg-desktop-portal-kde`, not the prefix path, and the
  variable on `kwin_wayland` turns the check off. An installed backend at that path is assumed to
  need no variable; that was not run.
- **Without** `org.kde.taskmanager` and `org.kde.plasma.workspace.dialogs`, the backend logged
  "Failed to load dialog, cannot exec" and answered 1, cancelled.
- **The chooser** listed the one other window, a 400 by 300 `qmlscene` window filled with
  `#cc3333`, and did not select it: the dialog's code to select a lone window raised `TypeError:
  Cannot call method 'index' of null` at line 141 of `ScreenChooserDialog.qml`. A script loaded
  through KWin's `org.kde.kwin.Scripting` read the dialog's place, and a minimal Wayland client
  sent the click and the key through `org_kde_kwin_fake_input` version 4. Escape alone answered 1.
- **The answer** held one stream, a PipeWire node id with `source_type` 2, and a `restore_token`.
  The second session's `Start` returned the same token and a new node id.
- **The frame.** After the choice a second `qmlscene` window, 200 by 150 in `#3333cc`, was opened,
  moved by a KWin script over the middle of the first and made the active window. GStreamer's
  `pipewiresrc` then read one buffer from the first stream's node through the descriptor
  `OpenPipeWireRemote` returned. It was 400 by 300, the window's content without its title bar;
  every pixel was 204, 51, 51 except the 256 of a green 16 by 16 square turning in its corner, and
  none had the covering window's colour.
- **A session manager is needed.** With only the PipeWire daemon, `pipewiresrc` stayed in the
  `paused` state and read nothing; with `wireplumber` 0.4.17 also running, the stream reached
  `streaming` and gave the buffer.

## The frame through a child's standard streams

**2026-10-05**, the same KWin stack and windows, for
[ADR-0073](../adr/ADR-0073-wayland-window-capture.md). `persist_mode` was 1, and `gst-launch-1.0
-q pipewiresrc fd=0 path=<node> num-buffers=1 always-copy=true ! videoconvert !
video/x-raw,format=RGB ! pngenc ! fdsink` ran with the `OpenPipeWireRemote` descriptor as its
standard input and its standard output read into memory.

| Session | `Start` | The child | Its standard output |
| --- | --- | --- | --- |
| first, a click on the window's card, then Enter | 0, a `restore_token` | exit 0 | a 400 by 300 PNG |
| second, given that token, no input | 0 at once, the same token | exit 0 | a 400 by 300 PNG |
| third, given that token after the picked window closed | no `Response` in 14 s | not run | none |

- **Both frames** were the picked window alone: every pixel 204, 51, 51 except the green square
  (256 and 260 pixels), and none in the covering window's colour.
- **`persist_mode` 1** returned a token, as 2 did, and it skipped the dialog within the run.
- **A token whose window has closed** did not fail the `Start`: it waited, as a session with no
  token does while the chooser is open.

Method: a scratch directory outside the repo held the prefixes, one shell script per stack that
starts it on a private session bus, the KWin scripts, the fake input client and the Python `Gio`
client, which ran the two sessions and the `gst-launch-1.0` read.

## The body's adapters on headless KWin

**2026-10-05**, the same KWin stack and red window, with no covering window. A scratch binary built
against `os_linux` ran `DbusScreenCast` alone and then `LinuxWindowCapture` over `DbusScreenCast`
and `GstLaunch`, on the private session bus. The fake input client clicked the window's card and
pressed Enter 2.5 s after each chooser opened.

| Step | Result |
| --- | --- |
| `source_types` | 3, so `offers_window` is true |
| `start` with no token, then a click | `Started::Stream`: node 45, a `restore_token`, a descriptor that is a Unix socket |
| a focus capture before any choice | `NoTarget` with `NO_WINDOW`, and `choice_wanted` true |
| `choose`, then a click | true, a token kept |
| a focus capture | a 400 by 300 frame of the window alone, its centre pixel 204, 51, 51 |

- **The frontend accepted the adapter's handles**: the session was
  `/org/freedesktop/portal/desktop/session/1_20/cortexcast1`, and each `Response` came from the
  unique name owning `org.freedesktop.portal.Desktop`, the only sender the adapter reads.
- **The restored session started with no dialog** and no input, within `RESTORE_LIMIT`.
