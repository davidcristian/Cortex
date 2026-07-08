# brain/packages/tools (`cortex_tools`)

**Purpose.** The MCP-client adapter for the core's `ToolRegistry` port (ADR-0009). A thin
translator between the core's tool values and the MCP Python SDK's `ClientSession`: it lists
a server's tools and calls them, holding no state (the one hard rule) beyond the injected
session. The core keeps talking only to `ToolRegistry`; this package makes any MCP server a
source of audited, model-callable tools.

**Public contract** (everything importable from `cortex_tools`; `__all__` is the API):

- `McpToolRegistry(session: McpSession)` is a `ToolRegistry` over one already-open session.
  - `describe_tools()` → `list_tools()` on the session, mapping each MCP `Tool` to a
    `ToolSpec` (name, description, `inputSchema` as the parameters) to advertise to the model.
    Every spec arrives `gated=False` and MCP annotations are deliberately dropped. A sidecar
    must never self-declare policy; gating for remote tools is stamped brain-side by the
    composition root's `GatedToolRegistry` overlay (`CORTEX_TOOLS_GATED`, ADR-0022).
  - `invoke(call)` → `call_tool(name, arguments)`, joining the result's text content blocks
    into `ToolResult.content` (non-text blocks skipped) and setting `is_error` from the
    server's `isError`.
- `streamable_http_session(url)` is an `@asynccontextmanager` opening a **structured, same-task**
  streamable-http MCP session (`streamable_http_client` + `ClientSession` + `initialize`), yielded
  for the scope of one `async with`. Replaces the old `connect` classmethod, which held the
  session on a long-lived `AsyncExitStack` whose anyio task-group cancel scopes cannot be exited
  from a different task (the source of the boot-time `CancelledError` the eager wiring hit). Real
  network I/O.
- `ReconnectingMcpToolRegistry(opener)` is a `ToolRegistry` that opens a **fresh session per call**
  from an injected `opener` (`streamable_http_session` in production; ADR-0009 boot-tolerance
  addendum). It holds no session between calls, so: a sidecar **down at boot is tolerated** (the
  first call's open fails as `ToolError`, which an outer `SkipUnavailableToolRegistry` reports and
  serves around) and a **recovered sidecar rejoins without a restart** (the next call re-dials). An
  open failure (`McpError`/`OSError`/`httpx.HTTPError`, unwrapped from anyio's `ExceptionGroup` by
  `except*`) crosses the port as `ToolError`; a `ToolError` from the live session's own
  `describe`/`invoke` passes through untouched (no double-wrap). Trades a per-call open for
  robustness. A session cache is a later optimization behind the same port.
- `McpSession` is the `Protocol` slice of `mcp.ClientSession` the adapter uses (`list_tools`,
  `call_tool`); the real session and the CI fake both satisfy it.
- `LoggingAuditSink` is a `ToolAuditSink` writing one structured `logging` record per
  dispatched call. A success logs the result *size* (not its content, since a file read can be
  large or sensitive); a failure logs the short error detail; both log the tool name,
  arguments, the result's `trust` provenance (so "did this turn read untrusted content?"
  is answerable from the durable trail alone, per ADR-0013 decision 2), and timestamp (the
  AGENTS.md audit gate).

**Error contract.** Every MCP transport/protocol failure crosses the `ToolRegistry` port as
`ToolError` with the cause chained: a listing/call failure on a live session (`McpError`,
socket `OSError`) from `McpToolRegistry`, and a session-**open** failure (additionally
`httpx.HTTPError`, and a refused dial arrives as `httpx.ConnectError` inside anyio's
`ExceptionGroup`, unwrapped by `except*`) from `ReconnectingMcpToolRegistry`. The dispatcher
turns a `ToolError` into an `is_error` `ToolResult` so the tool loop keeps going and the model
is told; an outer `SkipUnavailableToolRegistry` instead serves around an unavailable sidecar.
A tool that *ran* but reported an error (`CallToolResult.isError`) is a normal `is_error`
result, not an exception.

**Invariants.**
- Untrusted by default (ADR-0013): `invoke` leaves `ToolResult.trust` at its fail-closed
  `UNTRUSTED` default, so every remote MCP result (file contents, email bodies) is framed as
  data and taints the turn. The adapter needs no per-tool trust annotation; the core's default
  carries it. (A genuinely trusted remote tool, if one ever exists, is a composition-root overlay.)
- Stateless per call: no tool state outlives a call (the one hard rule); the adapter holds
  only the injected session.
- Adapter-only: real MCP/network I/O lives here, never in the core (AGENTS.md gate 3).
- Fully typed, pyright strict clean; 100% line+branch over a fake `McpSession` returning real
  `mcp` result types and a scripted session-`opener` (open success, refused dial, anyio
  `ExceptionGroup`, re-dial after recovery, listing-error passthrough). No server, no network.
  The live contract against a real streamable-http MCP server is the `integration`-marked
  `tests/test_registry_live.py` (now driving `ReconnectingMcpToolRegistry`; run per
  docs/runbooks/tools-mcp.md).
- Pinned to the MCP SDK v1.x (`mcp>=1.23,<2`); v2 is pre-release. A v2 migration is an
  adapter-only change behind the unchanged `ToolRegistry` port.

**Dependencies.** cortex-core (the `ToolRegistry`/`ToolAuditSink` ports, the tool values, and
typed errors), mcp (the client SDK), httpx (the streamable-http transport, whose connect errors
the open path maps). The composition root (`cortex_orchestrator.wiring`, via `build_tool_registry`)
builds one `ReconnectingMcpToolRegistry(partial(streamable_http_session, url))` per configured
endpoint (no dial at startup), optionally composing the core's
`FilteredToolRegistry`/`AggregateToolRegistry`/`SkipUnavailableToolRegistry` around them (ADR-0009
refinements + boot-tolerance addenda, but this adapter stays single-server), and wraps the result in
an audited `ToolDispatcher`.
