# ADR-0009: Tools via MCP with ToolRegistry + audited dispatch, native function-calling

**Status:** Accepted (2026-09-17)

## Context

The cortex needs to call tools: a filesystem first, then email, and later the body-backed OS
actions. Every call reaches outside the process on the user's behalf, so every call has to be
audited, and every later tool goes through the same audited path, to MCP servers behind one port.
The cortex talks to models through `InferenceBackend` ([ADR-0005](ADR-0005-llamacpp-engine.md),
[ADR-0007](ADR-0007-model-manager-inference.md)), whose text-only `stream()` cannot express a tool
call. A model that can call tools can also call them too often, repeat one call, wait on a sidecar
that never replies, or read more than its context holds, so each of those has a limit below.

## Decision

### Port and loop

1. **One `ToolRegistry` port and one audited `ToolDispatcher` in the pure core.**
   `describe_tools()` lists the tools to advertise (name and JSON-Schema parameters) and
   `invoke(call) -> ToolResult` runs one call. `ToolDispatcher` is the only entry point the turn
   uses: it wraps `invoke`, writes exactly one `ToolInvocation` to a `ToolAuditSink` for every call
   (success, tool error, registry failure or refusal) and returns a typed `ToolResult` the model
   can read. The value types live in `tools.py`, which imports no ports, so `ports_tools.py` can
   depend on them without a cycle. Failures cross the port as `ToolError` or `ToolNotFoundError`.
   `InMemoryToolRegistry`, `RecordingAuditSink` and a contract test cover the port with no server.
2. **Native function-calling through an extended `InferenceBackend`.** `stream` takes a `tools`
   argument and yields `TextChunk | ToolCall`. llama-server honours OpenAI `tools` and `tool_calls`
   with `--jinja` and a tool-capable chat template, and `--jinja` is set in
   `docker/docker-compose.gpu.yml`. `tools=()` yields text only, so the no-tools path is unchanged.
3. **The tool loop is explicit typed code, `stream_tool_loop`, with no framework.** Per round: one
   inference step, then each emitted call is dispatched through `ToolDispatcher`, the assistant
   message with its `tool_calls` and one `Role.TOOL` result per call id are fed back, and the model
   is asked again, until it answers in text. `MAX_TOOL_STEPS` (8) limits the rounds. When the last
   round still ends in calls, the loop dispatches them and asks nothing more, and the turn closes
   with `ROUNDS_SPENT_NOTE`, naming the limit and each tool it ran with its outcome, so the stored
   reply, the memory exchange and `TurnCompleted` hold the text the person saw. The loop's
   working messages stay in the turn: the session store keeps the user turn and the final answer
   with each call's tool name and outcome ([ADR-0074](ADR-0074-replayed-tool-runs.md)), and an
   escalating turn passes its tool steps in the handoff record ([ADR-0030](ADR-0030-brain-handoff.md)).

### MCP adapter and sidecars

4. **The brain is an MCP client through the official `mcp` SDK, at `mcp>=1.23,<2`, hidden behind
   the port.** v2 is a pre-release with a breaking client API. `McpToolRegistry` is a thin adapter
   over a `ClientSession`-shaped port, so CI covers listing, call mapping and error wrapping
   against a fake session. A tool returns one readable string, because FastMCP renders a list or
   dict as per-item content blocks.
5. **Each tool server is its own compose sidecar over streamable-http.** The reference filesystem
   server gets read-only bind mounts of the allowed directories only, and the mount is the security
   boundary: a write tool the server advertises fails with `EROFS`. The server is fixed to
   `@modelcontextprotocol/server-filesystem@2026.1.14`, past the EscapeRoute sandbox escapes
   (CVE-2025-53109/53110), behind `supergateway@4.1.0`, which drops an answer to a request its
   client abandoned where 3.4.3 exited. Both are installed at container start, and the bridge runs
   `--stateful` with `--sessionTimeout`: one child per MCP session, stopped with it (`docker/docker-compose.tools.yml`).
   Every release through 2.0.1 counts the empty text after a final newline as a file's last line,
   so `LastLinesToolRegistry` asks its text reads for one more `tail` line and drops that one.
