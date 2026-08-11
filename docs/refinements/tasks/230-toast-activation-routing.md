# Toast activation routing

**Status:** open, dead until a consumer
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** a second consumer of toast interaction, such as snooze-from-the-toast.

A shown toast is inert: clicking it does nothing, while the
overlay's reminder card offers "open the conversation this came from". Closing that asymmetry
is **not behind an unchanged seam**, which is why it is recorded rather than folded in:
`NotifyRequest` carries `title`/`body`/`reminder_id`/`tainted` and **no `session_id`** (unlike
`DueReminder`, which has carried one since the seam was designed), so the body cannot resolve
the origin chat at all today. It also needs an activation channel from the toast back into the
running app, and for an unpackaged Win32 app that means a registered COM activator, which is
more Windows plumbing than the delivery it improves. Wait for a second consumer of toast
interaction (snooze-from-the-toast would be the other one) before spending it.

The two-part design is recorded in the [ADR-0025 toast-activation
addendum](../../adr/ADR-0025-scheduling-reminders.md). Read against the tree, the `session_id`
the obvious fix wants on `NotifyRequest` has no reader but a host-side Windows one, so adding
it now would be the dead wire this sweep declined five times the same day (blended relevance,
`GetVolume`, the structured redaction event, occurrence history, the per-error-code retry table),
on the same "no consumer" test. **The push path is fire and forget, confirmed end to end.**
`_deliver` reads only the `shown` verdict (`ticker.py`), `GrpcBodyGateway.notify` returns only
`reply.shown` (`gateway.py`), the body's `OsService.notify` builds a `body_core::Notification`,
calls `Notify::show`, and discards all but `shown` (`body/crates/rpc/src/server.rs`), and
`WindowsNotify.show` renders a fire-and-forget `ToastGeneric` toast with nothing read back
(`body/crates/os_windows/src/notify.rs`); the Linux and macOS backends are `unimplemented!()`.
The overlay never sees the call at all: it is a `BrainService` client, while `Notify` is a
`BodyService` RPC the body serves, so no `notify` reference exists anywhere under `body/app/src`.
The only reader of any toast payload beyond `shown` is the host-side `toast_xml`
(`cfg(windows)`, never measured in CI), and the only thing that could act on a clicked toast is a
COM activator that does not exist. **The two-part design, so the next pass re-derives nothing.**
Part one, the seam prerequisite: a `session_id` on `NotifyRequest` (a new proto field
regenerated into both stubs), set by the ticker's `_deliver` for both kinds (a reminder and a
task each carry the origin `item.session_id`; a session-less item carries `""`, the `DueReminder`
convention, and its toast is simply not routable), plumbed through `BodyGateway.notify` and its
adapter into `Notification`, and embedded by `toast_xml` as the toast's top-level `launch`
argument so a click's activation payload names the origin chat. Part two, the host-side
activator: a registered COM `INotificationActivationCallback` for the unpackaged app's
`AppUserModelID`, plus an activation channel from the Tauri shell into the running overlay, so a
clicked toast invokes the app, reads the `launch` `session_id` back, and routes the overlay to
that chat through the same `onSelectSession`/`openSession` the reminder card's origin-chat control
already uses. **Why part one does not land alone.** Its last mile (the `launch` attribute in
`toast_xml`) is itself host-side `cfg(windows)` and uncovered, so the field cannot be plumbed
end to end in the CI-gated half; and the activation payload should be designed with its reader,
since the entry's own named second consumer, snooze-from-the-toast, wants toast action buttons
carrying their own arguments rather than a bare top-level `session_id`, so committing the wire
shape now risks being wrong when the activator arrives. **Trigger:** a second consumer of toast
interaction (snooze-from-the-toast) that shares the COM plumbing's cost, at which point the proto
field and the toast launch payload are designed together with the activator that reads them, as
one piece. This is the same `NotifyRequest` `session_id` the out-of-window authoritative title
entry ([session-read-seam.md](../index.md#session-read-seam)) names as one of its own reopen paths.

## Trail

- 2026-07-16: Newly deferred behind the landing of the body-side `Notify` trait and Tauri toast,
  which is what made a shown toast exist to click. The area's count held at 10 across that
  landing, one entry closing and this one opening behind it.
- 2026-07-16: Read against the tree and sharpened rather than built, moving from
  actionable-with-a-seam-change to dead-until-a-consumer with the two-part design and the trigger
  recorded. A sharpened deferral is still open, so the count was unchanged.
