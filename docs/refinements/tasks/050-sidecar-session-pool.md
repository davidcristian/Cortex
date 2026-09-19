# The sidecar session cache and pool

**Status:** declined 2026-08-08
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

[R-049](049-connect-time-sidecar-tolerance.md) priced the per-call open with an adjective and no
number, on a budget where a user-facing default had moved the same week on 0.515 s of time to
first token. So it was measured.

**How many opens a turn pays** was undocumented and larger than one per describe or invoke. With N
configured endpoints and the called tool owned by the k-th in config order, advertising costs N
opens and one cortex dispatch costs k + 1, because `AggregateToolRegistry.invoke` routes by
re-listing each registry until one claims the name; a subagent dispatch costs N more again,
because `UngatedToolRegistry.invoke` re-lists to recompute the set of tools needing confirmation
before delegating. Both walks are deliberate and live, so a tool a sidecar dropped or re-flagged
fails closed rather than routing stale, but nothing recorded that they make a delegated dispatch
cost twice a cortex one. The count is now asserted exactly against the shipped stack in
`packages/orchestrator/tests/test_mcp_handshake_live.py`, and deleting the second walk makes it
fail at `assert 1 == 2`.

**One open costs 17.8 ms** (n=30, 16.5 to 21.5), measured against a control server on the FastMCP
streamable-http transport `cortex_email` itself serves. A control rather than the email sidecar,
which needs Bridge credentials and does IMAP work, because the number wanted is the transport's
minimum: what the client and the protocol cost when the far end does nothing on connect. That is
0.4% of the 4.6 s a recalling turn takes to its first token, and 3% of the difference that moved
that default. Declined on that number.

**The measurement's real find was elsewhere.** The reference filesystem sidecar answered the same
open in 565 ms and a fresh-session dispatch in 1740 ms, a quarter of the whole time-to-first-token
budget spent before a token, and none of it was the handshake. Tracing every HTTP request
(`httpx.AsyncClient.send`, patched) showed each JSON-RPC round trip taking 3 to 5 ms and the rest
going to `supergateway` spawning a fresh `npx @modelcontextprotocol/server-filesystem` per
request, about 420 ms of which is npx resolving the fixed package again; bare `node` starts in 18
ms and the installed server answers in 107 ms. Worse, it never reaped them: after a few hundred
calls the shipped sidecar held 1452 live server processes and 20.5 GiB. Installing both fixed
packages once and running the bridge `--stateful` (one child per session, killed on the client's
goodbye, `--sessionTimeout` reaping a session abandoned without one) took the pre-token walk from
1156 ms to 146 ms and a dispatch from 1740 ms to 154 ms, left one process and 110 MiB after the
same run, and needed no brain code at all. A pool would have hidden that cost behind fewer
requests and fixed none of it.

Two corrections to [R-049](049-connect-time-sidecar-tolerance.md). Its "a localhost handshake per
describe/invoke" undercounts the requests: a fresh session's `invoke` issues three JSON-RPC calls,
not one, since the MCP SDK's `call_tool` caches tool output schemas per session and so pays for a
`tools/list` it will never reuse, and `describe_tools` issues two. And "behind the same
`ToolRegistry` port" is false: a pooled session must be closed, closing needs an explicit scope,
and a scope is a new port method that all seven combinators (`Aggregate`, `Filtered`, `Gated`,
`SkipUnavailable`, `Ungated`, `Composite`, `Sighted`) would have to forward. Without one the
session gets closed by a task other than the one that opened it, which is exactly the anyio
cancel-scope corruption the per-call open was adopted to avoid, and boot tolerance would have to
be rebuilt on the far side of it. That is a port change across the whole core, bought for 17.8 ms.

It reopens if a deployment makes the remainder matter: after the sidecar fix each call still pays
that sidecar's own child spawn, about 125 ms, which only a held session removes, the same calls on
a warm session measuring 4.4 ms and 3.8 ms. The right scope then is one tool loop, which is
same-task by construction, and the cost is the port change above.

## History

- 2026-07-08: Recorded as the item left behind the `ToolRegistry` port by
  [R-049](049-connect-time-sidecar-tolerance.md).
- 2026-08-08: Declined on measurement and recorded in ADR-0009 decision 9. The number is 17.8 ms
  on the transport this repo's own sidecars serve, 0.4% of a recalling turn's time to first token.
  The 565 ms the reference filesystem sidecar charged for the same open was not the handshake but
  that sidecar spawning an `npx` process per JSON-RPC request and leaking every one of them, so
  the fix was the compose command rather than a pool and the pre-token walk went from 1156 ms to
  146 ms with no brain code touched.
