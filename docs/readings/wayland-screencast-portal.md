# Readings: the ScreenCast portal's window source

Which of this distribution's `org.freedesktop.portal.ScreenCast` backends offer a window source,
and how far a window session gets on a headless desktop. Cited by
[787](../refinements/tasks/787-read-a-wayland-window-through-the-screencast-portal.md), the task
for a Wayland capture while the overlay is open.

## Method

**2026-10-05.** Two stacks from the Ubuntu 24.04 archive, unpacked by `apt-get download` and
`dpkg-deb -x` into userspace prefixes and run without sudo under `dbus-run-session`, each with
`pipewire` 1.0.5, `xdg-permission-store` and the `xdg-desktop-portal` 1.18.4 frontend:

- **sway**: the stack of [wayland-screenshot-portal](wayland-screenshot-portal.md), with
  `xdg-desktop-portal-wlr` 0.7.1 on `sway` 1.9.
- **KWin**: `kwin_wayland` 5.27.11 with `--virtual`, rendering through Mesa's llvmpipe, then
  `xdg-desktop-portal-kde` 5.27.11 with `qtwayland5` and the QML modules its window chooser
  imports, from `plasma-workspace` 5.27.12, `plasma-framework` and `qml-module-org-kde-pipewire`.
  `XDG_CURRENT_DESKTOP` was `KDE` and the portal file directory held `kde.portal`.

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
| the same, with the chooser modules | 0 | 0 | no `Response` in 12 s |

- **From the prefix** the backend logged `zkde_screencast_unstable_v1 does not seem to be
  available`. KWin offers that protocol only to a client whose executable a desktop file names
  with the interface in `X-KDE-Wayland-Interfaces`. The backend's file names
  `/usr/lib/x86_64-linux-gnu/libexec/xdg-desktop-portal-kde`, not the prefix path, and the
  variable on `kwin_wayland` turns the check off. An installed backend at that path is assumed to
  need no variable; that was not run.
- **Without** `org.kde.taskmanager` and `org.kde.plasma.workspace.dialogs`, the backend logged
  "Failed to load dialog, cannot exec" and answered 1, cancelled.
- **With them** the chooser loaded and `Start` waited for a choice nobody made. The session had no
  other window, so no window frame was read.

Method: a scratch directory outside the repo held both prefixes, one shell script per stack that
starts it on a private session bus, and the Python client.
