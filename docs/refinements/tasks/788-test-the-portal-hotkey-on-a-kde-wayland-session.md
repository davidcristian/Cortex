# Test the portal hotkey on a KDE Wayland session

**Status:** open, waiting for its trigger
**Area:** cross-cutting
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** a `GlobalShortcuts` backend that registers what `BindShortcuts` names can be installed here. None can yet: the Ubuntu 24.04 archive has one backend with the interface, `xdg-desktop-portal-kde` 5.27.11, and its `BindShortcuts` registers nothing.
**Verified:** 2026-10-05

The shell registers the hotkey on a Wayland session through `LinuxPortalHotkey` over
`DbusShortcuts` ([body-os-linux](../../modules/body-os-linux.md)), and both are tested only
against a fake portal over a socket pair. The task is an `#[ignore]`d test beside `portal_live`
that binds a chord through them on a real backend and presses it.

**What blocks it** ([globalshortcuts-portal](../../readings/globalshortcuts-portal.md)). The KDE
stack runs headless here without sudo, with `kglobalaccel` inside `kwin_wayland --virtual`, and
`org_kde_kwin_fake_input` presses keys that reach it. But the 5.27.11 backend registers shortcuts
only from a `shortcuts` option of `CreateSession`, which the 1.18 frontend does not forward, and
its `BindShortcuts` answers success with an empty list. `register` fails on it with "the portal
answered success without the shortcut", so the test cannot pass on any backend this distribution
has. A backend that implements `BindShortcuts`, such as Plasma 6's, is assumed and not checked.

**What the test does then.** Start the stack of the readings record with `XDG_CONFIG_HOME`
emptied, register `ctrl+alt+space` through `LinuxPortalHotkey` over `DbusShortcuts`, and press
it with a fake input client over the Wayland socket, which needs no new crate. It asserts one
callback for a tap, one for a held chord, and none for `ctrl+space`. The 5.27.11
backend opened no dialog and answered every call at once, so a test on a backend that behaves the
same runs unattended; a newer backend may ask the user first.

## History

- 2026-10-04: Filed when the portal backend and its shell wiring were built under
  [765](765-a-wayland-hotkey-through-the-globalshortcuts-portal.md).
- 2026-10-05: The KDE stack runs here without sudo. `kwin_wayland --virtual` 5.27.11 and
  `xdg-desktop-portal-kde` 5.27.11 ran from a userspace prefix on a private bus, and the backend
  exported `GlobalShortcuts` at `version` 1
  ([wayland-screencast-portal](../../readings/wayland-screencast-portal.md)). KWin ran with
  `--no-global-shortcuts` and no `kglobalaccel` was started, so no bind was tried.
- 2026-10-05: Corrected; the test cannot pass here. With `kglobalaccel` running and keys pressed
  through `org_kde_kwin_fake_input`, the 5.27.11 backend bound nothing through the frontend and
  ran `xdg-open` on System Settings' shortcuts page at each `BindShortcuts`, and the adapter's
  `register` failed. Called directly, the backend answered the three points: it parses
  `CTRL+ALT+space`, sends one `Activated` per auto-repeat, and reports a taken trigger as bound
  ([globalshortcuts-portal](../../readings/globalshortcuts-portal.md)). Filed
  [791](791-bind-the-wayland-hotkey-on-plasma-5-27.md).
