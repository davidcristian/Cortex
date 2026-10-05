# Readings: the GlobalShortcuts portal on KDE

What `xdg-desktop-portal-kde` 5.27.11, this distribution's one backend with
`org.freedesktop.portal.GlobalShortcuts`, does with each call, what a press of a bound chord
sends, and what a direct `kglobalaccel` registration does instead. Cited by
[body-os-linux](../modules/body-os-linux.md) and by
[788](../refinements/tasks/788-test-the-portal-hotkey-on-a-kde-wayland-session.md).

## Method

**2026-10-05.** The KWin stack of [wayland-screencast-portal](wayland-screencast-portal.md),
without PipeWire, under `dbus-run-session`: `kwin_wayland --virtual` 5.27.11 started without
`--no-global-shortcuts`, so KWin runs `kglobalacceld` 5.115 in its own process and owns
`org.kde.kglobalaccel`, then `xdg-desktop-portal-kde` 5.27.11, `xdg-permission-store` and the
`xdg-desktop-portal` 1.18.4 frontend. `XDG_CONFIG_HOME` was emptied before each run, because
`kglobalaccel` writes every component it registers to `kglobalshortcutsrc`, and a component left
there by an earlier run kept the trigger: the next run's shortcut got no key and no press.

A Python `Gio` client called the frontend, and in a second set of runs the backend's
`org.freedesktop.impl.portal.GlobalShortcuts` directly. A minimal Wayland client pressed keys
through `org_kde_kwin_fake_input` version 4, with the evdev codes of left Ctrl, left Alt and
space. An `xdg-open` script placed first in `PATH` wrote down what the backend opened. The
shipped adapter ran once as well: a scratch test called `LinuxPortalHotkey::register` over
`DbusShortcuts` on the same bus.

## Binding through the frontend

| Call | What the backend received | Its answer | In `kglobalaccel` |
| --- | --- | --- | --- |
| `CreateSession`, with or without a `shortcuts` option | the two tokens only | 0, the session handle | nothing |
| `BindShortcuts`, id `ctrl+alt+space`, trigger `CTRL+ALT+space` | the shortcut list | 0 at once, `shortcuts` empty | nothing |
| `ListShortcuts` | the session | 0, `shortcuts` empty | nothing |

- **The backend registers shortcuts only from a `shortcuts` option of `CreateSession`**, which
  the frontend does not forward. For each session it logged "Wrong global shortcuts type, should
  be a(sa{sv})" when that option was missing.
- **`BindShortcuts` opens a settings page** and registers nothing: it ran
  `xdg-open systemsettings://kcm_keys/<session token>`, then answered. On a Plasma desktop that
  address opens System Settings' shortcuts page; that was assumed, not run, since this stack has
  no `systemsettings`.
- **The adapter**: `register` failed with `Registration("the portal answered success without the
  shortcut ctrl+alt+space")` and dropped the callback, so it kept no binding.

So through the frontend no client binds a shortcut on this backend, and each bind opens the page.

## The backend given the shortcuts at `CreateSession`

Called directly with a `shortcuts` option, the backend registered each shortcut with
`kglobalaccel` under a component named after the session token, and answered with the list.

| `preferred_trigger` | `trigger_description` in the answer |
| --- | --- |
| `CTRL+ALT+space` | `Ctrl+Alt+Space` |
| `CTRL+ALT+SPACE` | `Ctrl+Alt+Space` |
| `LOGO+F5` | `Meta+F5` |
| `Ctrl+Alt+Space` | empty |
| `<Control><Alt>space` | empty |

Each answer was code 0. A trigger the backend did not parse also answered 0, with an empty
description.

| Keys pressed, the shortcut bound by session 1 | `Activated` | `Deactivated` |
| --- | --- | --- |
| Ctrl, Alt, space, released at once | 1 | 1 |
| Ctrl, Alt, space, held 1.5 s | 24 | 1 |
| Ctrl, space | 0 | 0 |
| Ctrl, Alt, space once session 2 asked for `CTRL+ALT+space` too | 1, to session 1 | 1 |

- **A held chord sends one `Activated` per auto-repeat.** `kglobalaccel` sent its own
  `globalShortcutPressed` 26 times and `globalShortcutReleased` 3 times over the run, the same
  counts. The repeat delay and rate were KWin's defaults, from an empty configuration.
- **A taken trigger is not reported.** Session 2's shortcut was answered with code 0 and
  `trigger_description` `Ctrl+Alt+Space`, the same as session 1's, while `kglobalaccel`'s
  `allShortcutInfos` listed it with no key and `Ctrl+Alt+Space` only as its default. Every press
  went to session 1.
