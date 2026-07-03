# ADR-0009: Tools via MCP with ToolRegistry + audited dispatch, native function-calling

- **Status:** Accepted (Slice 6)
- **Date:** 2026-06-29

## Context

Slice 6 gives the cortex hands. It calls tools, starting with a filesystem, then read-only
email, and **every call is audited**. Per the founding arc and AGENTS.md, tools are
reached through **MCP** servers, behind **one port** so every later tool (including the
body-backed OS actions of Slices 9-10) dispatches through the same audited path.

Two existing seams frame this. The cortex talks to models through `InferenceBackend`
(ADR-0005/0007); for a tool to be called, the model must be able to *decide* to call it, which is
a capability the text-only `stream()` cannot express today. And the user uses ProtonMail
with Thunderbird, which means a local **ProtonMail Bridge** exposing IMAP on the host is the
concrete target for the email tool.

## Decision

1. **One `ToolRegistry` port + one audited `ToolDispatcher` use-case in the pure core.**
   `ToolRegistry.describe_tools()` lists the available tools (name + JSON-Schema
   parameters) to advertise to the model; `ToolRegistry.invoke(call) -> ToolResult` runs
   one call. `ToolDispatcher` is the only gateway the turn uses: it wraps `invoke`, writes
   one `ToolInvocation` record to a `ToolAuditSink` for **every** call (success, tool-level
   error, or registry failure), and returns a typed `ToolResult` the model can consume.
   Value types (`ToolSpec`/`ToolCall`/`ToolResult`/`ToolInvocation`) live in `tools.py`,
   which imports no ports, mirroring `memory.py`, so `ports.py` can depend on them without
   a cycle. Failures cross the port as `ToolError`/`ToolNotFoundError`. Fakes
   `InMemoryToolRegistry` + `RecordingAuditSink` and a shared contract test prove the port
   without a server (the ports-before-adapters gate).

2. **Native function-calling via an evolved `InferenceBackend`, not prompt-and-parse.** The
   cortex invokes tools via the model's *trained* tool-calling: `stream` gains a `tools`
   argument and yields `InferenceEvent = TextChunk | ToolCall` instead of raw text.
   llama-server honors OpenAI `tools`/`tool_calls` with `--jinja` + a tool-capable chat
   template (gemma-4 ships one). The rejected alternative (keep the port text-only and
   regex a hand-rolled convention out of the model's text) is fragile and fights the
   model's native format; evolving the port for a genuine new capability is exactly the
   "ports before adapters" rule, not a violation of it. The no-tools path (`tools=()`)
   yields only `TextChunk`, so behavior is preserved.

3. **The tool loop is explicit typed code in `TurnEngine` and uses no framework.** Per turn:
   recall → one inference step → if the model emitted tool calls, dispatch each through
   `ToolDispatcher` (audited), feed the tool-call and result messages back, and re-infer;
   repeat until the model returns a final text answer (streamed live throughout). A
   **max-steps** guard (`MAX_TOOL_STEPS`) bounds the loop. The fed-back context carries the
   native structure (an `ASSISTANT` message with `tool_calls`, then `Role.TOOL` result
   messages keyed by call id), so re-inference is faithful. **v1 keeps this context
   in-turn** (there is no mid-turn swap yet, ADR-0007): only the user turn and the final
   assistant answer are persisted, and the exchange rolls into the single memory record at
   turn end. Persisting the tool steps for mid-swap rehydration lands with the swap slice
   (Slice 11), which teaches the session store their schema.

4. **MCP integration: the brain is an MCP *client* via the official `mcp` SDK, hidden
   behind the port.** Pin `mcp>=1.23,<2` because v2.0 is a pre-release with a breaking Client
   API; the v1.x `ClientSession` is the production surface. The SDK is a thin adapter
   satisfying `ToolRegistry`, injected a `ClientSession`-shaped port so CI covers
   tool-listing, call mapping, and error-wrapping against a **fake session** (the
   `httpx.MockTransport` / canned-row-`Database` analog). A live MCP server is host-only.

5. **Tool servers run as sidecar containers over streamable-http.** Each MCP server is its
   own Compose service; the brain connects over the Compose network. The reference
   filesystem server gets **read-only bind mounts of only the allowed directories** and is
   pinned to a patched version (the EscapeRoute sandbox-escape CVEs, CVE-2025-53109/53110).
   The rejected alternative (a stdio subprocess inside the brain container) bundles Node
   into the Python image and runs the tool server in the brain's own process space (weaker
   isolation). No write tools in v1: only the read-only filesystem tool subset registers.

