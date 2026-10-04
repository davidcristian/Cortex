# Wire the portal hotkey into the Wayland shell

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-04

`os_linux` has a `GlobalShortcuts` portal backend, `LinuxPortalHotkey` over `DbusShortcuts`
([body-os-linux](../../modules/body-os-linux.md)), but the shell's Linux `hotkey::register` still
logs and registers nothing when `WAYLAND_DISPLAY` is set and not empty. Wiring it means three
things. First, the registration runs on its own thread: a bind can wait up to `SHORTCUTS_LIMIT`
(1 min) on a compositor dialog, and the shared request module bounds only the `Response`, not the
method reply, so a frontend that never replies would hold the caller with no limit. Second, the
shell opens the session bus as the capture path does and passes a description for the shortcut,
which the compositor shows the user. Third, the overlay runbook says that the trigger the user sees
can differ from `CORTEX_HOTKEY`, because the compositor may change it.

A live test needs a KDE Wayland session (`kwin_wayland` with `kglobalaccel` and
`xdg-desktop-portal-kde`), the only backend on this distribution that implements the interface.
That test would also answer the three points the module doc lists as read from the specification:
the trigger form, one `Activated` per hold or per repeat, and what a backend answers when the
preferred trigger is taken.

## History

- 2026-10-04: Filed when the portal backend was built under
  [765](765-a-wayland-hotkey-through-the-globalshortcuts-portal.md).
