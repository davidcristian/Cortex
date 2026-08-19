# The brain is never told the deadline the body is holding it to

**Status:** landed 2026-08-19
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

**What landed** is the header, its margin, and the reply mapping that goes with it.
`RetryPlan` gained `announced_deadline_for(method)`, which is `deadline_for` plus
`ANNOUNCED_DEADLINE_GRACE_MS` (250 ms) and `None` where the enforced deadline is `None`, so the
number the brain is told is a core decision and the adapter only writes it down. `BrainSeamClient`
gained `announcing(plan)`, holds the channel, the token and that plan, and builds one generated
client per call (`body/crates/rpc/src/call.rs`, which took the interceptor and the
`SEAM_TOKEN_HEADER` declaration with it under the line cap); the shell's `seam::connect()` reads
one plan and hands it to both the decorator that enforces and the client that announces. The
redacting `Debug` this entry predicted is written out rather than derived, since the client now
holds the token itself.

**The carrying shape was neither of the two this entry named**, though it is closer to the first.
Rebuilding the client per call is what happens, but the deadline is not threaded in from a caller:
the client asks the plan it was given, per method, which keeps the policy in the core and the
translation in the adapter. Threading a duration through `sessions.rs`, `reminders.rs`,
`preferences.rs` and `converse.rs` would have put the same number in four modules' signatures. The
reply side does need the value, so those three unary modules take a `SeamCall` rather than a bare
client, which carries the announcement to the status mapping.

**The classification did not move.** The pin is untouched and still green, a new unit check holds
that an *announced* call does not move it either, and the new answer is only for a
`DEADLINE_EXCEEDED` the brain sent on a call that announced something, which maps to
`TransportError::Timeout { after }`. Announced with nothing to announce it stays `Rpc`; all of
them are terminal, so no retry decision turns on the difference.

**And the premise this entry rested on was half wrong**, which is the part worth keeping. A real
`grpc.aio` `BrainService` driven by a real announcing client reported `time_remaining` of 1.048 s
against an announced 1.05 s, and its handler cancelled 800 ms in, at the instant the body dropped
the call rather than at the deadline it had been told. So the servicer coroutine already dies on
the stream reset, and the abandoned store query and memory cascade were mostly not burning after
all. What the header adds is a bound the brain holds on its own clock rather than one waiting for
a reset a killed body or a half-open connection may never send, plus a number a handler can plan
against before it starts. The measurement is in the origin ADR.

## Trail

- 2026-08-18: opened by the per-attempt deadline ([301](301-seam-attempt-deadline.md)), which
  deliberately landed the bound without the header so the classification decision and the
  adapter's client construction did not have to move in one change.
- 2026-08-18, later: the tonic fact this plan rested on was corrected by running it rather than
  reading it, and the plan is firmer for it. The hazard is a *retried* deadline, not a mislabelled
  one, and `set_timeout` turns out to arm a local timer as a side effect of announcing the header,
  which is why the grace margin is now the mechanism rather than a nicety. Nothing here is done
  yet; the estimate is unchanged.
- 2026-08-19: landed as the header plus the named margin, with the ordering proven rather than
  asserted (the core test walks every method over three plans, and the adapter test drives a
  hanging brain with both clocks armed and still gets `Timeout`, which is the answer only the
  core's bound can produce). Two things the work found that the plan did not. The wire cannot
  spell an arbitrary deadline and tonic panics past its ceiling, so an unspellable announcement is
  dropped rather than clamped, a shorter announcement being the one failure mode the margin
  exists to prevent. And the waste this entry was opened over was already mostly cut by the
  stream reset, which grpc.aio turns into a cancellation of the handler, so the value of the
  header is a brain-side clock and an up-front number rather than the rescue of a burning
  cascade, which an end-to-end run against a real grpc-python brain measured rather than argued. What the brain does with the number it is now told is
  [322](322-brain-reads-the-remaining-time.md), which this closure opens.