6. **Email: a thin, purpose-built read-only IMAP MCP server (imap-tools).** Read-only (list
   folders / search / read one message, with **no** send/delete/flag surface), 100%-covered with a
   fake `Mailbox` and a fake imap-tools `MailBox`, pointed at the ProtonMail Bridge
   (`host.docker.internal:1143`, STARTTLS, Bridge-generated per-client credentials + the
   exported self-signed cert or a loopback `tls_insecure` escape hatch, all via env, never in
   the repo). **imap-tools (over stdlib `imaplib`) replaces the originally-planned aioimaplib**:
   aioimaplib has no STARTTLS (the Bridge's default) and the async-native rationale for it does
   not apply, because the email server is a **separate sidecar process**, not the async brain;
   imap-tools also gives cleanly parsed messages. Read-only is enforced three ways: only read
   tools register, folders open with EXAMINE (`readonly=True`), and fetches never set Seen
   (`mark_seen=False`). The rejected alternative (vendoring `ai-zerolab/mcp-email-server`)
   carries a send/write surface to lock down, an external dependency, and resists 100% coverage.

7. **Opt-in, mirroring memory and inference.** `CORTEX_TOOLS_BACKEND` (`none` default, `mcp`
   enables); CI and the no-GPU dev loop stay tool-free. `registry=None` keeps the old turn
   path byte-for-byte, exactly as `memory=None` does.

## Consequences

Increments (each small, green, documented), mirroring Slice 5:

1. **The pure tool-dispatch core** covers the `ToolRegistry` + `ToolAuditSink` ports, the value
   types, the typed errors, the `InMemoryToolRegistry` + `RecordingAuditSink` fakes, and the
   `ToolDispatcher` use-case, fully covered in the core, no MCP.
2. **Native function-calling in the turn.** Evolve `InferenceBackend` to yield
   `InferenceEvent`, add `Role.TOOL` and the `Message` tool fields, the bounded tool loop in
   `TurnEngine` (behind the `TurnCapabilities` bundle), and the llama.cpp adapter's `tools`
   payload + streamed-`tool_calls` reassembly, tested end-to-end over the fakes.
3. **The MCP filesystem adapter** (`mcp` SDK behind the port) + the sidecar Compose service
   with read-only mounts + a runbook. Host-validated.
4. **The thin read-only IMAP email server** + the ProtonMail Bridge wiring + a runbook.
   Host-validated.

Config gains, at the composition root only: `CORTEX_TOOLS_BACKEND`, the MCP endpoint(s), and
the email/Bridge settings. The `--jinja` llama-server flag (engine/deployment, ADR-0005) is
added to the GPU Compose command when the real tool path is validated on the host.

## Risks

- **Filesystem sandbox-escape CVEs** (EscapeRoute). Mitigated by a pinned patched version,
  read-only bind mounts, a minimal allowed-directory set, and auditing every call; the
  container is a second containment layer.
- **MCP SDK v1→v2 churn.** v2 is pre-release; pin v1.x behind the port so a v2 migration is
  an adapter-only change. Do not copy v2 in-memory `Client(mcp)` snippets into production.
- **Model tool-calling reliability.** gemma-4 tool-calling under llama.cpp + `--jinja` is
  validated on the host (integration), not in CI. The loop bounds steps and treats a
  malformed or failed call as an `is_error` `ToolResult` the model can recover from.
- **ProtonMail Bridge coupling.** The brain depends on a host process outside its lifecycle
  (Bridge running, self-signed cert, a rotating per-client password). The adapter degrades
  gracefully (tool unavailable, audited) on auth/transport failure; the coupling lives in
  the runbook.
- **Loop non-termination / tool spam.** Bounded by the max-steps guard; the audit trail
  makes runaway visible. Salience/rate policy is a later refinement behind the port.

## Addendum (2026-06-29): increment 3 host validation

The filesystem sidecar + `McpToolRegistry` were validated on the host machine (WSL +
Docker Desktop). The sidecar is `@modelcontextprotocol/server-filesystem` bridged to
streamable-http by `supergateway` (`--outputTransport streamableHttp --port 9000`, endpoint
`/mcp`), with `./sandbox` bind-mounted read-only at `/projects`. `McpToolRegistry.connect`
opened a real session, `describe_tools()` listed the server's 14 tools, and
`read_text_file` returned the file's contents (`is_error=False`). The integration test
passed.

- **Read-only containment works at the OS level.** `write_file` on the mount returned
  `is_error=True` with `EROFS: read-only file system`. The model *can* call a write tool,
  but the mount blocks it. This is the real security boundary (fork 2), proven end to end.
- **The reference server advertises write tools** (`write_file`, `edit_file`, `move_file`,
  `create_directory`) rather than a read-only subset, so decision 5's "only the read-only
  subset registers" is enforced by the **mount**, not by tool filtering. Filtering the
  advertised set to the read tools (so the model never sees a write tool that will EROFS) is
  a **noted refinement**, behind the unchanged port; the mount makes it a UX nicety, not a
  security need.
- **The read tool is `read_text_file`** on the current server (older builds named it
  `read_file`, still present); the live test's tool name is env-overridable.

## Addendum (2026-06-29): increment 4 host validation

The `cortex_email` sidecar was validated against the user's live **ProtonMail Bridge** (WSL
+ Docker Desktop). WSL cannot reach the Bridge's Windows-loopback IMAP directly, but the
sidecar container reaches it via `host.docker.internal:1143` (STARTTLS, `tls_insecure` on
loopback), as confirmed by the Bridge's IMAP banner. Dogfooding `McpToolRegistry` from WSL
against the sidecar (`http://127.0.0.1:9100/mcp`): `describe_tools()` returned **exactly the
three read-only tools** (no write tool exists), `list_folders` returned **17 real folders**
(INBOX present), `search_emails` returned a well-formed summary line, and `read_email`
returned a real message.

