# ADR-0009: Tools via MCP with ToolRegistry + audited dispatch, native function-calling

**Status:** Accepted (2026-09-17)

## Context

The cortex needs to call tools: a filesystem first, then email, and later the body-backed OS
actions. Every call reaches outside the process on the user's behalf, so every call has to be
audited, and every later tool has to go through the same audited path. Tools are reached through
MCP servers, behind one port.

Two existing interfaces frame this. The cortex talks to models through `InferenceBackend`
([ADR-0005](ADR-0005-llamacpp-engine.md), [ADR-0007](ADR-0007-model-manager-inference.md)), and for
a model to call a tool it has to be able to decide to, which a text-only `stream()` cannot express.
And the user reads mail through ProtonMail, so a local ProtonMail Bridge exposing IMAP on the host
is the concrete target for the email tool.

A model that can call tools can also call them too often, call the same one repeatedly, or wait on
a sidecar that never replies. The limits below exist because each of those was possible in the code
before it was closed off.

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
   is asked again, until it answers in text. `MAX_TOOL_STEPS` (8) limits the rounds. The loop's
   working messages stay in the turn: the session store keeps the user turn and the final answer,
   and an escalating turn passes its tool steps in the handoff record
   ([ADR-0030](ADR-0030-brain-handoff.md)).

### MCP adapter and sidecars

4. **The brain is an MCP client through the official `mcp` SDK, at `mcp>=1.23,<2`, hidden behind
   the port.** v2 is a pre-release with a breaking client API. `McpToolRegistry` is a thin adapter
   over a `ClientSession`-shaped port, so CI covers listing, call mapping and error wrapping
   against a fake session. A tool returns one readable string, because FastMCP renders a list or
   dict as per-item content blocks.
5. **Each tool server is its own compose sidecar over streamable-http.** The reference filesystem
   server gets read-only bind mounts of the allowed directories only, and the mount is the security
   boundary: a write tool the server advertises fails with `EROFS`. The version is fixed to a
   release patched against the EscapeRoute sandbox escapes (CVE-2025-53109/53110),
   `@modelcontextprotocol/server-filesystem@2026.1.14` behind `supergateway@3.4.3`, both installed
   once at container start, with the bridge run `--stateful` and `--sessionTimeout` so one child
   serves one MCP session and is stopped with it (`docker/docker-compose.tools.yml`).
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
   optional JSON allowlist; the singular `CORTEX_TOOLS_ENDPOINT` is still valid alone, and setting
   both forms, or an allowlist with no endpoint, fails at startup. `FilteredToolRegistry`
   intersects the advertisement with the allowlist and refuses a name outside it, and only
   restricts. `AggregateToolRegistry` lists registries in sorted endpoint-name order, keeps the
   first of a duplicated name, and routes an invoke by a live listing walk rather than a cached
   table, so a tool a sidecar dropped fails with `ToolNotFoundError`. A listing failure is a
   visible `ToolError` under `CORTEX_TOOLS_ON_UNAVAILABLE=fail` (the default); under `skip`,
   `SkipUnavailableToolRegistry` turns it into an empty advertisement plus a mandatory report,
   logged as a warning on every walk, while an invoke still fails visibly.
