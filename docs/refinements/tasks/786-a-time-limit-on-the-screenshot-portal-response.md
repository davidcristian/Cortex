# A time limit on the screenshot portal's response

**Status:** open, waiting for its trigger
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-04
**Trigger:** the shell serves `LinuxPortalCapture` on a Wayland session, the wiring step of 752.
The time limit is built with that change or before it.

`DbusPortal::screenshot` in `body/crates/os_linux/src/portal_dbus.rs` waits for the `Response`
signal with `MessageIterator::next`, which has no time limit. A portal that never answers, such as
a backend whose permission dialog nobody closes, holds the tokio blocking thread the `BodyService`
server lent to the call: `off_worker` in `body/crates/rpc/src/server.rs` runs `spawn_blocking` with
no deadline. `LinuxPortalCapture` also holds its request lock for the whole capture, because the
wlr backend writes every picture to one path, so every later capture waits behind the hung one.

The fix is a deadline on the wait that fails the call as a `PortalError` and lets the lock go.
The value must allow for a backend that reports `version` 2 and asks the person once, which the
1.18.4 frontend does for an unsandboxed app too, as read in its source and not run
([752](752-wayland-screen-capture-through-the-portal.md)). `zbus` offers no
blocking wait with a timeout; the async `MessageStream` raced against a timer under
`zbus::block_on` is one way, and needs a timer crate as a direct dependency. A test over the
socket pair serves a fake portal that never emits `Response` and checks the call returns at the
limit, with the limit a constructor argument so the test does not wait the production value.

## History

- 2026-10-04: Filed when the portal capture core and its `zbus` adapter were built under
  [752](752-wayland-screen-capture-through-the-portal.md), which does not wire them into the shell
  yet, so no capture can hang today.
