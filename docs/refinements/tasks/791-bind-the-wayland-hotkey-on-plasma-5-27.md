# Bind the Wayland hotkey on Plasma 5.27

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-05

On a Plasma 5.27 Wayland session, the KDE that Ubuntu 24.04 ships, the shell has no hotkey.
`xdg-desktop-portal-kde` 5.27.11 registers shortcuts only from a `CreateSession` option the
frontend does not forward, and its `BindShortcuts` answers success with no shortcut, so
`LinuxPortalHotkey::register` fails and the shell logs "could not register"
([globalshortcuts-portal](../../readings/globalshortcuts-portal.md)). Before it answers, that
`BindShortcuts` runs `xdg-open systemsettings://kcm_keys/cortex1`, which on a Plasma desktop is
assumed to open System Settings' shortcuts page at every shell start; that was not run.

So nothing the shell sends through the portal binds a chord there. Registering with
`kglobalaccel` directly does. On KWin 5.27.11,
`doRegister` and `setShortcut` on `org.kde.kglobalaccel` bound Ctrl+Alt+Space with no settings
page, and each press sent `globalShortcutPressed` on `/component/<component>`, one per
auto-repeat, then one `globalShortcutReleased`
([globalshortcuts-portal](../../readings/globalshortcuts-portal.md)).

The build is a `Hotkey` adapter over that interface with its own small D-Bus port and fake, the
hotkey check list, and the `Hold` rule `LinuxPortalHotkey` follows
([body-os-linux](../../modules/body-os-linux.md)). Its parts:

- The chord as a Qt key code: the key's code with Qt's modifier bits, as `0x0C000020` for
  Ctrl+Alt+Space. Only that chord was run; each other key's Qt code is to be checked on the stack.
- One fixed component name and action id, so a restart registers the same action again.
- Signals read only from the unique name that owns `org.kde.kglobalaccel`, and a malformed one
  skipped, as `DbusShortcuts` does for the portal.
- The shell choosing it whenever `org.kde.kglobalaccel` has an owner, before any portal call,
  since a portal `register` that fails has already opened the settings page, and the choice then
  needs no fact about newer backends, whose `GlobalShortcuts` version was not read.

The backend also runs a portal session's shortcut when a client registers its id with
`kglobalaccel` under the component named after the session token, so a portal session plus that
registration, with no `BindShortcuts`, binds as well. It is not the plan: it depends on how this
backend names its component, which no portal document states.

## History

- 2026-10-05: Filed when the portal hotkey was run against the KDE backend under
  [788](788-test-the-portal-hotkey-on-a-kde-wayland-session.md).
