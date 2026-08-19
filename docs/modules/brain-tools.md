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
    server's `isError`. A source a sidecar declared in the result's MCP `_meta` (under
    `_SOURCE_META_KEY`, `"cortex/source"`) is read into `ToolResult.source` (`_declared_source`):
    it rides beside the content blocks, so the model-facing text is untouched, and the core's
    `claimed_source` is the trust gate, admitting only a sanitized, claimed SENDER/URI and dropping
    an attested kind a hostile sidecar might forge (ADR-0027 sidecar addendum). The key is a
    cross-deployable wire contract with the standalone email sidecar, which writes the same shape.
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
  robustness, and the trade was **measured on 2026-08-08 and kept**: the open costs 17.8 ms against
  a control server on the FastMCP streamable-http transport `cortex_email` serves (the transport's
  floor, with nothing happening server-side on connect), and a pooled session is not the
  local optimization it looked like, since closing one needs a scope that every combinator would
  have to forward and, without a scope, gets closed from a task other than the one that opened it,
  which is the cancel-scope failure this design exists to avoid (ADR-0009 handshake addendum). A
  turn's open count is N per advertisement and k + 1 per cortex dispatch (N endpoints, the called
  tool owned by the k-th), doubling per dispatch for a subagent because `UngatedToolRegistry`
  re-lists before delegating; `packages/orchestrator/tests/test_mcp_handshake_live.py` asserts it.
  Note that a fresh session's `invoke` is two round trips beyond the open, not one: the MCP SDK's
  `call_tool` caches tool output schemas per session, so the first call in a session also lists.
- `McpSession` is the `Protocol` slice of `mcp.ClientSession` the adapter uses (`list_tools`,
  `call_tool`); the real session and the CI fake both satisfy it.
- `LoggingAuditSink` is a `ToolAuditSink` writing one structured `logging` record per
  dispatched call. A success logs the result *size* (not its content, since a file read can be
  large or sensitive); a failure logs the short error detail; both log the tool name,
  arguments, the result's `trust` provenance (so "did this turn read untrusted content?"
  is answerable from the durable trail alone, per ADR-0013 decision 2), and timestamp (the
  AGENTS.md audit gate). All of it rides the record as `extra` and reaches the line through the
  process entry's formatter (ADR-0038 rendered-fields addendum); the sink used to serialize its
  own JSON copy into the message because the shipped handler printed no `extra`, and no longer
  does, so the trail now depends on that formatter being installed.

**Error contract.** Every MCP transport/protocol failure crosses the `ToolRegistry` port as
`ToolError` with the cause chained: a listing/call failure on a live session (`McpError`,
socket `OSError`) from `McpToolRegistry`, and a session-**open** failure (additionally
`httpx.HTTPError`, and a refused dial arrives as `httpx.ConnectError` inside anyio's
`ExceptionGroup`, unwrapped by `except*`) from `ReconnectingMcpToolRegistry`. The dispatcher
turns a `ToolError` into an `is_error` `ToolResult` so the tool loop keeps going and the model
is told; an outer `SkipUnavailableToolRegistry` instead serves around an unavailable sidecar.
A tool that *ran* but reported an error (`CallToolResult.isError`) is a normal `is_error`
result, not an exception.

**Shared contract.** `tests/registry_contract.py` holds the six checks every `ToolRegistry`
implementation owes and `tests/test_registry_contract.py` drives them over three: the core's
`InMemoryToolRegistry`, `McpToolRegistry`, and the `ReconnectingMcpToolRegistry` production
wires, the last two over a serving `McpSession` that answers real `mcp` result types. The six are
that every served tool is advertised with its name, purpose and schema in order; that the listing
is read again on every walk; that a call comes back stamped with its own id and the tool's text;
that a tool which ran and failed is an `is_error` result rather than an exception; that a name the
registry does not serve never comes back as a success; and that an unreachable backend raises
`ToolError` from both verbs.

The fifth of those sits at the altitude it does because the two kinds of registry genuinely
diverge, and the port now says so: a registry that knows its whole set raises `ToolNotFoundError`
for an unknown name, while this adapter can only relay what its server says, and an MCP server
answers an unknown tool with an error *result*. The difference is visible downstream, since the
dispatcher stamps its own `ToolError` message `TRUSTED` and leaves a relayed result `UNTRUSTED`,
which is the correct reading of each: one sentence is ours and the other is the server's. Callers
that must tell the two apart resolve ownership by a live `describe_tools` walk first, which is
what `AggregateToolRegistry` does before it routes.

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