Two refinements landed during validation:

- **Tools return a single readable string, not `list`/`dict`.** FastMCP renders a list/dict
  return as *per-item* content blocks; a text-only MCP client (our `McpToolRegistry`, which
  joins text blocks) then smushes them. Returning one formatted string per tool keeps the
  result clean end to end. Readable text is what the model consumes anyway.
- **`read_email` falls back to `text/html` when there is no `text/plain` part.** Most real
  mail is HTML-only, so plain-only extraction returned empty bodies; the fallback returns the
  HTML source (readable enough for the model). A readable-text-from-HTML extraction is a
  noted refinement. With it, every sampled INBOX message returned a non-empty body.

Read-only is confirmed three ways end to end: only the three read tools are registered,
folders open with EXAMINE (`readonly=True`), and fetches use `mark_seen=False`, so the live
mailbox is never modified.

## Addendum (2026-07-01): the untrusted-content boundary is ADR-0013

Two threads left open here are now owned by [ADR-0013](ADR-0013-untrusted-content.md) (Slice 6.5):
tool-result content re-entering the loop is **untrusted data** (framed, not obeyed), and the deferred
"email write-actions behind explicit per-action confirmation" (the Risks section) is subsumed by
ADR-0013's capability gate (`ToolSpec.gated` + the `Confirmer` port), shipped inert until the first
outbound tool. The tool seams (`ToolRegistry`/`ToolDispatcher`/`stream_tool_loop`) are unchanged; the
boundary is a hardening pass behind them plus that one new port.

## Addendum (2026-06-29): multi-server tool aggregation as a noted refinement

Wiring connects `CORTEX_TOOLS_BACKEND=mcp` to a **single** MCP endpoint, so a running brain
has the filesystem tools *or* the email tools, not both at once. An `AggregateToolRegistry`
satisfying the same `ToolRegistry` port, fanning `describe_tools()` across several
`McpToolRegistry` sessions and routing `invoke(call)` to the owning session by tool name
(with a name-collision policy), lets several sidecars coexist behind the unchanged port and
the same audited `ToolDispatcher`. Deferred: no slice needs both tool families live at once
yet, and the port already admits it without change. Tracked in the ROADMAP deferred-refinements
list alongside the two refinements that *did* land above (readable-string output; HTML-body
fallback) and the advertised-write-tool filtering from the increment-3 addendum.

## Addendum (2026-07-03): `--jinja` committed to the GPU compose; live cortex tool path validated; the version pin made real

Closes the two open ends the 2026-07-02 slice audit flagged (`audit/slice-6.md`, which is a review
artifact removed after remediation; in git history through commit `96463aa`):

- **The Consequences condition is met and the flag is committed.** "`--jinja` … is added to
  the GPU Compose command when the real tool path is validated on the host" had never been
  exercised: increments 3/4 dogfooded `McpToolRegistry` directly and the ADR-0013 probe
  hand-built the tool-call message, so no recorded run showed the cortex *natively* emitting
  a tool call. Validated 2026-07-03 (agent, via Docker): with `--jinja` on the resident
  gemma-4-12B and the filesystem sidecar up, a `Converse` turn asking for a file's contents
  made the model emit a native `read_text_file` call through the full audited loop. The
  MCP sidecar served it, the audit trail logged it (`tool.invocation … "tool":
  "read_text_file", "trust": "untrusted"`), and the reply contained the file's exact
  contents. `--jinja` is now baked into `docker/docker-compose.gpu.yml`.
- **The filesystem-server pin decision 5 asserts now exists in the compose.** The committed
  override had run *unversioned* `npx` (the pin was delegated to an operator comment); it now
  pins `@modelcontextprotocol/server-filesystem@2026.1.14` (EscapeRoute CVE-2025-53109/53110
  were patched in `2025.7.1`; both GitHub advisories confirm) and `supergateway@3.4.3`.
  Validated live: the pinned sidecar passes the tools integration test unchanged.
