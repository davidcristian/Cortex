# brain/packages/tools (`cortex_tools`)

**Purpose.** The MCP-client adapter for the core's `ToolRegistry` port, and the adapters of its
`ToolAuditSink` port (ADR-0009). It is a thin translator between the core's tool values and the MCP
Python SDK's `ClientSession`: it lists a server's tools and calls them, holding no state beyond the
injected session (the one hard rule). The core keeps talking only to `ToolRegistry`; this package
turns any MCP server into a source of audited, model-callable tools.

## Public contract

`__all__` is the API.

### Registries

- `McpToolRegistry(session: McpSession)` is a `ToolRegistry` over one already-open session.
  - `describe_tools()` calls `list_tools()` and maps each MCP `Tool` to a `ToolSpec` (name,
    description, `inputSchema` as the parameters) to advertise to the model. Every spec arrives with
    `gated=False` and MCP annotations are deliberately dropped: a sidecar must never declare its own
    policy, so which remote tools need confirmation is stamped brain-side by the composition root's
    `GatedToolRegistry` overlay (`CORTEX_TOOLS_GATED`, ADR-0022).
  - `invoke(call)` calls `call_tool(name, arguments)`, joins the result's text content blocks into
    `ToolResult.content` and sets `is_error` from the server's `isError`. Image blocks are read into
    `ToolResult.images` by `blocks.result_images`, beside the text rather than inside it. A source a
    sidecar declared in the result's MCP `_meta` (under `_SOURCE_META_KEY`, `"cortex/source"`) is
    read into `ToolResult.source` by `_declared_source`: the declaration is a mapping of two fields,
    the kind word (`_KIND_FIELD`, `"kind"`) and the value (`_VALUE_FIELD`, `"value"`), and it sits
    beside the content blocks, so the model-facing text is untouched. The core's `claimed_source`
    decides trust, admitting only a sanitized, claimed SENDER or URI and dropping an attested kind a
    hostile sidecar might forge (ADR-0027 decision 10). The key and both field names are a wire
    contract with the standalone email sidecar, which writes the same shape, and `crosscheck.py`
    compares each pair of bindings, each module's use of its own binding, and this contract's
    quotation of each (`scripts/emailcouplings.py`, ADR-0042).
