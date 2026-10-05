# Read only the portal owner's Response in every portal adapter

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** [ADR-0073](../../adr/ADR-0073-wayland-window-capture.md)
**Verified:** 2026-10-05

Any process on the session bus can send an `org.freedesktop.portal.Request.Response` signal on a
request handle, and the handle is predictable: the sender's unique name and a counted token.
`DbusScreenCast` asks the bus which unique name owns `org.freedesktop.portal.Desktop` and passes
it to `answered` in `body/crates/os_linux/src/request.rs`, whose match rule then reads only that
sender's `Response`. `DbusPortal` (`Screenshot`) and `DbusShortcuts` (`CreateSession` and
`BindShortcuts`) still call `request`, which passes no owner, so they read a `Response` from any
sender. A forged one could hand the screenshot backend a `uri` of the sender's choosing, which the
backend reads and then removes, or tell the hotkey a shortcut was bound when it was not.
`DbusShortcuts` already filters its `Activated` and `Deactivated` signals by the same owner.

**The work.** Resolve the owner once per call in both adapters with `owner` from
`shortcuts_dbus.rs`, fail the call when the bus names none, and pass it to `answered`; then have
`request` take the owner and drop the `None` case. The Screenshot fake in
`body/crates/os_linux/tests/portal_dbus.rs` serves no `org.freedesktop.DBus` object, so it needs
the `FakeBus` the shortcuts and screencast fakes serve, and each adapter a test with a forged
`Response` sent before the real one.

## History

- 2026-10-05: Filed when `DbusScreenCast` was built under
  [787](787-read-a-wayland-window-through-the-screencast-portal.md) with the owner filter, which
  the other two adapters do not have.
