# The brain is told how long it has and does nothing with it

**Status:** landed 2026-08-20
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Every unary call from the body now carries `grpc-timeout`
([302](302-brain-learns-the-deadline.md)), and grpc.aio hands the servicer a real
`ServicerContext.time_remaining()` because of it. No handler in `cortex_orchestrator` reads it.
What the announcement buys today is therefore the half that needs no brain code at all: grpc.aio
enforces the deadline itself, cancelling the handler coroutine when it expires, which is a bound
the brain holds on its own clock rather than one that depends on a stream reset arriving. A live
run against a real `grpc.aio` `BrainService` measured both halves at once: `time_remaining` of
1.048 s for an announced 1.05 s, and a handler cancelled at 800 ms because the body's own bound
dropped the call first. The other half is untouched.

That half is a handler deciding what to do with time it can measure *before* it starts. The shapes
worth weighing, each its own small decision rather than one rule: a `ListSessions` that sees
milliseconds left could answer `DEADLINE_EXCEEDED` immediately instead of spending a store round
trip nobody will read; a session read whose memory cascade will not fit could return the
transcript without it rather than nothing at all; a handler that is cancelled could log the
abandonment as such, which today is indistinguishable in the logs from any other cancelled call.
The remaining time also wants to travel: the model host and the MCP tool calls a handler makes are
where the seconds actually go, and a call that inherits none of its caller's deadline can outlive
the request that made it by an unbounded margin.

None of this is a transport change and none of it belongs in the body. It is a per-handler
decision about what "not enough time left" means for each RPC, in the orchestrator's tree with the
orchestrator's tests, which is why it was not carried in the slice that put the number on the
wire. The seam is unchanged either way: the announcement is already longer than the bound the body
enforces, so a brain that gives up early is answering a call the body has usually stopped waiting
for, and one that never looks keeps today's behaviour exactly.

Note that `Converse` announces nothing and must keep announcing nothing: a turn is long by design,
and a handler that read a deadline there would be enforcing a feature this seam deliberately does
not have.

## Trail

- 2026-08-19: opened by the courtesy header landing
  ([302](302-brain-learns-the-deadline.md)), which measured what the brain does with an announced
  deadline today (it enforces it, through grpc.aio, and reads nothing) and left the reading half
  here rather than shipping a per-handler policy inside a transport slice.
- 2026-08-20: Landed as the abandonment line, the one of its four shapes needing no per-RPC
  judgement: `AbandonedCallInterceptor` writes a `WARNING` naming the RPC and the
  `time_remaining()` a dropped unary call had left, judging none of the three facts that reading
  can carry. `Converse` is passed through by shape rather than by name, so the fence is code. The
  three shapes that *are* a policy per RPC or per port moved to
  [341](341-nothing-declines-work-it-cannot-finish.md). Recorded in the ADR-0024 abandonment
  addendum.
