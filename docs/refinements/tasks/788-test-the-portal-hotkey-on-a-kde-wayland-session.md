# Test the portal hotkey on a KDE Wayland session

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-04

The shell registers the hotkey on a Wayland session through `LinuxPortalHotkey` over
`DbusShortcuts` ([body-os-linux](../../modules/body-os-linux.md)), and both are tested only
against a fake portal over a socket pair. No live test exists, because of this distribution's
portal backends only `xdg-desktop-portal-kde` implements `GlobalShortcuts`. A live test needs a KDE
Wayland session (`kwin_wayland` with `kglobalaccel` and `xdg-desktop-portal-kde`), headless if it
can be, and an `#[ignore]`d test beside `portal_live` that binds a chord and presses it.

That test would answer the three points the module doc lists as read from the specification and
not tested: the trigger form, one `Activated` per hold or per repeat, and what a backend answers
when the preferred trigger is taken. It would also show whether a first bind opens a dialog that
a headless session cannot answer, which decides whether the test can run unattended.

## History

- 2026-10-04: Filed when the portal backend and its shell wiring were built under
  [765](765-a-wayland-hotkey-through-the-globalshortcuts-portal.md).
