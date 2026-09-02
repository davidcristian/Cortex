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
  `describe`/`invoke` passes through untouched (no double-wrap). It pays a per-call open for that
  boot tolerance, and the trade was **measured on 2026-08-08 and kept**: the open costs 17.8 ms against
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
  AGENTS.md audit gate). The logger it writes through is declared in the module as `_LOGGER_NAME`
  rather than spelled inside the `getLogger` call, because four places restate that name and none
  of them can import it: the two runbooks that tell an operator to select the trail by it, the
  docstring that fixes the shipped level at INFO because this trail rides on it, and that module's
  suite, which writes a line under the name to prove it. `scripts/crosscheck.py` ties all four to
  the declaration, so a rename here fails the gate rather than leaving them describing a trail
  nothing writes (ADR-0009 audit-logger addendum). This contract names the declaration rather than
  the literal, deliberately: a fifth restatement added here only so the gate would have something
  to compare is a mention the gate itself caused to exist.
  The word the line opens with is declared beside it as `_MESSAGE` and handed to the
  emitting call, for the same reason and against the same three restatements, the runbook sentence
  that tells a reader what to look for and that suite's two spellings (ADR-0009 audit-message
  addendum). The call itself is a fifth place the registry reads, `_logger.info({name},` over
  this module, so a call handed another word fails the gate (ADR-0009 held-call addendum). The
  sample gate cannot stand in for either: this sink builds its `extra=` by condition, so no
  runbook may print one of these lines as a rendered sample and have it hold.
  A line also names the work it was for: `session_id`, `turn_id`,
  `task_id` and `item_id`, taken off the dispatch's stamp and written under the field names the
  rest of the brain's log lines use.
  This is the one sink that imports those five names from
  `cortex_core.log_fields` rather than writing them out, because it is the one place that writes
  the whole vocabulary as a list (ADR-0009 one-vocabulary addendum). The trail therefore reads
  turn by turn, a delegated call names both its task and
  the turn that spawned it (ADR-0009 named-work addendum), and a scheduled fire names the item
  that fired (named-call addendum). It names the **call** too, `call_id` off `ToolCall.id`, which
  is what the result and its `Role.TOOL` message are keyed by, so a turn's lines stop being
  interchangeable. That one is the model's own string on a cortex dispatch, printed for the reason
  the tool name and arguments are and read back by nothing; the field name is what tells a reader
  which class it is in, and the formatter's quoting and `VALUE_CHARS` are what keep it from
  forging a field or flooding a line. An id the dispatch did not have is
  left off the line rather than printed empty, since a caller with no chat, turn or task behind
  it has nothing to print there. All of it rides the record as `extra` and reaches the line through the
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

**Nothing here bounds a call, and that is deliberate.** The MCP session's own wait for a response
is unbounded by construction (`ClientSession.call_tool`'s `read_timeout_seconds` defaults to
`None`, which is `anyio.fail_after(None)`), so a sidecar that accepts a call and never answers
would hold a turn open for as long as the process lives. What bounds it is the core's
`BoundedToolRegistry`, which the composition root wraps each endpoint in **innermost** (ADR-0009
bound addendum): an overrun cancels the call and crosses the port as `ToolError`, which is
precisely the shape `SkipUnavailableToolRegistry` above it already serves around, so a hung
sidecar ends up on the same path as one whose dial was refused. It sits above rather than inside
this adapter because
the bound must cover the dial as well as the call, and because a bound belongs to the deployment
rather than to one transport.

**Shared contract.** `tests/registry_contract.py` holds the six checks every `ToolRegistry`
implementation owes and `tests/test_registry_contract.py` drives them over four: the core's
`InMemoryToolRegistry`, `McpToolRegistry`, the `ReconnectingMcpToolRegistry` production
wires, and that one under the `BoundedToolRegistry` the root wraps it in, the last three over a
serving `McpSession` that answers real `mcp` result types. The six are
that every served tool is advertised with its name, purpose and schema in order; that the listing
is read again on every walk; that a call comes back stamped with its own id and the tool's text;
that a tool which ran and failed is an `is_error` result rather than an exception; that a name the
registry does not serve never comes back as a success; and that an unreachable backend raises
`ToolError` from both verbs.

The fifth of those is worded that loosely because the two kinds of registry genuinely
diverge, and the port now says so: a registry that holds its whole set raises `ToolNotFoundError`
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
  carries it. A remote result is re-stamped trusted only by the brain's `OwnTextToolRegistry`
  at the composition root, and only when its whole content is byte-equal to text the brain holds
  in code (`cortex_orchestrator/own_texts.py`), rendered with the call's own argument; nothing
  the sidecar writes, `isError` and `_meta` included, is read for it (ADR-0013 own-text
  addendum). That overlay's contract runs over this adapter and the fake alike
  (`test_own_text_contract.py`), and one consequence of this adapter is recorded there: `invoke`
  joins the text blocks and carries no image, so an image block beside the exact text is dropped
  before the overlay sees the result and the text alone is re-stamped, which is sound because the
  dropped block reaches neither the model nor the audit log. A tool whose every answer should be
  trusted is a built-in, never a remote overlay.
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