6. **Email is a thin, purpose-built IMAP MCP server on `imap-tools`, read-only by default.**
   `list_folders`, `search_emails` and `read_email` against the ProtonMail Bridge
   (`host.docker.internal:1143`, STARTTLS, Bridge-issued credentials and its exported certificate
   or a loopback `tls_insecure` escape, all from the environment). The read path is read-only three
   ways: only read tools register, folders open with EXAMINE, and fetches never set Seen.
   `imap-tools` replaced the planned `aioimaplib`, which has no STARTTLS; the sidecar is a separate
   process, so the brain's async model does not apply to it. An HTML-only body is converted to text
   with a stdlib `HTMLParser` (`html.py`), falling back to the raw HTML when the extraction is
   empty. A Bridge that is down or refuses the login fails that call as an audited `is_error`
   result. The one write tool, `send_email`, is opt-in and needs confirmation (ADR-0022).
7. **Opt-in.** `CORTEX_TOOLS_BACKEND` is `none` by default and `mcp` enables tools; `registry=None`
   keeps the turn path unchanged, as `memory=None` does. CI and the no-GPU loop stay tool-free.
8. **Several sidecars compose through port-preserving combinators in the core.**
   `CORTEX_TOOLS_ENDPOINTS__<name>` declares an endpoint and `CORTEX_TOOLS_ALLOW__<name>` an
   optional JSON allowlist; the singular `CORTEX_TOOLS_ENDPOINT` works alone, and setting both
   forms, or an allowlist with no endpoint, fails at startup. `FilteredToolRegistry` intersects the
   advertisement with the allowlist, refuses a name outside it, and only restricts.
   `AggregateToolRegistry` lists registries in sorted endpoint-name order, keeps the first of a
   duplicated name, and routes an invoke by a live listing walk, not a cached table, so a tool a
   sidecar dropped fails with `ToolNotFoundError`. **A sidecar that is down costs a turn its tools,
   never the turn.** Under `CORTEX_TOOLS_ON_UNAVAILABLE=skip`, the default,
   `SkipUnavailableToolRegistry` lists a failing sidecar as empty, logs a warning on every walk and
   notes its name for the listing in progress (`tool_skips.py`), so the turn sends one `forgoing`
   `StatusUpdate` naming each tool server left out. A call to a tool from its last good listing
   while its server is down fails as `SERVER_DOWN_MSG`, not as an unknown tool, and one cut off by
   the server stopping fails as `CUT_OFF_MSG`; both name the server. `fail` instead ends every turn
   before inference ([readings](../readings/store-and-sidecar-outages.md#the-filesystem-sidecar)).
   Skipping only removes tools, and the allowlist, confirmation set and taint rules apply by name to
   what stays; a name two sidecars advertise routes to the second while the first is down.
9. **A fresh MCP session per call, opened and closed in one task.** `streamable_http_session(url)`
   opens the transport, session and `initialize` for one `async with`, and
   `ReconnectingMcpToolRegistry` opens one per `describe_tools` or `invoke`, mapping an open failure
   (`McpError`, `OSError`, `httpx.HTTPError`, unwrapped from anyio's `ExceptionGroup`) to
   `ToolServerDownError`, a `ToolError`. A held session is not possible behind this port: anyio's
   cancel scopes are task-bound, so closing a session from another task corrupts it, and a refused
   connection showed up as a bare `CancelledError`. `build_tool_registry` is synchronous and
   connects to nothing, so a sidecar down at startup does not fail the build and a recovered one
   rejoins on the next call. A session pool is declined: one open costs a small fraction of a turn's
   time to first token ([readings](../readings/tool-sidecar-calls.md)), and a pool would need a
   close scope forwarded by every combinator, a port change across the core.
10. **A sidecar call is time-limited, and a sidecar that overran rests.** `BoundedToolRegistry`
    (`tool_deadline.py`) wraps each remote registry directly around the reconnecting one, under the
    filter and the skip. `CORTEX_TOOLS_CALL_TIMEOUT_S` (60 s) limits a call, connect included, and
    `CORTEX_TOOLS_LIST_TIMEOUT_S` (10 s, lowered to the call bound when above it) a listing; an
    overrun raises `ToolError`, and a value at or below zero fails at startup. After one overrun,
    every listing and call on that sidecar fails at once, unsent, for `CORTEX_TOOLS_RETRY_AFTER_S`
    (120 s), with a text naming the server and telling the model to answer without its tools, so a
    frozen sidecar costs a turn one bound, not one per call. The rest describes a transport, not
    conversation or task state, so the brain process keeps it and a restart costs one more bound.
    No wait is held around a 146 ms listing; its bound limits the silence before the `forgoing`
    status names the server. Built-in tools are not bounded: `spawn_subagents` and
    `escalate_to_brain` are slow by design. SDK `read_timeout_seconds` does not limit the session
    open and would put deployment policy in one adapter, so it is not used.

### Dispatch limits

11. **One priced dispatch budget per turn.** `DispatchBudget` (`tool_budget.py`) holds `limit`,
    `spent` and `closed`, and `charge(cost)` deducts when a call fits and closes the budget
    permanently when it does not, so a later cheaper call cannot slip in behind a refused one and a
    turn's total does not depend on call order. `MAX_TOOL_DISPATCHES` is 32. `ToolCostPolicy` prices
    tools by name, `DEFAULT_TOOL_COST` 1 for the rest and for unadvertised names; only
    `spawn_subagents` is priced by default, at `MAX_TOOL_DISPATCHES // 4`, and `send_email` is not,
    because a human already approves each send. `CORTEX_TOOLS_COSTS__<name>` must lie in
    `1..MAX_TOOL_DISPATCHES`, and the built-in price is merged under the operator's. The prices sit
    on the dispatcher and are never read off a `ToolSpec`, so a sidecar cannot set its own limit.
    The budget is passed on `TurnStamp.budget` (excluded from equality) into spawned subagents, so
    the cortex and every subagent it spawns draw on one pool, first come first served, and a close
    applies to the whole turn. A root caller with no budget, such as the schedule ticker, gets a
    fresh one. `charge` has no `await`, so concurrent subagents cannot overspend it. It is not
    persisted: it limits one turn's reach and dies with the turn.
12. **Salience refuses a call this loop has already made.** `RepeatSalience` (`tool_salience.py`)
    identifies a call by its name and its arguments compared with mapping equality, and admits it at
    most once per round and at most `MAX_IDENTICAL_DISPATCHES` (2) times per loop; two rather than
    one, so a re-read after the turn changed something still runs. The policy reads only what the
    loop already dispatched and never predicts usefulness. Before it, a call identical to one the
    person declined in this loop is refused with `ALREADY_DECLINED_MSG` and no card, whatever the
    policy. It is per loop: it limits redundancy against one context, and a sibling subagent cannot
    see this loop's calls. `SaliencePolicy.admits` takes the calls grouped by round. It is on by
    default; `CORTEX_TOOLS_SALIENCE=off` selects `AlwaysSalient`, and `CORTEX_TOOLS_SALIENCE_LIMIT`
    sets the limit, refused below 1; one at or above `MAX_TOOL_STEPS` never binds.
13. **A round keeps at most `MAX_CALLS_PER_ROUND` calls.** `plan_round` (`tool_round.py`) drops the
    calls a round emits past 16, half the budget, and truncates the assistant message's
    `tool_calls` to match, so the conversation stays well formed and the dropped calls add nothing
    to the context. One overflow slot is kept and refused with a message naming the cap, so the
    model knows its round was cut. The cap counts emitted calls, independent of salience.
14. **Every refusal is the dispatcher's, audited, and checked before confirmation.** The loop
    passes `refusal: DispatchRefusal | None` (round oversized, redundant, budget), whose member
    value is the model-facing message. `_refused_by` checks the overflow slot first, then salience,
    then the budget, so a refusal is charged nothing. All three sit ahead of the taint block and the
    confirmer ([ADR-0013](ADR-0013-untrusted-content.md),
    [ADR-0022](ADR-0022-email-write-confirmer.md)), so no limit can be turned into a flood of
    confirmation cards. A refused call is answered, never dropped from the message list, and after
    the budget closes the loop keeps running so the model can read the refusal and answer. The set
    of tools needing confirmation, the prices and salience travel as one `DispatchPolicy`, and with
    the audit sink as one `DispatchSetup`.

### What the user sees

15. **A chip per running tool, and its outcome.** The loop yields a `ToolStep` just before each
    dispatch of an advertised call; the engine maps it to `ToolActivity(tool_name, summary)`, which
    is ephemeral, never passed through the guardrail, persisted or recorded. Both fields come from
    the advertised `ToolSpec` (name, first line of the description cut at `MAX_STEP_SUMMARY_CHARS`),
    never from the model's call, and an unadvertised or refused call lights no chip. When a dispatch
    resolves, `ToolOutcome` reports the tool name and the audit's `ok` on its own proto message; a
    `phase` field on `ToolActivity` was declined as a second way of writing the same fact. A
    subagent's steps reach the spawning stream as activity only.

### The audit log

16. **One line per dispatch naming the call and the work it was made for.** `LoggingAuditSink`
    writes `tool.invocation` on `cortex.tools.audit` with `tool`, `ok`, `arguments`, `trust`, `at`,
    `result_chars` or `error` (a success logs its size, never its content), and the work identities
    `session_id`, `turn_id`, `task_id`, `item_id` and `call_id`, each left off when the dispatch has
    none. The first group is what was asked for, `call_id` included even when the model wrote it;
    the identities are what the brain knows, copied from the `TurnStamp` the dispatcher overwrites
    before any branch returns, so the model cannot set them. `item_id` is set only by the schedule
    ticker. A subagent's identities come from its stored `SubagentTask` rather than a parameter, so
    a re-read recovers them, and the codec requires each key. The four stamp identities stay four
    fields, since each is independently present or absent. `trust` is the result of the own-text
    overlay, so `ok=True` with `trust=trusted` under `read_email` or `search_emails` is one of the
    two corrections `own_texts.py` applies, recoverable from the same line's `arguments`. The field
    names are [ADR-0046](ADR-0046-work-identities-on-log-lines.md)'s vocabulary.
17. **The line's structure is the brain's, and secrets are withheld at any depth.** Rendering is
    the formatter's (`cortex_core.log_fields`): a value containing whitespace or a quote is
    JSON-quoted, so no model string can open a field; each rendered value is cut at `VALUE_CHARS`
    (2048) with a marker; URL credentials are withheld per value and over the whole line; and
    `withhold_secrets` (`log_secrets.py`) replaces the value under every string key matching
    `SECRET_NAMES`, a case-insensitive substring rule, at any depth in dicts, lists and tuples,
    before anything renders, in both the plain and the packed formatter. A structure too deep to
    walk is withheld whole, and a cycle is left for the encoder to refuse. A logged field that
    counts tokens is named without the marker, so it is not withheld.
18. **The audit can also be kept in a JSON-lines file.** `CORTEX_TOOLS_AUDIT_FILE`, empty by
    default, adds `JsonLinesAuditSink` behind a `TeeAuditSink` that writes the log line first. The
    file keeps no more than the line prints (`durable_value` runs the same secret walk and keeps the
    formatter's rendering whenever it differs from the parsed value), writes one ASCII-escaped
    record per line, opens per record with `O_APPEND` and mode `0600`, and starts a record on a new
    line after a torn one. A failed append is logged as `tool.audit.gap` and never fails the
    dispatch, since the log line was already written. Rotation is the operator's: a `mv` is a
    complete rotation. A Postgres table was rejected: it would tie the audit to the memory backend.

### What a result puts in the prompt

19. **An MCP image block is passed into the result, sized from its header.**
    `McpToolRegistry.invoke` puts `ImageContent` into `ToolResult.images`, so the model sees the
    picture and `TaintLedger.opaque` is set ([ADR-0029](ADR-0029-vision-screen-capture.md)).
    `cortex_tools/headers.py` reads the size without decoding: PNG from IHDR, JPEG by a segment walk
    limited to `MAX_JPEG_SEGMENTS` (512) steps with every length at least two bytes and checked
    against the buffer, stopping before scan data, and WebP from its first chunk in all three forms.
    Bad base64, an unrecognized signature, a truncated header, an edge past `MAX_IMAGE_EDGE` or a
    declared mime type outside `ALLOWED_MIME_TYPES` raise `ImageError`, crossed as `ToolError`.
20. **A result is cut to `MAX_RESULT_CHARS` (6,000) before it enters the prompt.** `cut_result`
    (`tool_round.py`) keeps the head to its last line break in the second half; `RESULT_CUT_NOTE`,
    after the fence, gives both lengths and says to ask for a smaller part (`head` or `tail` of a
    file) or tell the person. 6,000 is 3,640 tokens at a pasted log's 1.65 characters a token; with
    a full plain-English window and the fixed prompt ([ADR-0014](ADR-0014-history-windowing.md)
    decision 4), 2,860 of 16,384 remain to reply. Several cut results can still overflow one turn.

## Consequences

- Every tool call, including every refusal, writes exactly one audit line, and the audit reads turn
  by turn, delegation included, without the task store.
- A turn makes at most 32 priced dispatches however it fans out, 16 calls per round and two
  identical calls per loop; a declined action that needs confirmation prompts at most twice.
- Nothing waits forever on a sidecar, and one that is down or resting drops out of a turn, which says so.
- A per-call handshake is paid on every describe and invoke, and a delegated dispatch walks the
  registry about twice as often, since `ConfirmFreeToolRegistry` re-lists before it delegates.
- Log lines and the audit file contain model-authored text only inside quoted values; a mislabeled
  image reaches the model under the sidecar's label.
- No write tool exists outside ADR-0022's confirmed `send_email`, and the filesystem mount stays
  read-only whatever the server advertises.

## Alternatives rejected

- **Prompt-and-parse tool calls:** fragile and against the model's trained format.
- **A stdio tool server in the brain container:** bundles Node into the image and weakens isolation.
- **Vendoring `mcp-email-server`:** a send path to lock down and hard to cover with tests.
- **A per-round or per-subagent budget share:** a per-round cap multiplies by the round count, and a
  share strands the allowance of subagents that call nothing.
- **Folding schema defaults or canonicalizing arguments for salience:** a schema `default` is
  advisory, so folding it can refuse a legitimate call, and a schema-free canonical form is just
  mapping equality.
- **A final completion with no tools offered:** it costs a completion and can misstate the calls.
- **Unknown image dimensions on `ImagePart`, a size declared in `_meta`, or dropping
  `read_media_file` from the allowlist:** the first widens a validated invariant for one adapter,
  the second still drops a plain sidecar's picture, and the third removes an existing capability.

## Related

- Module contracts [brain-tools](../modules/brain-tools.md), [brain-core](../modules/brain-core.md), [brain-orchestrator](../modules/brain-orchestrator.md), [brain-email](../modules/brain-email.md);
  runbooks [tools-mcp](../runbooks/tools-mcp.md), [email-imap](../runbooks/email-imap.md); readings [tool sidecar calls](../readings/tool-sidecar-calls.md), [tool failure flows](../readings/overlay-tool-failure-flows.md).
- [ADR-0013](ADR-0013-untrusted-content.md) (untrusted tool content, the block), [ADR-0022](ADR-0022-email-write-confirmer.md) (the write confirmer),
  [ADR-0045](ADR-0045-documented-log-lines.md) (the log-sample check and the audit's declared names), [ADR-0046](ADR-0046-work-identities-on-log-lines.md)
  (work identities on log lines), [ADR-0047](ADR-0047-delegated-run-bound-ordering.md) (the call bound against the delegated run's deadline).