- **No call opened a dialog or waited for one.** Every answer came at once, so a bind on this
  backend runs unattended; the settings page that `BindShortcuts` opens is not waited for.

## Registering with `kglobalaccel` directly

**2026-10-05**, on the same stack. A Python `Gio` client, with no portal call, registered one
action with `org.kde.kglobalaccel` at `/kglobalaccel` (interface `org.kde.KGlobalAccel`), the
interface KDE applications register through, and pressed keys as above.

| Call | Arguments | Answer |
| --- | --- | --- |
| `doRegister` | `["cortex", "toggle", "Cortex", "Show or hide the overlay"]` | none |
| `setShortcut`, flag 1 (`IsDefault`) | that action id, `[201326624]` | `[201326624]` |
| `setShortcut`, flag 2 (`SetPresent`) | the same | `[201326624]` |
| `getComponent` | `"cortex"` | `/component/cortex` |

201326624 is `0x0C000020`, Qt's key code for Space (`0x20`) with its Ctrl (`0x04000000`) and
Alt (`0x08000000`) modifier bits. `allMainComponents` then listed `cortex` beside KWin's own.

| Keys pressed | `globalShortcutPressed` | `globalShortcutReleased` |
| --- | --- | --- |
| Ctrl, Alt, space, released at once | 1 | 1 |
| Ctrl, Alt, space, held 1.5 s | 24 | 1 |
| Ctrl, space | 0 | 0 |

- **This binds the chord on 5.27 with no portal and no settings page.** Each signal came on
  `/component/cortex`, interface `org.kde.kglobalaccel.Component`, naming `cortex` and `toggle`,
  from `:1.0`, the owner of `org.kde.kglobalaccel`.
- **A held chord sends one `globalShortcutPressed` per auto-repeat**, the same count as the
  portal's `Activated` above, so the `Hold` rule applies here too.

## The `LinuxKdeHotkey` adapter

**2026-10-05**, on the same stack with an empty `XDG_CONFIG_HOME`. The ignored test
`os_linux/tests/accel_live.rs` built `LinuxKdeHotkey` over `DbusGlobalAccel` on the session bus
and registered `ctrl+alt+space`, while a script pressed keys as above and read the component with
`allActionsForComponent(["cortex"])`. Introspection listed `unregister(s componentUnique, s
shortcutUnique)` on `org.kde.KGlobalAccel`.

| Case | `register` | Callback runs | `cortex` actions after |
| --- | --- | --- | --- |
| Tap, hold 1.5 s, tap, then the backend dropped | `Ok` | 3, none in the next 2 s | none |
| `other` registered first with the same key (flags 6) | `Registration`, key given to another action | 0 | none |
| A run killed after registering, then a new run: tap, hold, tap | `Ok` | 3 | none |

- **`setShortcut` with flags 6 binds the chord given**, on an empty configuration and over an
  action a killed run left with that key, and answers `[0]`, which the adapter refuses, when
  another component holds it.
- **The drop removes the action.** While registered, the component listed
  `["cortex", "ctrl+alt+space", "Cortex", "Cortex live test"]`; after the drop, or after a refused
  register, it listed nothing. The killed run left that action listed until the next run.
- Only `ctrl+alt+space` was run; the Qt codes of the other keys `qt_code` names are Qt's values,
  unchecked here.

## Who sends each signal

A fourth client created a session through the frontend with session token `cortex1`, bound
`ctrl+alt+space` (answered with an empty list, as above), then registered that id with
`kglobalaccel` directly under the component `cortex1`, and pressed the chord once.

| Signal | Sender | Owner of |
| --- | --- | --- |
| `globalShortcutPressed`, `/component/cortex1` | `:1.0` | `org.kde.kglobalaccel` |
| backend `Activated`, the frontend's session handle | `:1.4` | `org.freedesktop.impl.portal.desktop.kde` |
| `org.freedesktop.portal.GlobalShortcuts.Activated`, the same handle | `:1.8` | `org.freedesktop.portal.Desktop` |

`Deactivated` followed the same path at the release, and each `Response` came from `:1.8` too.

- **The frontend sends `Activated` from the connection that owns `org.freedesktop.portal.Desktop`**,
  so a client that reads only that owner's signals reads every press.
- **The backend listens on the component named after the session token** whether or not
  `BindShortcuts` registered anything, so an action any client registers there makes the
  backend send `Activated` for that session.

Method: a scratch directory outside the repo held one shell script that starts the stack on a
private session bus, the fake input client, and the four Python `Gio` clients.
