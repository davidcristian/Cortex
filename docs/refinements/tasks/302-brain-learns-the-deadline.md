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

**The one thing this must not do is move the classification.** tonic's own expiry is not harmless
to fall back on. It arrives as a `Status::cancelled` carrying tonic's `transport::Error`, so
`status_to_error` classifies it `TransportError::Connection`, which is honest about the absent
answer and is also in the **retryable** set, so an expiry tonic enforced would be *retried* against
a brain that has just proved too slow or too stuck to answer. That is the load amplifier
[301](301-seam-attempt-deadline.md) classified a timeout terminal to avoid. (The reading this entry
first carried, that the expiry is *sourceless* and classifies `Rpc`, was false; it is corrected at
the origin ADR and pinned by
`tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure` in
`body/crates/rpc/tests/client.rs`.)

**And the header cannot be sent without arming that timer**, which is the constraint the design
turns on. `Request::set_timeout` inserts the `grpc-timeout` metadata and does nothing else, but the
client channel's own `GrpcTimeout` layer parses that header back off the outgoing request and arms
a local clock from it, so announcing a deadline to the brain and arming tonic's timer are one act,
not two choices. The design conclusion therefore stands and now has its reason: announce a header
**strictly longer** than the local deadline by a named grace margin, so the core's bound wins
deterministically and tonic's timer is dead weight rather than a coin flip. The margin is a
constant with a name and an argument behind its size (a loopback round trip plus the brain's own
header parsing, with room to spare), not a fudge factor. The header stays a courtesy to the brain
rather than a second enforcement point, and if a brain-sent `DEADLINE_EXCEEDED` ever does arrive it
maps to the same `TransportError::Timeout` the local clock produces, since both mean the same thing
to everything above the adapter. That mapping is the safety net; the margin is the mechanism.

## Trail

- 2026-08-18: opened by the per-attempt deadline ([301](301-seam-attempt-deadline.md)), which
  deliberately landed the bound without the header so the classification decision and the
  adapter's client construction did not have to move in one change.
- 2026-08-18, later: the tonic fact this plan rested on was corrected by running it rather than
  reading it, and the plan is firmer for it. The hazard is a *retried* deadline, not a mislabelled
  one, and `set_timeout` turns out to arm a local timer as a side effect of announcing the header,
  which is why the grace margin is now the mechanism rather than a nicety. Nothing here is done
  yet; the estimate is unchanged.
