# Connect-time sidecar tolerance and reconnect policy

**Status:** done 2026-07-08
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Skip mode covered a sidecar that failed after connect; a sidecar down at brain startup still
failed `McpToolRegistry.connect` in the wiring, with no second attempt. A Docker and uv probe
against the real `mcp`, `httpx` and `anyio` stack found the cause: the `connect` that held an
`AsyncExitStack` has anyio task-group cancel scopes bound to the task that opened them, so closing
from another task errors, and a refused dial at boot arrived as a bare `CancelledError` that skip
mode could not catch.

`connect` was therefore removed in favour of a structured, same-task `streamable_http_session`
(`@asynccontextmanager`) driven by a new `ReconnectingMcpToolRegistry` that opens a fresh session
per call. `build_tool_registry` is now synchronous and dials nothing, so a sidecar down at boot no
longer fails the build, its first-use open failing as a `ToolError` that
`SkipUnavailableToolRegistry` handles, and a recovered sidecar rejoins without a restart. Covered
end to end at 100% over a scripted opener: open success, refused dial, anyio `ExceptionGroup`,
re-dial, and listing passthrough.

What it left behind is [R-050](050-sidecar-session-pool.md), a session cache or pool to remove the
per-call open.

## History

- 2026-07-08: Recorded in ADR-0009 decision 9.
- 2026-08-08: The per-call open this entry called acceptable at personal scale was measured: 17.8
  ms on the transport this repo's own sidecars serve. The claim that a pool sits behind the
  unchanged `ToolRegistry` port was also false, a pooled session needing a scope that all seven
  combinators would have to forward. Both findings are recorded with the measurement.
