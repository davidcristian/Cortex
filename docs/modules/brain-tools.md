# brain/packages/tools (`cortex_tools`)

**Purpose.** The MCP-client adapter for the core's `ToolRegistry` port (ADR-0009). A thin
translator between the core's tool values and the MCP Python SDK's `ClientSession`: it lists
a server's tools and calls them, holding no state (the one hard rule) beyond the injected
session. The core keeps talking only to `ToolRegistry`; this package makes any MCP server a
source of audited, model-callable tools.

**Public contract** (everything importable from `cortex_tools`; `__all__` is the API):

- `McpToolRegistry(session: McpSession)` is a `ToolRegistry`.
  - `describe_tools()` → `list_tools()` on the session, mapping each MCP `Tool` to a
    `ToolSpec` (name, description, `inputSchema` as the parameters) to advertise to the model.
  - `invoke(call)` → `call_tool(name, arguments)`, joining the result's text content blocks
    into `ToolResult.content` (non-text blocks skipped) and setting `is_error` from the
    server's `isError`.
  - `connect(url)` classmethod → opens a streamable-http MCP session (holds the transport and
    session open on an `AsyncExitStack`), `initialize()`s it, and returns `(registry, closer)`.
    Real network I/O. The composition root calls it; only the live test exercises it for real.
- `McpSession` is the `Protocol` slice of `mcp.ClientSession` the adapter uses (`list_tools`,
  `call_tool`); the real session and the CI fake both satisfy it.
- `LoggingAuditSink` is a `ToolAuditSink` writing one structured `logging` record per
  dispatched call. A success logs the result *size* (not its content, since a file read can be
  large or sensitive); a failure logs the short error detail; both log the tool name,
  arguments, the result's `trust` provenance (so "did this turn read untrusted content?"
  is answerable from the durable trail alone, per ADR-0013 decision 2), and timestamp (the
  AGENTS.md audit gate).

**Error contract.** Every MCP transport/protocol failure (`McpError`, socket `OSError`)
crosses the `ToolRegistry` port as `ToolError` with the cause chained; the dispatcher turns
that into an `is_error` `ToolResult` so the tool loop keeps going and the model is told. A
tool that *ran* but reported an error (`CallToolResult.isError`) is a normal `is_error`
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
  `mcp` result types (no server, no network). The live contract against a real streamable-http
  MCP server is the `integration`-marked `tests/test_registry_live.py` (run per
  docs/runbooks/tools-mcp.md).
- Pinned to the MCP SDK v1.x (`mcp>=1.23,<2`); v2 is pre-release. A v2 migration is an
  adapter-only change behind the unchanged `ToolRegistry` port.

**Dependencies.** cortex-core (the `ToolRegistry`/`ToolAuditSink` ports, the tool values, and
typed errors), mcp (the client SDK). The composition root (`cortex_orchestrator.wiring`) calls
`McpToolRegistry.connect` per configured endpoint, optionally composing the core's
`FilteredToolRegistry`/`AggregateToolRegistry` around the sessions (ADR-0009 refinements
addendum, with this adapter staying single-server), and wraps the result in an audited
`ToolDispatcher`.
