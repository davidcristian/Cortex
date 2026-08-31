# Rust BrainTransport reminder methods

**Status:** landed 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 transport addendum](../../adr/ADR-0025-scheduling-reminders.md).
`list_due_reminders` / `ack_reminder` (+ the `DueReminder` core mirror) behind the committed proto
shapes, translated in a new `body/crates/rpc/src/reminders.rs` beside the session reads, with the
retry split the entry predicted (list retried as idempotent, ack forwarded). The reason for that
split sharpened in the writing: a repeated ack is harmless *brain*-side, but a retry after a **lost
reply** answers `acked=false` for a reminder the same call cleared, so the caller reads "nothing to
ack"; the test is whether a repeat can change the answer, not whether the call is a write. CI-gated
at 100% and mutation-proven (retry present, retry absent, row mapping, ack answer; each reverted
individually makes a distinct test fail). Remaining of the in-slice remainder: the overlay's
reminders-on-open surface (fetch on open, badge tainted, ack on dismiss), now unblocked, and the
body-side `Notify` OS trait + the Tauri toast rendering reminder text inert (host-validated). The
brain treats the interim `Unimplemented` as any push failure, so pull already delivers end to end.