- `ReconnectingMcpToolRegistry(opener)` is a `ToolRegistry` that opens a **fresh session per call**
  from an injected `opener` (`streamable_http_session` in production, ADR-0009 decision 9). It holds
  no session between calls, so a sidecar **down at boot is tolerated** (the first call's open fails
  as `ToolError`, which an outer `SkipUnavailableToolRegistry` reports and serves around) and a
  **recovered sidecar rejoins with no restart** (the next call dials again). An open failure
  (`McpError`, `OSError` or `httpx.HTTPError`, unwrapped from anyio's `ExceptionGroup` by `except*`)
  crosses the port as `ToolError`; a `ToolError` from the live session's own `describe` or `invoke`
  passes through untouched. It pays a per-call open for that boot tolerance, and the trade was
  **measured on 2026-08-08 and kept**: the open costs 17.8 ms against a control server on the
  FastMCP streamable-http transport `cortex_email` serves, with nothing happening server-side on
  connect, and a pooled session is not the local optimization it looked like, since closing one
  needs a scope every combinator would have to forward and, with no scope, gets closed from a task
  other than the one that opened it, which is the cancel-scope failure this design avoids. A turn's
  open count is N per advertisement and k + 1 per cortex dispatch (N endpoints, the called tool
  owned by the k-th), doubling per dispatch for a subagent because `UngatedToolRegistry` re-lists
  before delegating; `packages/orchestrator/tests/test_mcp_handshake_live.py` asserts it. A fresh
  session's `invoke` is two round trips beyond the open, not one: the MCP SDK's `call_tool` caches
  tool output schemas per session, so the first call in a session also lists.
- `streamable_http_session(url)` is an `@asynccontextmanager` opening a **structured, same-task**
  streamable-http MCP session (`streamable_http_client`, `ClientSession`, `initialize`), yielded for
  the scope of one `async with`. It replaces an earlier `connect` classmethod that held the session
  on a long-lived `AsyncExitStack` whose anyio task-group cancel scopes cannot be exited from a
  different task. Real network I/O.
- `McpSession` is the `Protocol` slice of `mcp.ClientSession` the adapter uses (`list_tools`,
  `call_tool`); the real session and the CI fake both satisfy it.

### Image blocks

- `blocks.result_images(result)` reads every `ImageContent` block of a `CallToolResult` into an
  `ImagePart`, in wire order (ADR-0009 decision 19). An MCP image block states no dimensions and
  `ImagePart` requires them, so the width and height come out of the bytes through
  `headers.image_size`. Bad base64, a size past `MAX_IMAGE_EDGE`, a mime type outside
  `ALLOWED_MIME_TYPES`, and every refusal a header reader raises all arrive as `ImageError`, which
  `invoke` crosses the port as `ToolError` with the cause chained. The mime type stays the sidecar's
  declaration, judged against the core's allow-list rather than against the bytes; the reader is
  picked by the signature the bytes have instead. It is not exported from `cortex_tools`, the
  adapter being its only caller.
- `headers.image_size(data)` states the width and height an encoded image's container declares, for
  the three formats `ALLOWED_MIME_TYPES` lists. PNG's IHDR chunk and a WebP RIFF container are
  fixed-offset reads, the WebP in whichever of its three shapes its first chunk is: `VP8 `, whose
  two edges sit under two scale bits; `VP8L`, which packs them across bits rather than bytes; and
  `VP8X`, which states a canvas one less than each edge. A JPEG's frame header is not a fixed-offset
  read: it sits behind a chain of segments whose lengths the bytes themselves state, so reaching it
  means following a length an attacker wrote. That walk is bounded three ways. It takes at most
  `MAX_JPEG_SEGMENTS` steps; every segment must state a length of at least two bytes, so the cursor
  advances every step; and every offset is compared against the buffer before it is read, so a
  truncated or self-referential chain raises `ImageError` rather than looping, reading past the end,
  or raising `struct.error`. Nothing here reaches a pixel, an entropy-coded byte or a palette, so
  the posture `cortex_core.images` sets out still applies. A block with none of the three signatures
  is refused rather than accepted at a guessed size.

### Audit sinks

- `LoggingAuditSink` is a `ToolAuditSink` writing one structured `logging` record per dispatched
  call. A success logs the result's *size*, not its content, since a file read can be large or
  sensitive; a failure logs the short error detail. Both log the tool name, the arguments, the
  result's `trust` provenance (so "did this turn read untrusted content?" is answerable from the
  durable trail alone, ADR-0013 decision 2) and the timestamp.
  - Logging the size and not the content means an answer that corrected the model and succeeded
    leaves none of its text on the line, and nowhere durable holds that text either, the tool loop's
    `Role.TOOL` results reaching a store only inside the handoff record an escalating turn writes.
    What a line does say about such an answer is `trust`: a remote result reaches the trail
    `untrusted` unless the composition root's own-text overlay found it byte-equal to a sentence the
    brain holds (`cortex_orchestrator/own_texts.py`), so on a line naming a tool that set declares,
    `ok=True` with `trust=trusted` says the answer was one of those sentences, and the `arguments`
    the same line prints are what it is rendered from. Every other successful answer reports its
    size alone, which is the decision rather than an omission: a bounded first line of the content
    would put part of every file read on the trail to serve the few answers that correct the model
    (ADR-0009 decision 16).
  - A line also names the work it was for: `session_id`, `turn_id`, `task_id` and `item_id`, taken
    off the dispatch's stamp and written under the field names the rest of the brain's log lines
    use. This is the one sink that imports those five names from `cortex_core.log_fields` rather
    than writing them out, because it is the one place that writes the whole vocabulary as a list
    (ADR-0046 decision 1). So the trail reads turn by turn, a delegated call names both its task and
    the turn that spawned it, and a scheduled fire names the item that fired. It names the **call**
    too, `call_id` off `ToolCall.id`, which is what the result and its `Role.TOOL` message are keyed
    by, so a turn's lines stop being interchangeable. That one is the model's own string on a cortex
    dispatch, printed for the reason the tool name and arguments are and read back by nothing; the
    field name is what tells a reader which class it is in, and the formatter's quoting and
    `VALUE_CHARS` are what keep it from forging a field or flooding a line. An id the dispatch did
    not have is left off the line rather than printed empty.
  - All of it is attached to the record as `extra` and reaches the line through the process entry's
    formatter (ADR-0051 decision 1), so the trail depends on that formatter being installed.
  - The logger it writes through is declared in the module as `_LOGGER_NAME` rather than written
    inside the `getLogger` call, because four places restate that name and none of them can import
    it: the two runbooks that tell an operator to select the trail by it, the docstring that fixes
    the shipped level at INFO because this trail depends on it, and that module's suite, which
    writes a line under the name to prove it. `scripts/crosscheck.py` compares all four with the
    declaration (ADR-0045 decision 13). The word the line opens with is declared beside it as
    `_MESSAGE` and handed to the emitting call, for the same reason and against the same three
    restatements (ADR-0045 decision 14). The emitting call is itself a fifth place the registry
    reads, `_logger.info({name},` over this module, so a call handed another word fails the check.
    `samplecheck.py` covers this sink's lines a different way: its `extra=` is built by condition,
    so no reading of the source can list one line's fields, and a rendered sample of it in the tools
    runbook is compared with a whole line this module's own suite asserts against the shipped
    formatter, which is why that suite asserts one whole line per shape the runbook prints (ADR-0045
    decision 11).
  - The field set is built by `invocation_fields(invocation)`, which the file sink below also uses,
    so the two trails cannot name different fields.
