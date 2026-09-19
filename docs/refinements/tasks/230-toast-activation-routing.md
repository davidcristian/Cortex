# Toast activation routing

**Status:** open, waiting for a consumer
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)
**Trigger:** a second consumer of toast interaction, such as snooze from the toast.
**Verified:** 2026-09-19

Clicking a shown toast does nothing, while the overlay's reminder card offers "open the
conversation this came from". Fixing that needs a change to the gRPC boundary: `NotifyRequest`
contains `title`, `body`, `reminder_id` and `tainted` and no `session_id` (unlike `DueReminder`,
which has had one since the boundary was designed), so the body cannot find the origin chat at
all. It also needs a way for a toast click to reach the running app, which for an unpackaged Win32
app means a registered COM activator: more Windows plumbing than the delivery it improves.

The push path is fire and forget. `_deliver` reads only `shown` (`ticker.py`),
`GrpcBodyGateway.notify` returns only `reply.shown` (`gateway.py`), the body's `OsService.notify`
builds a `body_core::Notification`, calls `Notify::show` and discards everything but `shown`
(`body/crates/rpc/src/server.rs`), and `WindowsNotify.show` renders a `ToastGeneric` toast with
nothing read back (`body/crates/os_windows/src/notify.rs`). The overlay never sees the call: it is
a `BrainService` client, while `Notify` is a `BodyService` RPC the body serves.

The design has two parts, recorded in the Consequences of
[ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md).

1. A `session_id` on `NotifyRequest`, regenerated into both stubs, set by the ticker's `_deliver`
   for a reminder and for a task from `item.session_id` (a session-less item sends `""`, the
   `DueReminder` convention, and its toast cannot be routed), passed through `BodyGateway.notify`
   and its adapter into `Notification`, and written by `toast_xml` as the toast's top-level
   `launch` argument.
2. A registered COM `INotificationActivationCallback` for the unpackaged app's `AppUserModelID`,
   so a clicked toast starts the app, reads the `launch` `session_id` back and routes the overlay
   to that chat through the same `onSelectSession`/`openSession` the reminder card already uses.

Part one cannot be done alone: its last step, the `launch` attribute in `toast_xml`, is
`cfg(windows)` and not covered in CI, and the payload should be designed together with its reader,
since snooze from the toast would want action buttons with their own arguments rather than one
top-level `session_id`. This is the same `NotifyRequest` `session_id` that the out-of-window
authoritative title entry ([session-read-rpc.md](../index.md#session-read-rpc)) names as one of
its reopen paths.

Corrected 2026-09-19, neither half measured: part two is smaller than described above. The channel
from the Tauri shell into the running overlay already exists, since the shell emits
`cortex:activate` on the hotkey and the tray (`body/app/src-tauri/src/lib.rs`) and the overlay
handles it (`body/app/src/overlay/activation.ts`), as it has since 2026-07-01. It has no payload, so
part two adds a session id to that event or a sibling of it. And the COM activator is only one of
two ways to hear a click: `ToastNotification` in the fixed `windows` 0.58 exposes an in-process
`Activated` event, and the body runs in the tray, so a click while the body runs could reach a
handler registered when the toast is shown, with no COM registration. The activator is what a click
needs when the process that showed the toast has exited. Whether `Activated` fires for an unpackaged
app's toast, and for one clicked from the notification centre rather than the popup, has never been
tested on a desktop.

## History

- 2026-07-16: Opened behind the body-side `Notify` trait and Windows toast, which is what made a
  shown toast exist to click.
- 2026-07-16: Checked against the tree and sharpened rather than built: it moved from actionable to
  waiting for a consumer, with the two-part design and the trigger recorded.
- 2026-09-13: Checked again and every claim holds. `NotifyRequest` still has no `session_id`,
  `DueReminder` still has one as field 6, `toast_xml` still renders one `ToastGeneric` binding with
  no `launch` attribute and no `<actions>` element, and `OsService.notify` still returns `shown`
  alone. The `snooze_scheduled` verb a model calls in a chat
  (`brain/packages/core/src/cortex_core/schedule_verbs.py`) reaches the store through a tool call
  and touches no toast, so it is not the second consumer this waits for.
- 2026-09-19: Checked again, same findings, and no surface offers snooze from a toast. What was
  wrong is part two's cost, corrected above.
