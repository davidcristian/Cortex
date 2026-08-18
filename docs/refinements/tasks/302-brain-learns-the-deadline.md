# The brain is never told the deadline the body is holding it to

**Status:** open, actionable
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

The per-attempt deadline is enforced entirely on the body's side: `within_deadline` drops the
call when the clock wins, which resets the in-flight HTTP/2 stream, and nothing on the wire ever
says how long the body intended to wait. gRPC has a header for exactly this, `grpc-timeout`, and
the brain's own server would then enforce it too, so a handler that is mid-query when the body
gives up learns it has been abandoned instead of finishing a reply nobody will read. On a
loopback pair sharing one machine that waste is small and real: the store query, the memory
cascade, and the reply serialization all keep running.

The natural place to set it is the seam-token interceptor (`body/crates/rpc/src/client.rs`),
which already touches every outgoing request and can call `Request::set_timeout`. That is the
part that makes this its own slice rather than a line: the interceptor is built once per client,
so the client needs a way to carry a per-call deadline into it, which means either rebuilding the
`BrainServiceClient` per deadline (the channel and the token would have to be held for that, and
the redacting `Debug` reviewed with them) or threading the duration through every translation
helper in `sessions.rs`, `reminders.rs`, `preferences.rs` and `converse.rs`.

**The one thing this must not do is move the classification.** tonic reports its own expired
timeout as a sourceless `Status::cancelled`, which `status_to_error` reads as a status the brain
sent, so a body that started trusting tonic's expiry would report its own deadline as
`TransportError::Rpc` and draw the indicator `Degraded`, claiming an answer that never came. The
header is a courtesy to the brain, not a second enforcement point: the local bound stays where it
is, and if a brain-sent `DEADLINE_EXCEEDED` ever wins the race it maps to the same
`TransportError::Timeout` the local clock produces, since both mean the same thing to everything
above the adapter.

## Trail

- 2026-08-18: opened by the per-attempt deadline ([301](301-seam-attempt-deadline.md)), which
  deliberately landed the bound without the header so the classification decision and the
  adapter's client construction did not have to move in one change.
