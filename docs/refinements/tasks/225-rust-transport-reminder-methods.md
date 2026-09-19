# Rust BrainTransport reminder methods

**Status:** done 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Decided in [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 5. `list_due_reminders`
and `ack_reminder`, plus the `DueReminder` core mirror, sit behind the committed proto shapes and
are translated in a new `body/crates/rpc/src/reminders.rs` beside the session reads, with the retry
split the entry predicted: the list is retried as idempotent and the ack is not.

The reason for that split sharpened in the writing. A repeated ack is harmless on the brain side,
but a retry after a lost reply answers `acked=false` for a reminder the same call cleared, so the
caller reads "nothing to ack". The test is whether a repeat can change the answer, not whether the
call is a write.

Mutation-proven on four points: retry present, retry absent, row mapping, and the ack answer, each
reverted individually failing a distinct test. The brain treats the interim `Unimplemented` from
push as any other push failure, so pull already works end to end.

## History

- 2026-07-14: Closed, leaving the overlay's reminders-on-open surface and the body-side `Notify`
  trait with its Tauri toast as the remaining parts of the slice.