- `JsonLinesAuditSink(path)` is the second `ToolAuditSink`, off unless `CORTEX_TOOLS_AUDIT_FILE`
  names a file (ADR-0009 decision 18). It appends one JSON object per call, built by `durable_line`,
  so `jq 'select(.turn_id == "<turn id>")'` answers what the log line could only be grepped for. Its
  rules:
  - **It keeps no more than the line prints.** `durable_value` keeps a field as its parsed value
    when the line's formatter prints it whole, and otherwise keeps the formatter's own rendering as
    a string, cut marker included. That covers a value past `VALUE_CHARS` and a URL credential split
    across two strings of `arguments`, which the formatter withholds over its whole rendering and a
    string-by-string pass would miss. A successful call still keeps its size and never its content.
    A secret-named key inside `arguments`, at any depth, is withheld first by `withhold_secrets`,
    the walk the formatter runs over every field, so the file keeps the parsed object with
    `<redacted>` in the same places the line prints it (ADR-0009 decision 17).
  - **One record is one line.** The line is ASCII JSON, so every control character, line separator
    and lone surrogate arrives escaped and nothing can fail to encode. A file that ends mid-line,
    from an append a full disk cut short, gets a newline before the next record.
  - **A failed append never fails the dispatch.** The dispatcher awaits the sink with no guard, so a
    raise here would end the turn. A refused open or write, and a value the formatter could not
    render either (a non-string key, a cycle, nesting past the interpreter's depth), is logged
    instead as a `tool.audit.gap` warning on `cortex_tools.audit_file` with `error`, `path` and
    `tool`, and the call is still on the log line written before it.
  - **The file is opened per record**, created with mode `0600` and appended through `O_APPEND`, so
    a file an operator moves away is created afresh on the next call and needs no signal. Retention
    is the operator's; nothing here rotates or deletes.
- `TeeAuditSink(sinks)` records each invocation to every sink it holds, in order. The composition
  root puts `LoggingAuditSink` first.
- The shared checks are `tests/audit_contract.py`, run by `tests/test_audit_contract.py` over
  `RecordingAuditSink`, the file sink over a temporary file, and a tee of the two: one row per
  record in dispatch order, the work ids a record was handed and no others, and a hostile tool name
  or call id kept inside its own row. `LoggingAuditSink` is not among them, its trail being a stream
  nothing reads back; `tests/test_audit.py` asserts its whole lines instead.

## Error contract

Every MCP transport or protocol failure crosses the `ToolRegistry` port as `ToolError` with the
cause chained: a listing or call failure on a live session (`McpError`, socket `OSError`) from
`McpToolRegistry`, and a session-**open** failure (additionally `httpx.HTTPError`, and a refused
dial arriving as `httpx.ConnectError` inside anyio's `ExceptionGroup`, unwrapped by `except*`) from
`ReconnectingMcpToolRegistry`. The dispatcher turns a `ToolError` into an `is_error` `ToolResult` so
the tool loop keeps going and the model is told; an outer `SkipUnavailableToolRegistry` instead
serves around an unavailable sidecar. A tool that *ran* but reported an error
(`CallToolResult.isError`) is a normal `is_error` result, not an exception.

**Nothing here bounds a call, and that is deliberate.** The MCP session's own wait for a response is
unbounded by construction (`ClientSession.call_tool`'s `read_timeout_seconds` defaults to `None`,
which is `anyio.fail_after(None)`), so a sidecar that accepts a call and never answers would hold a
turn open for as long as the process lives. What bounds it is the core's `BoundedToolRegistry`,
which the composition root wraps each endpoint in **innermost** (ADR-0009 decision 10): an overrun
cancels the call and crosses the port as `ToolError`, which is the shape
`SkipUnavailableToolRegistry` above it already serves around, so a hung sidecar ends up on the same
path as one whose dial was refused. It sits above rather than inside this adapter because the bound
must cover the dial as well as the call, and because a bound belongs to the deployment rather than
to one transport.

## Shared contract

`tests/registry_contract.py` holds the six checks every `ToolRegistry` implementation owes and
`tests/test_registry_contract.py` drives them over four: the core's `InMemoryToolRegistry`,
`McpToolRegistry`, the `ReconnectingMcpToolRegistry` production wires, and that one under the
`BoundedToolRegistry` the root wraps it in, the last three over a serving `McpSession` that answers
real `mcp` result types. The six are that every served tool is advertised with its name, purpose and
schema in order; that the listing is read again on every walk; that a call comes back stamped with
its own id and the tool's text; that a tool which ran and failed is an `is_error` result rather than
an exception; that a name the registry does not serve never comes back as a success; and that an
unreachable backend raises `ToolError` from both methods.

The fifth is worded that loosely because the two kinds of registry genuinely differ, and the port
now says so: a registry that holds its whole set raises `ToolNotFoundError` for an unknown name,
while this adapter can only relay what its server says, and an MCP server answers an unknown tool
with an error *result*. The difference is visible downstream, since the dispatcher stamps its own
`ToolError` message `TRUSTED` and leaves a relayed result `UNTRUSTED`, which is the correct reading
of each: one sentence is ours and the other is the server's. Callers that must tell the two apart
resolve ownership by a live `describe_tools` walk first, which is what `AggregateToolRegistry` does
before it routes.

## Invariants

- **Untrusted by default** (ADR-0013): `invoke` leaves `ToolResult.trust` at its fail-closed
  `UNTRUSTED` default, so every remote MCP result (file contents, email bodies) is framed as data
  and taints the turn. The adapter needs no per-tool trust annotation. A remote result is re-stamped
  trusted only by the brain's `OwnTextToolRegistry` at the composition root, and only when its whole
  content is byte-equal to text the brain holds in code (`cortex_orchestrator/own_texts.py`),
  rendered with the call's own argument; nothing the sidecar writes, `isError` and `_meta` included,
  is read for it (ADR-0013 decision 10). That overlay's contract runs over this adapter and the fake
  alike (`test_own_text_contract.py`), the image case over both: a result with a picture is never
  the brain's own text, so the exact text beside an image stays untrusted through the real adapter.
  A tool whose every answer should be trusted is a built-in, never a remote overlay.
- Stateless per call: no tool state outlives a call (the one hard rule), and the adapter holds only
  the injected session. Real MCP and network I/O lives here, never in the core.
- Fully typed, pyright strict clean, 100% line and branch over a fake `McpSession` returning real
  `mcp` result types and a scripted session opener (open success, refused dial, anyio
  `ExceptionGroup`, re-dial after recovery, listing-error passthrough). No server, no network. The
  live contract against a real streamable-http MCP server is the `integration`-marked
  `tests/test_registry_live.py`, run per [docs/runbooks/tools-mcp.md](../runbooks/tools-mcp.md).
- Fixed to the MCP SDK v1.x (`mcp>=1.23,<2`); v2 is pre-release. A v2 migration is an adapter-only
  change behind the unchanged `ToolRegistry` port.

**Dependencies.** cortex-core (the `ToolRegistry` and `ToolAuditSink` ports, the tool values,
`ImagePart` and `ImageError`, and the typed errors), mcp (the client SDK) and httpx (the
streamable-http transport, whose connect errors the open path maps). The composition root
(`cortex_orchestrator.wiring`, through `build_tool_registry`) builds one
`ReconnectingMcpToolRegistry(partial(streamable_http_session, url))` per configured endpoint with no
dial at startup, optionally composes the core's `FilteredToolRegistry`, `AggregateToolRegistry` and
`SkipUnavailableToolRegistry` around them (ADR-0009 decisions 8 and 9; this adapter stays
single-server), and wraps the result in an audited `ToolDispatcher`.
