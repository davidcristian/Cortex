# The brain is told how long it has and does nothing with it

**Status:** done 2026-08-20
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)

Every unary call from the body includes `grpc-timeout` ([302](302-brain-learns-the-deadline.md)),
and grpc.aio therefore gives the servicer a real `ServicerContext.time_remaining()`. No handler in
`cortex_orchestrator` reads it. What the header buys today is the half that needs no brain code:
grpc.aio enforces the deadline itself, cancelling the handler coroutine when it expires, which is a
bound the brain applies on its own clock rather than one that waits for a stream reset. A live run
against a real `grpc.aio` `BrainService` measured both: `time_remaining` of 1.048 s for an
announced 1.05 s, and a handler cancelled at 800 ms because the body's own bound dropped the call
first.

The other half is a handler deciding what to do with time it can measure before it starts. Three
shapes, each its own small decision: a `ListSessions` with milliseconds left could answer
`DEADLINE_EXCEEDED` immediately instead of spending a store round trip nobody will read; a session
read whose memory cascade will not fit could return the transcript without it; a handler that is
cancelled could log the abandonment, which today looks like any other cancelled call. The remaining
time also has to be passed on, since the model host and MCP tool calls a handler makes are where
the seconds go, and a call that inherits none of its caller's deadline can outlive the request that
made it.

None of this is a transport change and none belongs in the body. `Converse` announces nothing and
must keep announcing nothing: a turn is long by design, and a handler reading a deadline there
would enforce something this interface deliberately does not have.

## History

- 2026-08-19: Opened by the commit that added the deadline header
  ([302](302-brain-learns-the-deadline.md)), which measured what the brain does with an announced
  deadline (it enforces it, through grpc.aio, and reads nothing) and left the reading half here.
- 2026-08-20: Fixed as the abandonment line, the one of the four shapes needing no per-RPC
  judgement: `AbandonedCallInterceptor` writes a `WARNING` naming the RPC and the
  `time_remaining()` a dropped unary call had left, and judges none of it. `Converse` is excluded
  by its kind rather than by name, so the exclusion is code. The three shapes that are a policy per
  RPC or per port moved to [341](341-nothing-declines-work-it-cannot-finish.md).
