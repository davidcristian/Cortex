# The brain is never told the deadline the body enforces

**Status:** done 2026-08-19
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

The per-attempt deadline is enforced entirely on the body's side: `within_deadline` drops the call
when the clock wins, which resets the in-flight HTTP/2 stream, and nothing on the wire says how
long the body intended to wait. gRPC has a header for this, `grpc-timeout`, and the brain's own
server would then enforce it too, so a handler that is mid-query when the body gives up is told the
call was abandoned instead of finishing a reply nobody will read.

The natural place to set it is the token interceptor (`body/crates/rpc/src/client.rs`), which
already touches every outgoing request and can call `Request::set_timeout`. That is what made this
its own slice rather than a line: the interceptor is built once per client, so the client needs a
way to get a per-call deadline into it.

The header cannot be sent without also starting tonic's own timer, which is the constraint the
design turns on. `Request::set_timeout` inserts the `grpc-timeout` metadata and does nothing
else, but the client channel's `GrpcTimeout` layer parses that header back off the outgoing
request and starts a local clock from it. Since tonic's expiry classifies as the retryable
`TransportError::Connection`, letting it decide would retry against a brain that has just proved
too slow to answer, which is what [301](301-a-per-attempt-deadline-on-the-body-to-brain-calls.md) classified a timeout
terminal to avoid. So the announced
header is strictly longer than the local deadline by a named grace margin, and the core's bound
wins.

What was built is the header, its margin and the reply mapping. `RetryPlan` gained
`announced_deadline_for(method)`, which is `deadline_for` plus `ANNOUNCED_DEADLINE_GRACE_MS`
(250 ms) and `None` where the enforced deadline is `None`, so the number the brain is told is a
core decision and the adapter only writes it down. `BrainSeamClient` gained `announcing(plan)`,
holds the channel, the token and that plan, and builds one generated client per call
(`body/crates/rpc/src/call.rs`, which took the interceptor and the `SEAM_TOKEN_HEADER` declaration
with it under the line cap); the shell's `seam::connect()` reads one plan and hands it to both the
decorator that enforces and the client that announces. The redacting `Debug` is written out rather
than derived, since the client now holds the token itself.

The shape was neither of the two the entry named, though closer to the first. The client is rebuilt
per call, but the deadline is not passed in by a caller: the client asks the plan it was given, per
method, which keeps the policy in the core. Threading a duration through `sessions.rs`,
`reminders.rs`, `preferences.rs` and `converse.rs` would have put the same number in four modules'
signatures. The reply side does need the value, so those three unary modules take a `SeamCall`
rather than a bare client.

The classification did not move. A `DEADLINE_EXCEEDED` the brain sends on a call that announced
something maps to `TransportError::Timeout { after }`; with nothing announced it stays `Rpc`. All
of them are terminal, so no retry decision turns on the difference.

The premise this entry rested on was half wrong, which is the part worth keeping. A real
`grpc.aio` `BrainService` driven by a real announcing client reported `time_remaining` of 1.048 s
against an announced 1.05 s, and its handler was cancelled 800 ms in, at the instant the body
dropped the call rather than at the deadline it had been told. So the servicer coroutine already
dies on the stream reset, and the abandoned store query and memory cascade were mostly not still
running. What the header adds is a bound the brain holds on its own clock rather than one waiting
for a reset a killed body may never send, plus a number a handler can plan against before it
starts.

## History

- 2026-08-18: Opened by the per-attempt deadline ([301](301-a-per-attempt-deadline-on-the-body-to-brain-calls.md)), which
  deliberately left the header out so the classification decision and the adapter's client
  construction did not have to move in one change.
- 2026-08-18, later: The tonic fact this plan rested on was corrected by running it rather than
  reading it. The hazard is a retried deadline, not a mislabelled one, and `set_timeout` starts a
  local timer as a side effect of announcing the header, which is why the grace margin is the
  mechanism rather than a nicety.
- 2026-08-19: Done, with the ordering proven rather than asserted: the core test walks every method
  over three plans, and the adapter test drives a hanging brain with both clocks running and still
  gets `Timeout`, which only the core's bound can produce. Two things the work found that the plan
  did not. The wire cannot express an arbitrary deadline and tonic panics past its ceiling, so an
  inexpressible announcement is dropped rather than clamped, a shorter announcement being the one
  failure the margin exists to prevent. And the waste this entry was opened over was already mostly
  avoided by the stream reset, measured end to end against a real grpc-python brain. What the brain
  does with the number it is now told is [322](322-brain-reads-the-remaining-time.md).
