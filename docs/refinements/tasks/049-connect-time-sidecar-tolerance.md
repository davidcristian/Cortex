# Connect-time sidecar tolerance and reconnect policy

**Status:** landed 2026-07-08
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Skip mode covered a sidecar that
failed *after* connect; a sidecar down *at brain startup* still failed `McpToolRegistry.connect`
in the wiring, with no re-dial. A Docker/uv probe against the real `mcp`/`httpx`/`anyio` stack
found the held-`AsyncExitStack` `connect` was the problem. Its anyio task-group cancel scopes
are task-bound (close-from-another-task errors) and a refused boot dial surfaced as a bare
`CancelledError`, uncatchable by skip mode. So `connect` is **retired** for a structured,
same-task `streamable_http_session` (`@asynccontextmanager`) driven by a new
`ReconnectingMcpToolRegistry` that opens a **fresh session per call**: `build_tool_registry` is
now synchronous and dials nothing, so a sidecar down at boot no longer fails the build (its
first-use open fails as `ToolError` that `SkipUnavailableToolRegistry` serves around) and a
recovered sidecar rejoins without a restart. CI-gated end to end over a scripted opener (open
success, refused dial, anyio `ExceptionGroup`, re-dial, listing passthrough) at 100%. Remaining
behind the same `ToolRegistry` port: a **session cache/pool** to retire the per-call open
overhead (a localhost handshake per describe/invoke, which is acceptable at personal scale, an
optimization when it matters).

## Trail

- 2026-07-08: Recorded in the ADR-0009 boot-tolerance addendum.
- 2026-08-08: The per-call open this entry called acceptable at personal scale was measured rather
  than left as an adjective, and the index struck that adjective the day it got a number: the open
  costs 17.8 ms on the transport this repo's own sidecars serve. The index read this entry's
  "behind the same `ToolRegistry` port" as false in the other direction too, a pooled session
  needing a scope that all seven combinators would have to forward. Both readings were recorded
  with the session cache and pool measurement rather than here.