9. **A fresh MCP session per call, opened and closed in one task.** `streamable_http_session(url)`
   opens the transport, session and `initialize` for one `async with`, and
   `ReconnectingMcpToolRegistry` opens one per `describe_tools` or `invoke`, mapping an open failure
   (`McpError`, `OSError`, `httpx.HTTPError`, unwrapped from anyio's `ExceptionGroup`) to
   `ToolError`. A held session is not possible behind this port: anyio's cancel scopes are
   task-bound, so closing a session from another task corrupts it, and a refused connection showed
   up as a bare `CancelledError`. `build_tool_registry` is synchronous and connects to nothing, so a
   sidecar down at startup does not fail the build and a recovered one rejoins on the next call. A
   session pool is declined: one open costs a small fraction of a turn's time to first token
   ([readings](../readings/tool-sidecar-calls.md)), and a pool would need a close scope forwarded by
   every combinator, a port change across the core. If the per-call child spawn ever matters, the
   scope for a held session is one tool loop, which runs in one task.
10. **One call on a sidecar is time-limited, by a combinator.** `BoundedToolRegistry`
    (`tool_deadline.py`) limits both operations with `asyncio.timeout` and raises `ToolError` on an
    overrun. It wraps each remote registry innermost, directly around the reconnecting one and
    under the filter and the skip, so it covers the connect and the call and a stuck sidecar is
    skipped exactly as a refused one is. The built-in tools are not wrapped, since
    `spawn_subagents` and `escalate_to_brain` are slow by design. `CORTEX_TOOLS_CALL_TIMEOUT_S`
    defaults to 60 s for both operations; a value at or below zero fails at startup. It limits one
    walk or call, not a turn. Passing `read_timeout_seconds` through the SDK was rejected: it does
    not limit the session open, and it would put deployment policy inside one adapter. Its ordering
    against the delegated run's deadline is
    [ADR-0047](ADR-0047-delegated-run-bound-ordering.md).

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
    loop already dispatched and never predicts usefulness. It counts attempts, so a declined call
    that needs confirmation cannot re-prompt the user more than twice. It is per loop, since it
    limits redundancy against one context and a sibling subagent cannot see this loop's calls.
    `SaliencePolicy.admits` takes the dispatched calls grouped by round. It is on by default;
    `CORTEX_TOOLS_SALIENCE=off` selects `AlwaysSalient`, and `CORTEX_TOOLS_SALIENCE_LIMIT` sets the
    limit, refused below 1 and with no upper bound, since a limit at or above `MAX_TOOL_STEPS`
    simply never binds while the once-per-round clause still holds.
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
    the advertised `ToolSpec` (name, first line of the description cut at
    `MAX_STEP_SUMMARY_CHARS`), never from the model's call, and an unadvertised or refused call
    lights no chip. When a dispatch resolves, `ToolOutcome` reports the tool name and the audit's
    `ok` on its own proto message; a `phase` field on `ToolActivity` was declined as a second way of
    writing the same fact. A subagent's steps reach the spawning stream as activity only.

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
    complete rotation. A Postgres table was rejected because it would tie the audit to the memory
    backend being on.

### Images in a result

19. **An MCP image block is passed into the result, sized from its header.**
    `McpToolRegistry.invoke` puts `ImageContent` into `ToolResult.images`, so the model sees the
    picture and `TaintLedger.opaque` is set ([ADR-0029](ADR-0029-vision-screen-capture.md)).
    `cortex_tools/headers.py` reads the size without decoding: PNG from IHDR, JPEG by a segment walk
    limited to `MAX_JPEG_SEGMENTS` (512) steps with every length at least two bytes and checked
    against the buffer, stopping before scan data, and WebP from its first chunk in all three forms.
    Bad base64, an unrecognized signature, a truncated header, an edge past `MAX_IMAGE_EDGE` or a
    mime type outside `ALLOWED_MIME_TYPES` raise `ImageError`, crossed as `ToolError`. The mime type
    is the sidecar's declaration checked against the allow-list, not against the bytes.

## Consequences

- Every tool call, including every refusal, writes exactly one audit line, and the audit reads turn
  by turn, delegation included, without the task store.
- One turn can make at most 32 priced dispatches however it fans out, at most 16 calls per round
  and at most two identical calls per loop; a declined action that needs confirmation prompts at
  most twice.
- A stuck sidecar fails one call with a `ToolError` the model reads, and under `skip` drops out of
  the advertisement; nothing waits forever on a sidecar.
- A per-call handshake is paid on every describe and invoke. A delegated dispatch walks the
  registry about twice as often as a cortex one, because `ConfirmFreeToolRegistry` re-lists to remove
  the names needing confirmation before it delegates.
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
- **A session pool:** see decision 9.
- **Unknown image dimensions on `ImagePart`, a size declared in `_meta`, or dropping
  `read_media_file` from the allowlist:** the first widens a validated invariant for one adapter,
  the second still drops a plain sidecar's picture, and the third removes an existing capability.

## Related

- Module contracts: [brain-tools](../modules/brain-tools.md),
  [brain-core](../modules/brain-core.md), [brain-orchestrator](../modules/brain-orchestrator.md),
  [brain-email](../modules/brain-email.md).
- Runbooks: [tools-mcp](../runbooks/tools-mcp.md), [email-imap](../runbooks/email-imap.md).
- Readings: [tool sidecar calls](../readings/tool-sidecar-calls.md).
- [ADR-0013](ADR-0013-untrusted-content.md) (untrusted tool content, the block),
  [ADR-0022](ADR-0022-email-write-confirmer.md) (the write confirmer),
  [ADR-0045](ADR-0045-documented-log-lines.md) (the log-sample check and the audit's declared
  names), [ADR-0046](ADR-0046-work-identities-on-log-lines.md) (work identities on log lines),
  [ADR-0047](ADR-0047-delegated-run-bound-ordering.md) (ordering the limits on a delegated run).
