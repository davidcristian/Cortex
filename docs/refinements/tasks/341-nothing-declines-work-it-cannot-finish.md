# Nothing declines work it cannot finish, and the remaining time does not travel

**Status:** landed 2026-08-21
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

The brain now reads `time_remaining()` in exactly one place and for exactly one purpose: a unary
handler the caller gave up on writes an abandonment line naming the RPC and the time it had left
([322](322-brain-reads-the-remaining-time.md)). That needed no judgement about any particular RPC,
which is why it went first. What is left is the part that does.

Three shapes, each a decision about one handler or one downstream port, and each changing what a
caller gets back rather than only what an operator reads:

- **A read that will not fit declines before it starts.** `ListSessions` with milliseconds left
  could answer `DEADLINE_EXCEEDED` immediately rather than spending a store round trip nobody will
  read. The question this turns on is what "will not fit" means when nothing measures how long a
  store read takes: a fixed floor is a number nobody has measured, and a measured one is a
  histogram this repo does not keep.
- **A partial answer beats none.** A session read whose memory cascade will not fit could return
  the transcript without it. That is a different reply rather than a refusal, so it needs the
  overlay's side asked too: a transcript missing its recalled context, with nothing on the wire
  saying so, is the shape a reader cannot tell from a session that recalled nothing.
- **The remaining time travels.** The model host call and the MCP tool calls a handler makes are
  where the seconds actually go, and each currently runs on its own bound with no relation to the
  caller's, so a call that inherits none of its caller's deadline can outlive the request that
  made it by an unbounded margin. This is the largest of the three and the only one that is a port
  change: `ModelHost` and the MCP client would both grow a per-call deadline.

The fence from the entry that opened this still holds: `Converse` announces nothing and must keep
announcing nothing, so none of the three may reach a turn. Note also that the announcement is
deliberately longer than the bound the body enforces, so a handler that gives up early is
answering a call the body has usually stopped waiting for already; the value here is in the
downstream work that outlives the request, not in the handler's own return.

## Trail

- 2026-08-20: Opened by the close of
  [322](322-brain-reads-the-remaining-time.md), which landed the one shape of the four that needed
  no per-RPC judgement and left the three that do. Recorded in the ADR-0024 abandonment addendum.
- 2026-08-21: Closed with all three shapes decided and one built. **The remaining time travels**
  was re-derived first and two of its claims did not survive: the model host is already bounded on
  every verb by `CORTEX_MODELHOST_TIMEOUT_S`, which is additionally compared at boot against the
  worst stop the sidecar reports, and no unary handler on `BrainService` reaches either downstream
  port, so there is no caller's deadline for one to inherit. What was really unbounded was the tool
  seam, in the stronger sense that this repo stated no bound for it at all: the MCP session's own
  wait for a response is `anyio.fail_after(None)`, so a sidecar that accepted a call and never
  answered held a turn open indefinitely, and the skip-and-report degraded mode could not see it,
  being built entirely on a `ToolError` a wedged sidecar never raises. That is what landed:
  `BoundedToolRegistry` in the core's tool family, wrapped innermost around each configured
  endpoint by the composition root and carrying `CORTEX_TOOLS_CALL_TIMEOUT_S`, so an overrun
  cancels the call and crosses the port as the `ToolError` every layer above already handles. The
  built-in tools beside it are deliberately not wrapped. The fence held by being looked at: nothing
  reads `time_remaining()`, `Converse` announces nothing, and no port signature moved. Recorded in
  the ADR-0009 bound addendum, with a dated pointer at the ADR-0024 origin.
  **A read that will not fit declines before it starts** was declined, on the unmeasured floor it
  always turned on and on a second reason re-derivation added, that the grace margin makes the
  handler's own early return worth about one Redis round trip while costing an invented expiry:
  [360](360-a-read-that-will-not-fit-declines-early.md). **A partial answer beats none** turned out
  to have no site at all, no read RPC on this seam recalling anything and the one handler that
  touches the cascade being a write whose ordering is already deliberate:
  [361](361-a-read-rpc-recalls-nothing-to-omit.md). The close opened
  [362](362-one-bound-for-every-sidecar.md) (one bound for every sidecar) and
  [363](363-the-call-bound-and-the-run-bound-are-unordered.md) (the new bound is unordered against
  the subagent run deadline it sits inside).
