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

`kglobalaccel`, the KDE service under that backend, has its own D-Bus interface
(`org.kde.kglobalaccel`), which KDE applications register through. Under KWin 5.27.11 it sent
`globalShortcutPressed` for each press of a shortcut the backend had given it and
`globalShortcutReleased` at each release. A `Hotkey` adapter over that interface, chosen when
`org.kde.kglobalaccel` is on the bus, would bind on 5.27 and skip the settings page. It needs its
own port, fake and check-list run, and the `Hold` rule `LinuxPortalHotkey` follows
([body-os-linux](../../modules/body-os-linux.md)), since it sends one press per auto-repeat too.

To decide first: whether to prefer that adapter on every KDE session or only where the portal
fails. A portal `register` that fails has already opened the page, and the frontend reports
`GlobalShortcuts` version 1 for the 5.27.11 backend; a newer backend's version was not read.

## History

- 2026-10-05: Filed when the portal hotkey was run against the KDE backend under
  [788](788-test-the-portal-hotkey-on-a-kde-wayland-session.md).
