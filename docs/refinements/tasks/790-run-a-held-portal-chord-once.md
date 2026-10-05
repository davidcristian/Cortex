# Run a held portal chord once

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-05

`LinuxPortalHotkey` runs a binding's callback for every `Activated` signal that names it, and
does not read `Deactivated` ([body-os-linux](../../modules/body-os-linux.md)). The KDE backend
sends one `Activated` per auto-repeat of a held chord and one `Deactivated` at the release: 24 and
1 for a chord held 1.5 s at KWin's default repeat settings
([globalshortcuts-portal](../../readings/globalshortcuts-portal.md)). A held chord therefore
shows and hides the overlay once per repeat. The X11 backend skips the repeats, and Windows
registers with `MOD_NOREPEAT`, so on both a held chord runs once. The `Hotkey` check list does not
see the difference, because its rig presses each chord as a tap.

The fix changes the core, the `ShortcutsPortal` port and its adapter: the adapter also
subscribes to `Deactivated`, `next_activation` returns which of the two signals came, and the
listener runs a binding only on the first `Activated` after a `Deactivated` for it, or on
its first `Activated`. To decide before building: what to do on a backend that never sends
`Deactivated`, where that rule would run a chord once and never again. The `Activated` timestamp
is one way to tell a repeat from a new press there.

No backend here binds through the frontend
([788](788-test-the-portal-hotkey-on-a-kde-wayland-session.md)), so the test is the fake portal
sending the measured sequence: several `Activated`, then one `Deactivated`.

## History

- 2026-10-05: Filed when the KDE backend, given the shortcut directly, was measured under
  [788](788-test-the-portal-hotkey-on-a-kde-wayland-session.md).
