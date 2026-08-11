# The sidecar session cache and pool

**Status:** declined 2026-08-08
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The entry above priced the per-call open with an
adjective and no number, on a budget where a user-facing default moved the same week on 0.515 s
of time to first token, so it was measured rather than shrugged at, and every clause of it was
re-derived from the tree first. **How many** opens a turn pays turned out to be undocumented and
larger than "one per describe/invoke": with N configured endpoints and the called tool owned by
the k-th in config order, advertising costs N and one cortex dispatch costs k + 1, because
`AggregateToolRegistry.invoke` routes by re-listing each registry until one claims the name, and
a **subagent** dispatch costs N more again, because `UngatedToolRegistry.invoke` re-lists to
recompute the gated set before delegating. Both walks are deliberate (live, so a tool a sidecar
dropped or re-flagged fails closed rather than routing stale); what nothing recorded is that they
make a delegated dispatch cost twice a cortex one. The count is now asserted exactly, against the
shipped stack, in `packages/orchestrator/tests/test_mcp_handshake_live.py`, and it is
mutation-proven (deleting the ungated re-walk turns it red at `assert 1 == 2`).
**What one open costs is 17.8 ms** (n=30, 16.5 to 21.5), measured against a control server on
the FastMCP streamable-http transport `cortex_email` itself serves (a control rather than the
email sidecar, which needs Bridge credentials and does IMAP work, because the number wanted is
the transport's floor: what the client and the protocol cost when the far end does nothing on
connect). That is 0.4% of the 4.6 s a recalling turn takes to its first token and 3% of the
difference that moved that default. **Declined on that number.** The measurement's real find was elsewhere, and it is why the run was worth doing: the
reference filesystem sidecar answered the same open in **565 ms** and a fresh-session dispatch in
**1740 ms**, a quarter of the whole TTFT budget spent before a token, and **none of it was the
handshake**. Tracing every HTTP request (`httpx.AsyncClient.send`, patched) showed each JSON-RPC
round trip taking 3 to 5 ms and the rest going to `supergateway` **spawning a fresh
`npx @modelcontextprotocol/server-filesystem` per request**, about 420 ms of which is npx
resolving the pinned package again (bare `node` starts in 18 ms, the installed server answers in
107 ms). Worse, it never reaped them: after a few hundred calls the shipped sidecar held **1452
live server processes and 20.5 GiB**. Installing both pinned packages once and running the bridge
`--stateful` (one child per session, killed on the client's goodbye, `--sessionTimeout` reaping a
session abandoned without one) took the pre-token walk from **1156 ms to 146 ms** and a dispatch
from **1740 ms to 154 ms**, left one process and 110 MiB after the same run, and needed **no brain
code at all**. A pool would have hidden that cost behind fewer requests and fixed none of it.
Two further corrections to the entry above. Its "a localhost handshake per describe/invoke"
**undercounts the requests**: a fresh session's `invoke` issues three JSON-RPC calls, not one,
since the MCP SDK's `call_tool` caches tool output schemas per session and so pays for a
`tools/list` it will never reuse; `describe_tools` issues two. And "behind the same
`ToolRegistry` port" is **false**, which is the design finding the entry itself asked for: a
pooled session must be closed, closing needs an explicit scope, and a scope is a new port method
that all seven combinators (`Aggregate`, `Filtered`, `Gated`, `SkipUnavailable`, `Ungated`,
`Composite`, `Sighted`) would have to forward. Without one the session gets closed by a task
other than the one that opened it, which is exactly the anyio cancel-scope corruption the
per-call open was adopted to escape, and boot tolerance would have to be rebuilt on the far side
of it. That is a port change across the whole core seam, bought for 17.8 ms. It reopens if a
deployment ever makes the residual bite: after the sidecar fix each call still pays that
sidecar's own child spawn, about 125 ms, which only a held session removes (the same calls on a
warm session measure 4.4 ms and 3.8 ms). The honest scope when it does is **one tool loop**,
which is same-task by construction, and the price of admission is the port change above.
Nothing else opened behind it.

## Trail

- 2026-07-08: Recorded as the item remaining behind the `ToolRegistry` port in the connect-time
  sidecar tolerance entry: a session cache/pool to retire the per-call open overhead, a localhost
  handshake per describe/invoke, which that entry called acceptable at personal scale and an
  optimization when it matters.
- 2026-08-08: Declined on measurement and recorded in the ADR-0009 handshake addendum. The
  adjective was never converted into a number, and the number is 17.8 ms on the transport this
  repo's own sidecars serve, 0.4% of a recalling turn's time to first token. The 565 ms the
  reference filesystem sidecar charged for the same open was not the handshake at all but that
  sidecar spawning an `npx` process per JSON-RPC request and leaking every one of them, 1452 of
  them holding 20.5 GiB after a few hundred calls, so the fix was the compose command rather than a
  pool and the pre-token walk went from 1156 ms to 146 ms with no brain code touched. The entry's
  "behind the same `ToolRegistry` port" was false in the other direction too, a pooled session
  needing a scope that all seven combinators would forward. What is left as the reopen trigger is
  only the residual a held session would remove and the port change that holding one would cost.
