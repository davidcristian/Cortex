# Nothing declines work it cannot finish, and the remaining time does not travel

**Status:** done 2026-08-21
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)

The brain reads `time_remaining()` in exactly one place and for one purpose: a unary handler the
caller gave up on writes an abandonment line naming the RPC and the time it had left
([322](322-brain-reads-the-remaining-time.md)). That needed no judgement about any particular RPC.
What is left is the part that does, three changes to what a caller gets back:

- A read that will not fit declines before it starts. `ListSessions` with milliseconds left could
  answer `DEADLINE_EXCEEDED` immediately rather than spending a store round trip nobody will read.
  It turns on what "will not fit" means when nothing measures how long a store read takes: a fixed
  floor is a number nobody has measured, and a measured one is a histogram this repo does not keep.
- A partial answer beats none. A session read whose memory cascade will not fit could return the
  transcript without it. That is a different reply rather than a refusal, so the overlay's side has
  to be asked too: a transcript missing its recalled context, with nothing on the wire saying so,
  cannot be told apart from a session that recalled nothing.
- The remaining time travels. The model host call and the MCP tool calls a handler makes are where
  the seconds go, and each runs on its own bound with no relation to the caller's. This is the
  largest of the three and the only port change: `ModelHost` and the MCP client would both grow a
  per-call deadline.

`Converse` announces nothing and must keep announcing nothing, so none of the three may reach a
turn. The announcement is also deliberately longer than the bound the body enforces, so a handler
that gives up early is answering a call the body has usually stopped waiting for; the value is in
the downstream work that outlives the request.

## History

- 2026-08-20: Opened by the close of [322](322-brain-reads-the-remaining-time.md), which built the
  one shape of the four that needed no per-RPC judgement.
- 2026-08-21: Closed with all three decided and one built. The remaining time travels was checked
  first and two of its claims did not survive: the model host is already bounded on every verb by
  `CORTEX_MODELHOST_TIMEOUT_S`, which is additionally compared at boot against the worst stop the
  sidecar reports, and no unary handler on `BrainService` reaches either downstream port, so there
  is no caller's deadline to inherit. What was really unbounded was the tool interface, in the
  stronger sense that this repo stated no bound for it at all: the MCP session's own wait for a
  response is `anyio.fail_after(None)`, so a sidecar that accepted a call and never answered held a
  turn open indefinitely, and the skip-and-report degraded mode could not see it, being built
  entirely on a `ToolError` a stuck sidecar never raises. That is what was built:
  `BoundedToolRegistry` in the core's tool family, wrapped innermost around each configured
  endpoint by the composition root and holding `CORTEX_TOOLS_CALL_TIMEOUT_S`, so an overrun cancels
  the call and crosses the port as the `ToolError` every layer above already handles. The built-in
  tools beside it are deliberately not wrapped. The `Converse` exclusion was checked rather than
  assumed: nothing reads `time_remaining()`, `Converse` announces nothing, and no port signature
  moved. Recorded in ADR-0009 decision 10. A read that will not fit declines before it starts was
  declined, on the unmeasured floor it always turned on and on a second reason, that the grace
  margin makes the handler's own early return worth about one Redis round trip while costing an
  invented expiry: [360](360-a-read-that-will-not-fit-declines-early.md). A partial answer beats
  none turned out to have no site at all, no read RPC here recalling anything and the one handler
  that touches the cascade being a write whose ordering is already deliberate:
  [361](361-a-read-rpc-recalls-nothing-to-omit.md). The close opened
  [362](362-one-bound-for-every-sidecar.md) and
  [363](363-the-call-bound-and-the-run-bound-are-unordered.md).
