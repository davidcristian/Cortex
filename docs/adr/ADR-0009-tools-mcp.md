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

## Addendum (2026-07-03): three deferred refinements land (aggregation, advertised-tool filtering, HTML→text)

The multi-server-aggregation addendum above, the increment-3 advertised-write-tool filtering
note, and the increment-4 readable-text-from-HTML note are now implemented (they were the
Slice 6 entries in the ROADMAP deferred-refinements list). The `ToolRegistry` port, the
audited `ToolDispatcher`, and the MCP adapter are all **unchanged**. The first two land as
pure port-preserving combinators in the core next to `CompositeToolRegistry`, the third as
pure parsing inside the email sidecar.

1. **`AggregateToolRegistry` (core, `aggregate.py`)** satisfies `ToolRegistry` over an
   ordered sequence of registries. `describe_tools` lists each in order and dedups by name
   **first-wins**, matching the shadowing precedence `CompositeToolRegistry` gives built-ins, with
   construction order as the precedence order; a duplicate name from a later registry is
   neither advertised nor routed to. `invoke` routes to the first registry currently
   advertising the name, resolved by a **live `describe_tools()` walk at invoke time**, with no
   cached routing table (nothing to invalidate or rehydrate; a tool dropped server-side
   mid-turn fails closed as `ToolNotFoundError`). A listing failure propagates as `ToolError`:
   one dead sidecar is a loud, audited failure, **not** a silently smaller tool set. A
   partial-degradation policy would be a later knob behind the same port.
2. **`FilteredToolRegistry` (core, same module)** is an allowlist over one registry:
   `describe_tools` intersects the inner advertisement with the allowlist, and `invoke`
   refuses a name outside it (`ToolNotFoundError`) so the filter is a real layer, not
   advisory, even though the read-only mount remains the security boundary (increment-3
   addendum); this closes the UX gap of advertising write tools that can only `EROFS`. The
   filter only *restricts*: an allowlisted name the inner registry does not advertise stays
   unadvertised, and invoking it surfaces the inner registry's own not-found.
3. **Config: one env var per sidecar, merge-friendly.** `CORTEX_TOOLS_ENDPOINTS__<name>=<url>`
   declares an endpoint and `CORTEX_TOOLS_ALLOW__<name>=<JSON name list>` optionally filters
   it (pydantic-settings `env_nested_delimiter="__"`). Compose merges `environment` maps
   key-wise, so layering `docker-compose.tools.yml` **and** `docker-compose.email.yml` now
   yields both sidecars. The singular `CORTEX_TOOLS_ENDPOINT` the two overrides previously
   fought over remains valid for a one-server deployment, but setting both forms is a
   validation error (ambiguity fails closed), as is an `ALLOW__<name>` with no matching
   endpoint. The wiring connects each endpoint, wraps it in `FilteredToolRegistry` when an
   allowlist is set, and aggregates when more than one, with registries ordered by **sorted
   endpoint name**, so collision precedence is deterministic and independent of env
   enumeration order. Sessions are owned by one `AsyncExitStack`; a failed later connect
   unwinds the earlier sessions.
4. **`read_email` HTML→text (email sidecar, `html.py`).** The increment-4 raw-HTML fallback
   now runs through a stdlib-`HTMLParser` extraction: script/style/head content dropped,
   block boundaries become newlines, entities decoded, whitespace collapsed. An extraction
   that comes back empty (e.g. an image-only body) falls back to the raw HTML, preserving
   increment 4's non-empty-body property. No new dependency.

The filesystem sidecar's allowlist (its 10 read tools) lives in `docker-compose.tools.yml`
where the mount it mirrors is declared; the email sidecar needs none (it never had write
tools). Runbook: [tools-mcp.md](../runbooks/tools-mcp.md) covers running both sidecars at
once.

Validated live 2026-07-03 (agent, via Docker, both sidecars up under the layered overrides):
`build_tool_registry` over both endpoints advertised exactly 13 tools, made up of the 10 allowlisted
filesystem read tools (every allowlist name exists on the pinned server; none of the 4 write
tools advertised) plus the 3 email tools; `read_text_file` routed through the aggregate and
returned the sandbox file's contents; `write_file` was refused at the filter
(`ToolNotFoundError`); and with the ProtonMail Bridge down on the host, `list_folders` still
routed to the email sidecar and its failure came back as a clean `is_error` result, which is the
graceful-degradation path of the Risks section, observed end to end.

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

## Addendum (2026-07-03): degraded-mode aggregation lands the skip-and-report knob

The 2026-07-03 refinements addendum left one policy open: `AggregateToolRegistry` fails tool
listing loudly when any one sidecar is down ("a partial-degradation policy would be a later
knob behind the same port"). That knob now exists, as a third port-preserving combinator:

- **`SkipUnavailableToolRegistry(inner, *, name, report)` (core, `aggregate.py`)** marks one
  registry *optional*: a `describe_tools` failure (`ToolError`) becomes an empty advertisement
  plus one `report(name, error)` call. The reporter is a **mandatory** constructor argument, so
  the "never a silently smaller tool set" rule is kept by construction, since the skipping
  behavior cannot be built without the reporting. Degradation is reported on **every** walk
  (the aggregate re-lists per describe and per invoke-routing), so a dead sidecar stays loud
  in the logs for as long as it is dead. Only *discovery* is softened: `invoke` delegates
  untouched, so executing against an unavailable registry still fails loudly, and through the
  aggregate a dead sidecar's tools are simply unadvertised. Calls fail closed as
  `ToolNotFoundError`.
- **Config: `CORTEX_TOOLS_ON_UNAVAILABLE=fail|skip`, default `fail`.** The default keeps the
  original loud behavior; `skip` makes the wiring wrap each endpoint's registry (outside its
  allowlist filter) with the combinator, reporting through a structured `warning` log at the
  composition root (`wiring._report_sidecar_unavailable`, since the core stays log-free/pure; the
  reporter is injected like every other edge concern).
- **Boundary, stated honestly:** the knob covers a sidecar that dies *after* its MCP session
  connected (the listing walk). A sidecar down *at startup* still fails
  `McpToolRegistry.connect` in `build_tool_registry`, skip mode or not. Connect-time
  tolerance plus a reconnect policy is a separate lifecycle refinement, recorded in the
  ROADMAP deferred-refinements list (Slice 6 block).

The `ToolRegistry` port, the audited `ToolDispatcher`, and the MCP adapter remain unchanged.

## Addendum (2026-07-08): connect-time boot tolerance + re-dial retire the eager `connect`

The boundary the degraded-mode addendum stated honestly ("a sidecar down *at startup* still
fails `McpToolRegistry.connect` … connect-time tolerance plus a reconnect policy is a separate
lifecycle refinement") now lands, and the fix forced retiring the held-session `connect`.

**The finding (agent, Docker/uv probe against the real `mcp`/`httpx`/`anyio` stack).** `connect`
held the streamable-http transport + `ClientSession` open on a long-lived `AsyncExitStack` and
returned `stack.aclose` as the shutdown closer. But `streamable_http_client` runs an
`anyio.create_task_group()`, whose cancel scopes are **task-bound**: entering the stack in one task
and closing it from another (composition-root shutdown, or a later turn) raises "Attempted to exit
cancel scope in a different task". Worse, a refused dial at boot surfaced through the stack as a
bare `asyncio.CancelledError` (a `BaseException`), not a catchable transport error, so
skip-mode could never have absorbed it. A **structured, same-task** `async with
streamable_http_client(...) as …: async with ClientSession(...) …:` instead surfaces a refused
dial cleanly as `httpx.ConnectError` inside an anyio `ExceptionGroup`.

**The decision.** Open a **fresh session per call**, structured and same-task, and never hold one
across tasks:

- **`streamable_http_session(url)` (adapter, `registry.py`)** is an `@asynccontextmanager` that
  opens `streamable_http_client` + `ClientSession` + `initialize` for the scope of one
  `async with`. Replaces the `connect` classmethod, now removed.
- **`ReconnectingMcpToolRegistry(opener)` (adapter)** is a `ToolRegistry` that opens a session per
  `describe_tools`/`invoke` from an injected `opener` and maps an open failure
  (`McpError`/`OSError`/`httpx.HTTPError`, unwrapped from the `ExceptionGroup` by `except*`) to
  `ToolError`; a `ToolError` from the live session's own describe/invoke passes through untouched.
- **`build_tool_registry` is now synchronous and dials nothing.** It builds one
  `ReconnectingMcpToolRegistry(partial(streamable_http_session, url))` per endpoint, still wrapping
  each in the allowlist filter and (under `skip`) `SkipUnavailableToolRegistry`, and returns a
  no-op closer (no session is held). No `AsyncExitStack`, no eager connect.

**Both properties fall out.** A sidecar **down at boot no longer fails the build**. It is dialed
on first use, and when down the open fails as `ToolError` that `SkipUnavailableToolRegistry`
reports and serves around. A **recovered sidecar rejoins without a brain restart**, as the next call
re-dials. **Trade-off:** a per-call session open (a localhost handshake per describe/invoke); a
session cache/pool is a later optimization recorded in the ROADMAP, and this paragraph's claim that
it sits behind the unchanged `ToolRegistry` port is **corrected by the handshake addendum below**,
which measured the trade and declined the pool. The port, the audited `ToolDispatcher`, and the core combinators are unchanged;
`httpx` becomes a direct `cortex_tools` dependency (the transport whose connect errors it maps).

## Addendum (2026-07-12): the tool loop emits `ToolActivity` for the overlay chip

The proto has carried `ServerEvent.tool_activity` (`ToolActivity{tool_name, summary}`) since the
seam landed, and the overlay's inline activity chips (the ADR-0011 gap closure) render it, but the
brain never emitted it: every audited dispatch inside `stream_tool_loop` was invisible to the user
mid-turn. This addendum lands the brain half, recorded as deferred at ADR-0022 (the chip's origin)
and closed here (the loop's home). Decisions:

1. **The loop yields a `ToolStep`; the engine maps it.** `stream_tool_loop`'s yield vocabulary
   grows to `str | ReasoningDelta | ToolStep` (frozen: `tool_name`, `summary`), yielded
   immediately *before* each audited `dispatcher.dispatch` so the chip shows while the tool
   runs. The `TurnEngine` maps it onto the new domain event `ToolActivity(tool_name, summary)`
   (the `ReasoningDelta` → `StatusUpdate` precedent, ADR-0020): ephemeral, never fed to the
   output guardrail, never part of `full_text`, never persisted or recorded to memory. The
   orchestrator's `_to_server_event` maps the domain event onto the wire type. The
   `SubagentRunner` keeps only `str` deltas in its joined output, dropping tool steps with
   reasoning: a subagent's loop has no `Converse` stream to ride, and surfacing its progress
   is the standing ADR-0010 deferral.
2. **Both chip fields are registry-authored, never model-authored (post-review hardening).**
   A `ToolStep` is yielded **only for a call that matched an advertised `ToolSpec`**, and it
   carries `spec.name` and `spec.description` (first line, capped at `MAX_STEP_SUMMARY_CHARS`,
   name as the empty-description fallback), never the model's `call.name` or its arguments. An
   unadvertised name (a model hallucination, or a tool skip-mode hid) still dispatches and
   fails as its usual `is_error` result, but renders **no chip**. The first cut rendered
   `call.name` and, for an unadvertised call, used it as the summary too: an adversarial
   review flagged that as exactly the model-writable display channel this event must not open,
   since the model's string is written after it may have read untrusted content and the
   ADR-0015 guardrail scrubbed only reply text at the time (its coverage has since grown to
   the thinking status, ADR-0020 addendum; the registry-authored rule stands on its own, as
   chip fields never pass any filter). Closed by keying the emission (and both fields)
   on the advertised spec.
3. **Start-only, no wire `phase` field.** One event per dispatch; the overlay chip is
   latest-wins and the turn-ending event clears it, which already gives a sensible lifecycle.
   A `phase` on the wire needs a proto field plus both committed stub trees; deferred until a
   design actually needs completion states.
4. **The dispatch rate/salience policy stays a separate deferral** (this ADR's risks; the
   ROADMAP's tools block). Emission is intrinsically bounded (`MAX_TOOL_STEPS` per turn, the
   credit-bounded `Converse` queue), so the chip needed no policy to land; limiting *dispatch*
   is its own design.

CI-gated end to end over the fakes (loop yield-before-dispatch order, engine passthrough, the
registry-authored summary derivation with an unadvertised call surfacing no chip, runner drop,
wire mapping); the overlay half was already browser-validated when the chips landed, and
renders this event with no overlay change.

## Addendum (2026-07-14): the dispatch budget bounds tool spam, which max-steps never did

This ADR's risks claimed loop non-termination and tool spam were "bounded by the max-steps
guard". Half of that was false, and the chip addendum's decision 4 repeated it ("emission is
intrinsically bounded (`MAX_TOOL_STEPS` per turn)"). `MAX_TOOL_STEPS` bounds **inference
rounds**. Within one round `stream_tool_loop` dispatched *every* call the model emitted, with
no cap: one round of 500 `tool_calls` was 500 dispatches, and eight such rounds were 4000, on
the only path that reaches external services. The audit trail made a runaway visible after the
fact; nothing stopped it. This addendum lands the dispatch half of the deferred rate policy.

1. **A per-loop total dispatch budget, counted across rounds.** `MAX_TOOL_DISPATCHES` (32,
   a module constant beside `MAX_TOOL_STEPS`, and configurable per loop via the new
   `ToolLoopContext.dispatch_budget`) caps how many calls one `stream_tool_loop` invocation
   may dispatch in total. A total, not a per-round cap, is the property worth having: a
   per-round cap of *n* still permits `MAX_TOOL_STEPS * n` external calls per turn, so the
   number a user could actually name ("how many tool calls can one turn make?") would still
   be a product of two constants. 32 sits above plausible legitimate use (eight rounds
   averaging four calls) and far below spam.

2. **An over-budget call is still dispatched, refused inside the dispatcher, and audited.**
   The tempting implementation, breaking out of the loop when the count is reached, is wrong
   twice. It would leave the assistant message's `tool_calls` without their matching
   `Role.TOOL` results, so the next round's re-inference sends a malformed conversation (an
   OpenAI-compatible backend requires one tool message per `tool_call_id`); and it would
   produce dispatch refusals that no audit record ever sees, breaking this ADR's "every
   dispatch writes exactly one audit record" contract at exactly the moment the audit trail
   matters most. So the loop passes its decision down as a new `dispatch(..., over_budget=)`
   keyword, mirroring how `gated` is passed: the caller states the fact, the dispatcher owns
   the refusal, its message (`BUDGET_EXHAUSTED_MSG`), and the audit line. The model reads the
   refusal as an ordinary `is_error` result and can wrap up in the rounds that remain.

3. **The budget is checked before the gate, so it cannot be turned into a confirmation flood.**
   Inside `dispatch`, `over_budget` short-circuits ahead of the tainted-turn block and ahead of
   `_confirmed`. Ordering it after would mean a model emitting 500 gated calls put 500
   confirmation prompts in front of the user before the budget refused any of them, which
   turns a spam bound into a denial-of-service on the human. The gate's own semantics are
   untouched: below the budget, the ADR-0022 decision-2 table still decides.

4. **A refused call lights no activity chip.** The guard sits *above* the `ToolStep` yield, so
   a chip still means what it says (a tool is running now). This also makes the chip addendum's
   decision-4 claim true retroactively: chip emission is now genuinely bounded per turn,
   because it is bounded by the budget rather than by a round count that multiplied.

The outer loop deliberately keeps running once the budget is spent, rather than stopping: the
remaining rounds are how the model learns of the refusal and produces a final answer instead of
the empty text a hard stop yields (the `MAX_TOOL_STEPS` exhaustion behavior). Those rounds
dispatch nothing external, so the bound holds.

Remaining behind the same seam: the **salience** half of the deferred policy (which calls
*deserve* dispatching, versus how many), a **per-tool or per-cost budget** (32 filesystem reads
and 32 outbound emails are not the same risk), and the fact that a subagent's loop gets its
**own** fresh budget, so a cortex turn that spawns subagents can still exceed 32 dispatches in
aggregate; a turn-wide budget shared across spawned work needs a counter that outlives one
`stream_tool_loop` invocation.

CI-gated over the fakes: the total counted across rounds, the boundary call, the refusal
audited with the tool never invoked, the ordering ahead of both the taint block and the
confirmer, no chip for a refused call, and the loop's message shape staying well formed.

## Addendum (2026-07-14): tools are priced, because a read and a fan-out are not one unit

The budget addendum above left its own successor open: the budget counts **calls**, so thirty
two filesystem reads and thirty two `spawn_subagents` batches spend it identically, though one
of those is thirty two fan-outs of concurrent model runs. This addendum makes the unit a cost.

1. **A `ToolCostPolicy` prices tools by name; the loop charges the price, not one.**
   `stream_tool_loop` keeps a running `spent` rather than a dispatch count and charges each
   call `dispatcher.cost_of(call.name)`. Everything unpriced costs `DEFAULT_TOOL_COST` (1), so
   with no tool priced the budget is exactly the call count it was, and a deployment opts into
   weighting one tool at a time instead of restating the whole tool set. A price must be
   positive: a zero or negative one would make a tool free to dispatch, so the budget would
   bound nothing on precisely the tool a user cared enough to configure, which is a silent
   hole rather than a visible failure. `MAX_TOOL_DISPATCHES` moved out of `tool_loop.py` to sit
   with the prices in a new `tool_budget.py`: the total and the prices are one currency, and the
   split now reads as what it is, `tool_budget.py` owning how much a loop may *spend* and
   `tool_loop.py` (`MAX_TOOL_STEPS`) how *long* it runs.

2. **The policy lives on the dispatcher, beside the gated-name set, and is never advertised.**
   Both are composition-root declarations *about* tools by name, so neither may be read off a
   `ToolSpec`: a sidecar that advertised its own price would be setting its own spending limit,
   exactly the authority ADR-0022 already denies it over its own gating. Putting it there also
   means the two `ToolLoopContext` builders (the cortex engine, each subagent) needed no new
   parameter: the price rides with the gateway that runs the tool. `cost_of` answers for
   unadvertised names too, at the default rather than free, so a model inventing tool names
   cannot dispatch without limit.

3. **A call that does not fit closes the budget instead of being stepped over.** The
   alternative, refusing only the call that overflows and admitting cheaper ones behind it,
   was rejected twice over: `BUDGET_EXHAUSTED_MSG` tells the model to stop calling tools
   entirely, which a budget that kept admitting small calls would make a lie; and the turn's
   spend would then depend on the order the model happened to emit its calls in, so "what can
   one turn spend?" would stop having one answer. The cost is that a refusal can forfeit up to
   `max_price - 1` unspent units, which is bounded and small.

4. **Only `spawn_subagents` is priced out of the box, and `send_email` deliberately is not.**
   The one wired tool whose single dispatch fans out into a batch of model runs is also the one
   with no confirmation gate in front of it, so it is priced at `MAX_TOOL_DISPATCHES // 4`:
   four delegations a turn, each still a whole batch. Pricing outbound email would be the
   obvious-looking choice and the wrong one, because every send already requires the user's
   out-of-band approval (ADR-0022) and a human saying yes thirty two times is by far the
   tighter bound; a second, weaker bound on the one path that already has a human in it would
   buy nothing. The prices reach the cortex dispatcher and each subagent's, since fan-out is
   what multiplies a cheap-looking call; the ticker's private spawn dispatcher (ADR-0025)
   deliberately gets none, as it dispatches one call directly and never runs a tool loop.

5. **Misconfiguration fails at boot, and pricing one tool cannot silently unprice another.**
   `CORTEX_TOOLS_COSTS__<name>=<int>` is validated to `1..MAX_TOOL_DISPATCHES`: below is free,
   above is permanently unaffordable (the tool never runs, and the first call to it closes the
   turn's budget), and both would surface as puzzling runtime behavior rather than as an error.
   Separately, a nested-dict env key **replaces** the whole mapping, so keeping the built-in
   price as the field's default would have dropped `spawn_subagents` back to one the moment a
   user priced an unrelated filesystem tool. `ToolsConfig.cost_policy` therefore merges the
   built-in prices *under* the user's, and restating one still overrides it.

CI-gated over the fakes, each guard mutation-proven to fail when reverted: an expensive tool
spending its price rather than one, the budget closing to cheaper calls behind a call that did
not fit, an unpriced tool still costing one, the dispatcher pricing from its policy, the
out-of-range boot failure, and the built-in price surviving an unrelated one.

Still remaining behind the same seam: the **salience** half (which calls *deserve* dispatching),
and the **turn-wide** budget spanning spawned subagents, which is unchanged by this addendum,
since pricing a call does not make one counter outlive one `stream_tool_loop` invocation.

## Addendum (2026-07-14): the budget belongs to the turn, not to one loop

Both addenda above sold the same property: one number answers "how many external calls can one
turn make?". Delegation made that false, and the budget addendum's own closing paragraph named
the hole without sizing it. `stream_tool_loop` kept `spent` as a **local**, and
`SubagentRunner._run_placed` builds a **fresh** `ToolLoopContext` per task, so every subagent
started at zero. The real arithmetic was worse than "32 plus 32 per subagent", because
`spawn_subagents` takes an unbounded `instructions` array: four batches (all the cost addendum's
price of `MAX_TOOL_DISPATCHES // 4` allows) of fifty subagents each was **6400** dispatches for a
spend of 32, on the only path that reaches external services. The price bought a bounded number
of *batches* and an unbounded number of *calls*. This addendum makes the budget one pool per
turn.

1. **The budget becomes an object that outlives a loop invocation.** `DispatchBudget`
   (`tool_budget.py`, beside the prices it is spent at) replaces the `int` on
   `ToolLoopContext.dispatch_budget` with a mutable handle carrying `limit`, `spent`, and
   `closed`, and one method: `charge(cost) -> bool`, which spends when the call fits and
   permanently closes when it does not. That folds the loop's two locals (`spent` and
   `budget_closed`) into the budget itself, so the cost addendum's decision 3 ("a call that does
   not fit closes the budget instead of being stepped over") is now a property of the budget
   rather than a rule each loop has to re-implement identically. A caller that passes no budget
   gets its own at `MAX_TOOL_DISPATCHES`, which is exactly the old per-loop behavior, so a root
   caller needs no wiring.

2. **It reaches spawned work on the `TurnStamp`, the channel that already exists.** The stamp is
   built fresh per dispatch by the loop and overwritten by the dispatcher (ADR-0018/0027), and it
   is already how `spawn_subagents` learns the spawning turn's taint. Adding a `budget` field
   there means no new `dispatch()` keyword, no second channel on `ToolCall`, and no call site
   changed: `SpawnSubagentsTool.invoke` reads `call.stamp.budget` and hands it to
   `SubagentRunner.run`, which puts it on the subagent's context. This is the stamp's **first
   non-provenance field**, and the widening is deliberate: the stamp's criterion is what the
   dispatching turn hands to work that this call spawns, which `tainted` already satisfies twice
   over (it is provenance *and* the input to the ADR-0017 model pin). The alternative,
   parallel keywords on `dispatch` and a second field on `ToolCall`, is precisely what the stamp
   was introduced to avoid. Because the handle is shared mutable state and a stamp is a value,
   the field is excluded from the stamp's equality (`compare=False`): two dispatches of the same
   turn still compare equal, and a caller cannot accidentally assert one pool equals another.

3. **One pool, first come first served, not a per-subagent share.** Dividing the remainder
   (`remaining // len(tasks)`) was rejected: it has to guess how many of a batch will call tools
   at all, so it strands the allowance of every subagent that answers from its instruction alone,
   and it reintroduces exactly the arithmetic this addendum removes (the answer becomes a
   function of the fan-out again). Starvation under one pool degrades an answer without breaching
   the bound, and it is visible: a starved subagent reads `BUDGET_EXHAUSTED_MSG` and reports
   stopping short to the cortex, which reports it to the user.

4. **Closure is turn-wide too.** A subagent whose call does not fit closes the pool for its
   concurrent siblings **and** for the cortex's remaining rounds. That is decision 3 of the cost
   addendum at the turn's scale, and it keeps the refusal message honest: "this turn has reached
   its limit" would be a lie if the cortex could keep dispatching after a subagent read it.

5. **`spawn_subagents` keeps its price, because the two bounds count different things.** The
   budget counts **dispatches**; a subagent that calls no tools spends nothing from the pool
   while still costing an admission slot, a placement, and a whole model run. So the batch price
   stays the only bound on delegation fan-out, and it is not made redundant by the shared pool.
   Neither bound alone is sufficient: without the price, one turn could spawn unbounded model
   runs that each dispatch nothing; without the pool, four priced batches could dispatch without
   limit.

6. **A root caller without a budget gets a fresh one.** The ticker (ADR-0025) dispatches one
   `spawn_subagents` call directly and runs no tool loop, so its stamp carries no budget and the
   fired subagent gets its own allowance, unchanged from today. A fire is its own root, like a
   turn; if one ever needs a tighter cap it passes a `DispatchBudget` on its stamp and nothing
   else moves.

Concurrency is not a hazard here even though a batch runs under `asyncio.gather`: `charge` is
synchronous and contains no `await`, so on the single-threaded event loop no two charges can
interleave, and the pool cannot be overspent by a race. Nothing about the budget is persisted,
which is deliberate under the one hard rule: it bounds one turn's reach and dies with the turn,
so a model swap mid-turn costs at most a re-derived allowance and never a stuck one.

CI-gated over the fakes, each guard mutation-proven: the pool shared across two loops, a
subagent's spend visible to the cortex loop that spawned it, a subagent closing the pool for its
sibling, the stamp carrying the handle to the spawn tool, the runner falling back to its own
budget when handed none, and the stamp's equality ignoring the handle.

Still remaining behind the same seam: a **fair-share policy** if one greedy subagent starving its
siblings ever shows up in practice. The **salience** half (which calls *deserve* dispatching)
was closed 2026-07-14 by the addendum below, per loop rather than per turn, which is the opposite
scoping to this pool and for a reason this addendum makes visible: reach is a shared resource,
while redundancy is a property of one context. The **unbounded batch size** of `spawn_subagents`
this addendum left open (bounded in
dispatches, unbounded in model runs) was closed 2026-07-14 by the per-call cap in the
[ADR-0010 batch-cap addendum](ADR-0010-subagents.md), as predicted a spawn-tool decision rather
than a budget one: no pool grew a second currency.

## Addendum (2026-07-14): salience refuses a call this loop has already made

The three addenda above bound how *many* external calls a turn may make and how *much* each one
costs. None of them asks whether a call is worth making at all, which is decision 3's open half
and the last of this ADR's risks ("Salience/rate policy is a later refinement behind the port").
`stream_tool_loop` dispatched every call the model emitted, repeats included, so three
independent wastes were bounded only by the pool of 32:

- **The same call twice in one round.** The model chooses every call in a round before seeing
  any of that round's results, so an identical twin in the same `tool_calls` array cannot
  possibly learn anything the first did not. It was two round trips for one answer.
- **The same call every round.** A model that re-emitted `read_file(path=X)` after reading its
  result spent a dispatch per round on an answer already sitting in its own context.
- **A declined gated call, retried.** This is the one that mattered. The gate consults the
  `Confirmer` per dispatch, so a model that re-emitted a declined `send_email` re-asked, and the
  budget was the only thing stopping it: **up to 32 approval cards** for one refused action, each
  one a real interruption. `send_email` is deliberately unpriced (the cost addendum), so nothing
  made those retries expensive.

1. **"Deserve" is answered from what this loop has already done, never from a prediction of
   usefulness.** The tempting reading of decision 3, a policy that judges whether a call will
   help, is rejected outright: that is precisely the model's job, and a pure core that guesses it
   is a model judgment smuggled into deterministic code where it can neither be right nor be
   corrected. The one thing the core knows with certainty is the set of calls it has already
   dispatched, so that is the only thing the policy is allowed to read.

2. **A call runs at most once per round and at most twice per loop.** `RepeatSalience`
   (`tool_salience.py`), with identity taken as the call's `name` plus its `arguments`. The two
   clauses read as one sentence but answer different questions. Within a round there is **no**
   legitimate identical repeat, by the argument above, so the first clause is absolute. Across
   rounds a repeat is legitimate, because the model saw a result and chose again: it may be
   retrying a call that failed transiently, or re-observing something the turn itself changed
   (`list_scheduled` after a `schedule_task`). The second clause allows exactly one such repeat
   and calls the third identical attempt spinning.

3. **The limit is two rather than one, chosen on which failure is benign.** A limit of one
   **denies information**: the re-read after a write returns the stale listing and the model
   answers from it. A limit of two **wastes one dispatch** out of 32. Preferring the benign
   failure is the same asymmetry the ADR-0025 monthly clamp chose (an irregularity moves an
   occurrence and never deletes one), and it is the reason this policy is a cap rather than a
   prohibition.

4. **Attempts are counted, not answers.** An earlier draft recorded only dispatches that came
   back without `is_error`, reasoning that a call with no answer is worth asking again. That is
   wrong in exactly the case this addendum exists for: a gate denial and a declined confirmation
   are both `is_error` results, so the declined `send_email` would never have been recorded and
   the card spam would have survived the policy untouched. Counting attempts also removes any
   inspection of the result, so the loop records a call when it hands it to the dispatcher and
   the rule holds uniformly over successes, tool errors, gate denials, and declined
   confirmations. The refusal message says the call has already run, which stays true whatever
   it returned.

5. **A refused call is refused by the dispatcher, audited, never silently dropped**, exactly as
   an over-budget call is. It is checked **before** the budget is charged, so a repeat costs
   nothing (the cost addendum's "a refused call is charged nothing", applied to the second
   reason); charging the pool for a call that reaches nothing would spend the turn's reach on the
   model's own repetition. The consequence is deliberate: once the pool has closed, a redundant
   call reports redundancy rather than exhaustion, which is the less useful of two true
   statements and the price of not charging it. And like the budget it sits **ahead of the
   gate**, because a bound that runs after the confirmer is not a bound on confirmation prompts
   at all. That ordering is what turns "up to 32 cards" into "at most two".

6. **`over_budget: bool` becomes `refusal: DispatchRefusal | None`.** A second boolean meaning
   "refuse this and tell the model why" is the parallel-keyword shape the turn-wide addendum
   already rejected once for the stamp. The enum's value **is** the model-facing message, so a
   third reason cannot be added without writing one, and `dispatch` keeps one refusal branch
   however many reasons appear.

7. **Per loop, not per turn, which is the opposite of the budget and deliberately so.** The
   budget bounds **reach**, a resource the whole turn shares, so it is one pool riding the
   `TurnStamp` into spawned work. Salience bounds **redundancy against a context**: the loop
   refuses a repeat because the answer is already in *its own* `working` messages. A subagent
   holds a different message list and cannot see a sibling's result, so a sibling's read must
   never refuse mine. This needs no enforcement to hold: the counted calls are a local of
   `stream_tool_loop` and the policy itself is stateless, so per-loop scoping is what the shape
   already gives.

8. **The seam takes the dispatched calls grouped by round, not flat.** `SaliencePolicy.admits`
   receives a sequence of rounds, the last being the one in progress. A flat list would satisfy
   `RepeatSalience`'s second clause and make the first impossible, and the round boundary cannot
   be recovered afterwards. Designing the seam to carry it is cheaper now than reshaping the port
   later, which is the cost correction this repo keeps having to make.

9. **The policy defaults on.** `AlwaysSalient` (`CORTEX_TOOLS_SALIENCE=off`) restores the
   pre-policy behavior exactly, for a deployment that wants it. But `repeat` is the default,
   because this is a bound and both existing bounds (`MAX_TOOL_STEPS`, the dispatch budget)
   shipped on: a bound that ships off protects nobody, and its escape hatch is the knob.

10. **`gated_names`, `costs`, and `salience` become one `DispatchPolicy`.** Forced, not chosen:
    ruff's `max-args = 6` put `ToolDispatcher.__init__` and `build_cortex_tools` both exactly at
    the ceiling, so a third declaration could not be a seventh parameter. Bundling only the two
    cheapest would have left the ceiling reached again on the next one, so all three move,
    which is also the honest grouping: each is a composition-root declaration about dispatching
    that no sidecar may claim for itself, an argument the gated set and the prices already made
    in their own comments. Behavior preserving, keyword-only, and defaulted, so the construction
    sites that declare nothing are untouched.

The complexity gate is what shaped the loop's own diff: adding the second bound put
`stream_tool_loop` over ruff's branch and cyclomatic limits, so the decision moved into a named
`_refused_by(call, dispatcher, dispatched, budget)`. That is a better home for it anyway, since
the ordering between the two bounds is behavior (both calls have side effects) and now has one
docstring rather than a comment block inside a `for`.

CI-gated at 100% line and branch over the fakes, with twelve guards mutation-proven: reverting
each individually turns a distinct test red (the same-round clause, the per-loop cap and its
exact number, the empty-history guard, the non-positive-limit rejection, argument identity, the
salience-before-budget ordering, recording attempts rather than answers, the suppressed activity
chip, per-loop rather than shared history, the dispatcher's refusal branch, the policy freezing
its gate set, and the config knob). The counterfactual is asserted as a pair: the fixture whose
forty repeats cost a pool of two under the default policy spends and closes that same pool under
`ALWAYS_SALIENT`, so the saving cannot be an artifact of the fixture.

Still remaining behind the same seam:
- **Argument identity is structural**, so two spellings of one intent (`a.txt` versus
  `./a.txt`, an added default-valued key) are two different calls. Normalizing per tool would
  need the advertised parameter schema at the policy, which the seam does not carry; the
  direction is at least the safe one, since an unrecognized repeat is dispatched rather than an
  unrelated call refused.
- **A per-round cap on distinct calls.** One round may still emit unboundedly many *different*
  calls, each appending a result or a refusal to `working`. Salience does not change that and
  neither did the budget, which refuses past 32 but still appends. Naming it here because it is
  the one shape both bounds leave open, and it is a context-growth problem rather than a reach
  problem.
- **A limit knob** (`CORTEX_TOOLS_SALIENCE_LIMIT`) if two ever proves wrong for a real
  deployment; the policy already takes the number, so this is config, not design.
- **Cross-loop salience** for a batch of subagents handed the same instruction. Deliberately not
  shared today (decision 7), and it would need a different justification than this policy's,
  since the argument here is "the answer is already in your context" and a sibling's is not.


## Addendum (2026-07-16): a per-round cap bounds the one shape neither the pool nor salience closes

The salience addendum named the last shape both the dispatch budget and salience leave open:
one round may emit unboundedly many *different* calls, and every one of them appends a
`Role.TOOL` message to `working` whether it ran, was refused as a repeat, or was refused past a
closed pool. So the loop's context could still grow without bound at a cost of one dispatch (when
the calls were identical, salience refuses the twins) or of nothing at all (once the pool has
closed, the budget refuses each call and still appends its refusal). This addendum lands the cap.
The entry, this ADR, and the deferred-refinements index all had the diagnosis right for once,
which the index notes explicitly: it is a **context-growth** problem, not a reach one.

1. **The cap drops calls, it does not refuse them.** A cap on the calls a round may *dispatch*
   would have bounded nothing here, because the refusal is appended to the context exactly as a
   result is: 200 refusals grow `working` as much as 200 results. So `plan_round` (a new pure-core
   `tool_round.py`) **drops** the calls a round emits past `MAX_CALLS_PER_ROUND`, and the
   assistant message's own `tool_calls` are truncated to match, so the conversation stays well
   formed (an OpenAI-compatible backend requires one `Role.TOOL` answer per `tool_call_id`, the
   same invariant the budget addendum's refusals exist to preserve). The dropped calls append
   nothing at all: not refused, not audited, not answered.

2. **One overflow slot is kept and refused, so the truncation is observable.** The round is cut
   to the cap **plus one** slot, and that slot is refused as `ROUND_OVERSIZED_MSG`. A silent
   truncation is the one boundary behaviour a cap must not have: a model that cannot tell its
   round was cut re-emits the dropped calls every round until `MAX_TOOL_STEPS` runs out. The
   message names the cap (as the ADR-0010 batch-cap error does, so the bound is one the model can
   restate and obey) and invites the next reply rather than ending tool use, since the dropped
   calls may be work the turn still needs. Three alternatives were rejected: refusing the whole
   round (drops work the model may still need, and grows the context by a refusal per call, which
   is the growth being bounded); truncating silently (the retry-forever failure); and returning a
   refusal result per excess call (bounds the reach the pool already bounds, not the growth).

3. **"Distinct" means calls *emitted*, not distinct names or `(name, arguments)` pairs.** Context
   growth is driven by emission regardless of identity: a round of 200 identical calls still
   appended 201 messages even though salience let exactly one through to a tool. So the cap counts
   emitted calls, which makes it independent of the still-deferred *structural argument identity*
   refinement by construction: it needs no notion of when two spellings are one call, because it
   never asks whether two calls are the same, only how many were emitted.

4. **The cap is `MAX_CALLS_PER_ROUND` (16), half of `MAX_TOOL_DISPATCHES`.** A model chooses a
   round's calls before seeing any of that round's results, so a blind burst that could spend the
   whole turn's reach in one breath is strictly worse than one that must stop and read halfway;
   half the pool means two rounds at the cap exhaust the default budget. Sixteen is also four
   times the "eight rounds averaging four calls" the pool was sized against, so a legitimate
   fan-out fits without truncation.

5. **The overflow slot is refused ahead of every other bound, charged nothing, and lights no
   chip.** It reaches nothing, so charging the turn's pool for it or counting it against this
   loop's repeat history would both be wrong for the reason salience precedes the budget: a
   refusal spends no reach. `_refused_by` checks it first, then salience, then the budget. Like
   both other refusals it rides the dispatcher's machinery (dispatcher-issued as a new
   `DispatchRefusal.ROUND_OVERSIZED`, audited, model-visible), and sits above the `ToolStep`
   yield, so a chip still means a tool is running now.

`tool_round.py` also takes ownership of the two functions that build a round's appended messages
(`call_message`, `result_message`, moved from `tool_loop.py`), because the cap is a cap on
exactly those: how wide a round's footprint in the context may be, and what that footprint is made
of, are one responsibility, and `call_message` must be handed the **plan's** calls so a recorded
call is always answered.

CI-gated at 100% line and branch over the fakes, the pure arithmetic tested with no I/O in
`test_tool_round.py` and the loop's use of it through `stream_tool_loop`. Mutation-proven:
reverting each guard individually turns a distinct test red (the truncation itself, the kept
overflow slot, the exact boundary at the cap, the overflow flag pointing at the right slot, the
slot's refusal, its ordering ahead of the budget, and the assistant message's truncation).
Live-validated on the host 2026-07-16: a real Qwen3.5-4B on the GPU, asked over the reference
filesystem MCP sidecar to read more files than the cap in a single reply, emitted an oversized
round (25 calls); the loop ran the cap's worth, refused the one overflow slot, and the model read
the refusal and fetched the remaining files over two further rounds, exactly the recovery the
observable-refusal decision is for. With the cap raised out of the way the same model and prompt
produced one 25-call round, confirming the shape was real and not an artifact of the harness.

Nothing remains behind this cap. The adjacent refinements (structural argument identity, the
salience limit knob, cross-loop salience, all in the salience addendum's remaining list) are
untouched by it.

## Addendum (2026-07-16): structural argument identity in salience is declined, its threat already bounded

The salience addendum's first remaining item read "argument identity is structural", so two
spellings of one intent (`a.txt` versus `./a.txt`, an added default-valued key) are two different
calls, and the deferred-refinements index predicted the fix "needs the advertised parameter
schema at the policy". That index also warns that this very area misdiagnosed its own cost
before, so the entry was read against the code first. It is declined, on the merits, on four
findings.

1. **The evasion the index named is already closed.** `RepeatSalience` identifies a call by
   `_asks_the_same`: same `name`, and `arguments` compared with `Mapping.__eq__`. Python mapping
   equality is deep and key-order-independent at every nesting level, so permuted keys (top level
   and nested alike) already collapse to one call, JSON whitespace never survives into the parsed
   `arguments` mapping, and Python-equal scalars (`1` and `1.0`, `True` and `1`) already collapse
   too. A test pins the load-bearing half (`test_arguments_compare_structurally_rather_than_by_key_order`):
   reverting `_asks_the_same` to a naive `json.dumps` without `sort_keys` turns it red. That same
   experiment shows the shape a schema-free "canonicalization" would most naturally take is a
   **regression** rather than an improvement, since unsorted serialization reopens the permuted-key
   case and even sorted serialization splits `1` from `1.0` that equality collapses.

2. **A schema-free canonical form closes nothing the equality does not.** Recursively sorting
   object keys and comparing yields exactly the relation `Mapping.__eq__` already computes
   (order-insensitive for objects, order-sensitive for arrays, which is correct, since a list
   argument's order can be semantic). So the cheaper of the two directions the index posed is not
   merely unnecessary, it is a no-op carrying a regression risk, and it is rejected.

3. **The cases a schema would close are unsound to close and reverse this policy's chosen
   direction.** The only genuinely open cases are value spelling (`a.txt` versus `./a.txt`), a
   present-versus-omitted defaulted optional, and a cross-type scalar (`1` versus `"1"`). Value
   spelling needs per-tool domain semantics (a path normalizer), which is the model judgment
   decision 1 of the salience addendum rejected outright, and no parameter schema supplies it.
   Folding a defaulted optional is the one case the advertised schema seems to enable, but JSON
   Schema `default` is advisory documentation, not applied behaviour: a tool is free to treat an
   absent key differently from an explicit default, so folding "omitted" onto "the schema's
   default" can collapse two calls the tool would run differently, and the collapse **refuses a
   legitimate call**. That is the non-benign failure decision 3 deliberately steered away from ("a
   limit of two wastes one dispatch; a limit of one denies information"), reached now by a
   false-positive identity rather than a tight cap. The safe direction the entry itself named (an
   unrecognized repeat is dispatched, never an unrelated call refused) is a reason to keep the
   identity conservative, not to widen it.

4. **The residual the conservative identity leaves is already bounded twice over.** Not collapsing
   two semantically-equal spellings costs at most a few extra dispatches, and those are capped by
   `MAX_TOOL_DISPATCHES` (32 per turn) and `MAX_CALLS_PER_ROUND` (16 per round) whatever the
   spellings are. The one consequence that mattered in the salience addendum, a declined gated call
   re-prompting the user, is bounded independently of identity: a gated call on a **tainted** turn
   is denied outright with no card at all (so injected content produces zero confirmation prompts
   however it permutes arguments), and on an untainted turn the shared budget caps total dispatches
   at 32. So the worst structural-identity evasion turns "at most two cards" into "at most the
   budget's worth" for one action on a user's own untainted turn, a bounded UX degradation by a
   confused (not attacker) model, never an unbounded flood and never a boundary breach.

**Coherence with the round cap.** The round-cap addendum read "distinct" as *calls emitted*,
explicitly independent of argument identity: it never asks whether two calls are the same, only
how many were emitted, so it cannot disagree with salience about identity. Declining to widen
salience's identity keeps that independence intact. Context growth stays bounded by the round cap
and by the budget regardless of spelling, redundancy stays bounded by the conservative structural
identity, and neither bound consults the other.

**No code change.** The `SaliencePolicy.admits(call, dispatched)` seam is unchanged, no `ToolSpec`
is threaded to the policy, and the entry stays verbatim in the deferred-refinements area doc as
the historical record, annotated with this outcome and moved to its dead-until-a-real-gap list. It
reopens only if a real wired tool exhibits a semantic-equivalence evasion that the budget, the
round cap, and the tainted-turn block do not already bound, and even then the sound form is a
per-tool domain normalizer (the rejected model judgment), not schema-`default` folding.

## Addendum (2026-08-08): the per-call session open, measured, and the pool declined

**Status:** accepted. The boot-tolerance addendum above traded a per-call session open for
robustness and priced it in adjectives ("a localhost handshake per describe/invoke", which the
deferred-refinements entry then called acceptable at personal scale). Nothing had put a number on
it, on a budget where a user-facing recall default moved the same week on 0.515 s of time to first
token and a recalling turn takes about 4.6 s to its first token in total. So it was measured.

**How many opens a turn pays** is deterministic, and it is more than the addendum said. With N
configured endpoints and the called tool owned by the k-th in the config's sorted-name order:

| what the turn does | cortex stack | subagent stack |
| --- | --- | --- |
| advertise the tool set (once per loop, before the first token) | N | N |
| one dispatch | k + 1 | N + k + 1 |

The extra walks are deliberate and this ADR's own combinators own them: `AggregateToolRegistry`
routes an invoke by re-listing each registry until one claims the name, and `UngatedToolRegistry`
(ADR-0013) re-lists to recompute the gated set before delegating, both live so that a tool a
sidecar dropped or re-flagged fails closed rather than routing stale. What no document recorded is
the consequence, that a **delegated dispatch costs twice a cortex one**.
`packages/orchestrator/tests/test_mcp_handshake_live.py` now asserts every cell of that table
against the shipped registry stack by counting opens through a wrapping opener, and it is
mutation-proven: deleting the ungated re-walk turns it red at `assert 1 == 2`.

**What one open costs: 17.8 ms** (n=30, 16.5 to 21.5), measured against a control server on the
FastMCP streamable-http transport `cortex_email` itself serves
(`FastMCP(...).run(transport="streamable-http")`, two trivial tools). A control rather than the
email sidecar because the email sidecar needs Bridge credentials and does IMAP work, and the
number wanted here is the transport's floor: what the client and the protocol cost when the
server on the far end does nothing on connect. That is 0.4% of a recalling turn's time to first
token. **The pool is declined on that number**, and on two findings behind it.

**The first is that the expensive sidecar was not expensive because of the handshake.** The
reference filesystem sidecar answered the same open in 565 ms and a fresh-session dispatch in
1740 ms, a quarter of the whole TTFT budget spent before a token. Tracing every HTTP request
showed each JSON-RPC round trip taking 3 to 5 ms and the remainder going to `supergateway`
spawning a fresh `npx @modelcontextprotocol/server-filesystem` child **per request**, about 420 ms
of it npx resolving the pinned package again, and never reaping it: a few hundred calls left 1452
live server processes holding 20.5 GiB. Installing both pinned packages once at container start
and running the bridge `--stateful` (one child per MCP session, killed when the client ends it,
`--sessionTimeout` reaping a session abandoned without that goodbye) took the pre-token walk from
1156 ms to 146 ms and a dispatch from 1740 ms to 154 ms, left one process and 110 MiB after the
same run, and changed no brain code. A pool would have issued fewer requests and fixed none of
that. The change is in `docker/docker-compose.tools.yml`; the runbook carries the numbers.

**The second is that a pool cannot sit behind the unchanged port**, contrary to the boot-tolerance
addendum's trade-off line, which this addendum corrects. A held session must be closed; closing
needs an explicit scope; a scope is a new `ToolRegistry` method that all seven combinators
(`Aggregate`, `Filtered`, `Gated`, `SkipUnavailable`, `Ungated`, `Composite`, `Sighted`) would
forward. Without one, the session is closed by a task other than the one that opened it, which is
precisely the anyio cancel-scope corruption the per-call open was adopted to escape, and boot
tolerance would have to be rebuilt on the far side of it. That is a port change across the core
seam, bought for 17.8 ms.

**One correction to the request count.** A fresh session's `invoke` issues three JSON-RPC calls,
not one: `initialize`, `tools/call`, and a `tools/list` the MCP SDK's `call_tool` makes to cache
tool output schemas per session, which a per-call session can never reuse. `describe_tools` issues
two. The addendum above undercounted by one and two respectively.

**What reopens it.** After the sidecar fix each call still pays that sidecar's own child spawn,
about 125 ms, and only a held session removes it (the same calls on a warm session measure 4.4 ms
and 3.8 ms). If a deployment ever makes that bite, the honest scope for a pooled session is **one
tool loop**, which runs in exactly one task and so is same-task by construction, and the price of
admission is the port change above. Nothing else was opened behind this.


## Addendum (2026-08-18): the salience limit becomes a knob, without becoming a ceiling

The salience addendum's remaining list named `CORTEX_TOOLS_SALIENCE_LIMIT` "if two ever proves
wrong for a real deployment; the policy already takes the number, so this is config, not design".
That reading still held when this landed: `RepeatSalience.limit` has been a defaulted field since
the policy shipped, `__post_init__` has always rejected a non-positive one, and the core suite
already contract-tested a tighter limit. What was missing was only the wire from env to that
parameter, and the escape hatch a deployment actually had was binary: `repeat` or `off`, where
`off` deletes the bound entirely. So a deployment could say "two" or "unbounded" and nothing in
between.

1. **The knob is a lower half only.** `ToolsConfig.salience_limit` defaults to
   `MAX_IDENTICAL_DISPATCHES` and `salience_policy` builds `RepeatSalience(limit=...)` from it.
   A value below 1 fails at boot with `CORTEX_TOOLS_SALIENCE_LIMIT must be positive`, restating
   the core's own rejection where the operator who typed the number is still watching rather than
   at the first property read.
2. **There is deliberately no ceiling**, which is where this diverges from the price knob beside
   it. `CORTEX_TOOLS_COSTS` is bounded `1..MAX_TOOL_DISPATCHES` at both ends because both ends
   hide: free stops bounding the tool, unaffordable means it never runs. A large salience limit
   hides nothing. An identical call can be dispatched at most once per round and a loop runs at
   most `MAX_TOOL_STEPS` rounds, so any limit at or above that number simply never binds: a knob
   doing nothing, not a hole. More to the point, a large limit still says something `off` does not,
   because the once-per-round clause stays absolute under it and vanishes under `off`. A ceiling
   would have denied that configuration to buy a boot error for a setting that is already inert.
3. **The property constructs rather than returning the singleton.** Branching on whether the
   configured number happens to equal the default, so `REPEAT_SALIENCE` could still be handed
   back, buys one object and costs an untested path. The policy is a frozen dataclass, so a
   fresh instance compares equal to the singleton and every consumer takes it structurally.
4. **The compose default is tied to the core constant.** `docker/docker-compose.yml` spells
   `${CORTEX_TOOLS_SALIENCE_LIMIT:-2}`, which is the core's `MAX_IDENTICAL_DISPATCHES` written a
   second time, so `crosscheck.py` now carries the pair: retuning the constant alone would leave
   every container started with the old number and nothing saying so. Proved by drifting the
   compose default to 3, which reddens the scan with the reason printed, then restoring it.

Three guards were mutation-proven rather than assumed. Dropping the threaded limit
(`RepeatSalience()` for `RepeatSalience(limit=self.salience_limit)`) reddens exactly two tests:
the config one that asserts the configured number reaches the policy, and the wiring one that
asserts it reaches both the cortex dispatcher and the subagent dispatcher, which is the shape a
refactor threading the kind and dropping the number would take. Deleting the boot check reddens
both parametrized cases of the below-one test. The wiring test's history is one earlier round
holding one identical call, so the same-round clause is silent and only the across-loop cap can
decide it: a limit of 1 refuses, the shipped 2 admits.

**What this does not settle.** Nothing has measured 2 as wrong. The knob exists so a deployment
that measures it can act without a code change, and the number in the tree is unchanged.

## Addendum (2026-08-21): the audit trail names the work each call was made for

Every dispatched call has written one line since this ADR landed, and until now none of them said
whose work it was. `LoggingAuditSink` printed `tool`, `ok`, `arguments`, `trust`, `at` and either
`result_chars` or `error`, so the durable record of what this machine did on a user's behalf could
be read tool by tool and never turn by turn. The named-turn addendum in
[ADR-0038](ADR-0038-ranked-recall.md) gave a failed turn a line that names itself and recorded, in
its decision 3, that half the value of doing so is the join to these lines, which did not exist.
This is that join, filed as
[R-342](../refinements/tasks/342-the-audit-trail-cannot-name-the-turn.md).

### Re-derived first, and the entry's cheapest claim is the one that was wrong

The entry said `ToolDispatcher._audited` "already holds everything it needs", so the change was a
field on `ToolInvocation` and a line in the sink. Half of that is true. The dispatcher overwrites
every call's stamp before any branch can return, so `_audited` really does hold the calling turn's
`TurnStamp` on the refusal, gate-denial and served paths alike. But that stamp carried
`session_id`, `tainted`, `sources` and three live handles, and **no turn id at all**: the turn id
lives on `ToolLoopContext`, which builds the stamp, and the stamp never took it. So the identity
the trail was missing was missing from the value the trail would have read it off, and the change
is a stamp field before it is an audit field.

The delegation half was further away still. A subagent's own tool loop dispatches through the same
dispatcher with `turn_id=task.id`, and the spawning turn's id reached neither the runner nor the
attempt: `SpawnSubagentsTool` reads `tainted`, `budget` and `progress` off the stamp and passes the
last two down as parameters, and nothing carried a turn.

### Decision 1: a field per kind, and the names are the ones the log stream already spells

The line gains three identities, not one: `session_id`, `turn_id`, `task_id`. `turn_id` is the
conversation turn the dispatch was made for; `task_id` is the subagent task it was made inside;
each is empty when the dispatch had none, so a turn's own call names no task and the schedule
ticker's fire names no turn.

The alternative was one field named for the unit of work, empty for an unattributed caller, which
is cheaper and makes the trail greppable by one key. It was rejected on three counts, in ascending
order of weight.

The value it prints is a turn id for two of the three dispatch callers and a task id for the
third, so the key would need a name meaning "turn or task" and every reader would have to look at
another field to learn which they were holding. The trail is the record read when something has
already gone wrong, and a field whose meaning varies by row is the wrong thing to hand that
reader.

The name would also be new. `turn_id` already means a conversation turn on every line in the brain
that prints one: the three mid-turn failure lines in `converse_stream`, the engine's own
cortex-cut warning, and the forgone-recall warning. Under `CORTEX_LOG_FORMAT=packed` a field name
is a path (`jq .fields.turn_id`), so spelling the same fact under a different key on the one trail
meant to join to those lines is a real cost rather than a cosmetic one.

And the decisive one: a single field would make a subagent's dispatches name an identifier that
resolves against nothing a reader can reach. A task id is minted by `uuid4` inside the spawn tool
and printed on no other log line in the tree (the GPU-to-CPU re-place warning carries one, and only
when a re-place happens), so the reading "what did this turn's subagents do?" would need the
`TaskStore`, whose records expire in an hour. Two fields put the answer on the line itself, which
is the whole claim the trail makes: it outlives the process, and every id it prints resolves
against another line or against a store that keeps one.

### Decision 2: the line takes the stamp's identities, not the stamp

[R-233](../refinements/tasks/233-toolinvocation-audit-stamp.md) recorded this as "the audit line
gains the stamp", and it does not. `TurnStamp` carries the
turn's dispatch pool, its progress channel and its handoff slot, all live handles excluded from
equality precisely because they are not values. A `ToolInvocation` is a value that outlives the
process that wrote it, so a record holding a live pool is a record no durable sink could ever write
down. It takes the three strings and leaves the handles behind.

### Decision 3: the spawning turn reaches a subagent through its stored task

`SubagentTask` gains `session_id` and `turn_id`, written by `SpawnSubagentsTool` off the dispatch
stamp and read back by the attempt when it builds its loop context. The alternative was to thread
the turn id down `SubagentRunner.run` and `PlacedAttempt.run` as a third keyword beside `budget`
and `progress`.

Those two are threaded rather than stored because they are live handles a store cannot hold. A turn
id is a value, and a subagent is a stateless function over the `TaskStore` (the one hard rule): the
runner loads its task by id and every other thing it must know to run safely, the requested model
and the spawning turn's taint, already rides that record for exactly this reason. An attribution
that lived only in a parameter would be the one fact about the work that a re-read could not
recover. The trigger on
[R-232](../refinements/tasks/232-subagenttask-session-attribution.md) was "a subagent-reachable
consumer of the attribution exists", and the audit trail is that consumer.

This widens what a subagent's dispatch stamp carries: its calls now name the spawning chat where
they used to name none. Nothing but the audit sink reads it today, because a subagent holds only
the MCP subset and none of the built-ins that read a stamp's session, and the widening is in the
honest direction for the day one of them does.

### Decision 4: an id the dispatch does not have is left off the line

The sink prints each identity only when it has one. An empty `turn_id=` reads as a value that went
missing, where absence reads as what it is: a call nothing conversational was waiting on. This
matches how the stamp has always spelled an unattributed caller, and how the sink already prints
`result_chars` or `error` and never both.

### What did not change, deliberately

The message stays a bare `tool.invocation`, the arguments stay the audit's subject, a success
still logs its result size rather than its content, and no user text joins any line. A subagent's
own working messages are still grouped under its task rather than under the turn that spawned it,
which the loop context now says outright: the two identities it is audited under are fields, and
what its messages are stamped with is `unit_id`, the work they belong to.

### Distrust green

Eight mutations, each applied to production code alone with the whole brain suite re-run, then
restored and read back off disk:

| Mutation | Reddens |
| --- | --- |
| the loop's stamp drops the turn id | 3 |
| the loop's stamp drops the task id | 2 |
| the dispatcher stops copying the three identities onto the record | 8 |
| the sink stops printing them | 2 |
| the sink prints them empty rather than leaving them off | 3 |
| the spawn tool stops writing the attribution onto the task | 2 |
| the Redis task record forgets the attribution it was handed | 1 |
| a subagent's messages regroup under the spawning turn | 1 |

The fourth row reddens two of the sink's three cases and not the third, which is the point of the
third: it asserts the ids are **absent** from an unattributed line, so a sink that prints nothing
satisfies it truthfully, and the fifth row is what that case is there to catch. The seventh is the
narrowest and the one worth having: it reddens only the Redis arm of the task-store contract, the
fake having nothing to serialize, which is exactly the asymmetry a contract test exists to catch.

### Consequences

- A turn's tool calls, its subagents' tool calls, and its own failure line all carry the same
  `turn_id`, so the trail reads turn by turn and the join the named-turn addendum half-built is
  whole.
- A delegated call names both its task and the turn that spawned it, so delegation is readable
  without the task store.
- A scheduled fire's dispatches name the chat that scheduled the item, which the ticker had been
  stamping honestly and nothing had been reading.
- The audit line grows from six fields to at most nine, all three additions being short ids.
- The two attribution deferrals that were waiting on a consumer are closed by this change rather
  than by a separate one.

### Deferred by this addendum

The dispatched call's own id still reaches no line, which is also the only place a fired schedule
item's identity appears:
[R-352](../refinements/tasks/352-a-dispatch-names-no-call.md). And the trail is now worth querying
and has nowhere to be queried, `ToolAuditSink` having exactly one adapter:
[R-353](../refinements/tasks/353-a-trail-worth-querying-has-no-store.md).

## Bound addendum (2026-08-21): one call on a sidecar is bounded, because nothing bounded it

A dispatch has always waited as long as the sidecar took. That was never written down as a
decision, and it turns out not to have been one: the wait is unbounded by construction, and every
layer above it was built as if a failing sidecar always raises. Filed as
[R-341](../refinements/tasks/341-nothing-declines-work-it-cannot-finish.md), whose third shape
asked for the remaining time to travel down to the model host and the MCP client.

### Re-derived first, and two of the entry's three claims were wrong

The entry said both downstream seams "run on their own bound with no relation to the caller's, so
a call that inherits none of its caller's deadline can outlive the request that made it by an
unbounded margin". Three separate readings of the tree, and only one of them survived.

**The model host is already bounded, and by a number this repo argues about at length.** Every one
of `HttpModelHost`'s six verbs goes through one injected `httpx.AsyncClient` built by
`build_control_client` with `httpx.Timeout(CORTEX_MODELHOST_TIMEOUT_S)`, a whole minute by default,
covering every phase of the call because a control call streams nothing. That bound is also
*compared* at wiring time against the three the sidecar reports it was given, and a deployment
whose worst legitimate stop does not fit under it is refused at boot. So there is nothing unbounded
there and nothing to add.

**The caller's remaining time cannot travel to either seam, and must not.** No unary handler on
`BrainService` touches a model host or a tool registry: the ten of them read the session store, the
schedule store, the preference store, the residency report and (for a delete's cascade) the memory
store, and that is all. Every model-host
call and every tool call in this brain is made from a `Converse` turn, from boot recovery, or from
a background loop. `Converse` announces no deadline at all and must keep announcing none, which is
the fence the abandonment work in [ADR-0024](ADR-0024-transport-retry.md) drew and expressed as
code. So the deadline these calls could inherit does not exist, and building the plumbing to
inherit it would be the first half of enforcing a bound that seam deliberately does not have.

**The tool seam really is unbounded, and worse than the entry guessed.** It is not that a tool call
runs on a bound unrelated to its caller's; it is that this repo states no bound for it whatsoever.
`ClientSession.call_tool` takes `read_timeout_seconds`, `McpToolRegistry` passes none, and the
session's wait is then `anyio.fail_after(None)`. The transport underneath carries the MCP SDK's own
default client timeouts, which this repo neither sets nor documents and which do not bound a
response the server never sends. So a sidecar that accepts a call and never answers holds the turn
open for as long as the process lives.

The consequence reaches further than one slow call, and this is what makes the shape worth
building. The degraded-mode addendum above is built entirely on `ToolError`:
`SkipUnavailableToolRegistry` serves around a sidecar by catching one, and a dial that fails raises
one. A sidecar that is merely wedged raises nothing, so the whole skip-and-report design has a hole
in exactly the shape of the failure it cannot see.

### Decision 1: the bound is a combinator over the port, not a feature of one adapter

`BoundedToolRegistry` (`cortex_core/tool_deadline.py`) joins the port-preserving family in
`aggregate.py`: it takes a `ToolRegistry`, bounds both verbs with `asyncio.timeout`, and raises
`ToolError` on an overrun. The module sits beside `tool_loop.py` (how many rounds) and
`tool_budget.py` (how much they may spend) as the third bound and the only one that is time.

The alternative was to pass `read_timeout_seconds` down from `McpToolRegistry`, which the SDK
offers and which would be two lines. It was rejected on three counts. It bounds the *response* and
not the *session open*, and `initialize` is a `send_request` with no timeout either, so a sidecar
that accepts the TCP connection and never completes the handshake would still hang. It puts a
deployment's policy inside one transport's adapter, so a second remote `ToolRegistry` later starts
unbounded again. And it cannot express the one thing the bound has to be selective about, which is
decision 2.

### Decision 2: the remote registries are wrapped, and the built-ins beside them are not

The composition root wraps each configured endpoint and nothing else. This is not a convenience:
several built-in tools are *deliberately* slow. `spawn_subagents` fans out into a batch of model
runs bounded at 2400 s apiece, and `escalate_to_brain` puts a card in front of a human and waits.
A bound over the merged tool set would cut exactly the calls that are supposed to take a while,
and it would cut them with a number chosen for a filesystem read.

Making the bound a wrapper rather than a policy inside the dispatcher is what makes that
selectivity expressible at all: the root already composes the remote half separately from the
built-in half, so the bound simply goes on the half that reaches outside the process.

### Decision 3: it goes innermost, so a wedged sidecar looks like a refused one

The wrapping order carries as much of the value as the bound. `BoundedToolRegistry` sits directly
around the `ReconnectingMcpToolRegistry`, under the allowlist filter and under the skip. Two things
follow. The bound covers the dial and the call together, which is the whole exchange and the only
part of it that reaches outside this process. And the `ToolError` an overrun raises is caught by
`SkipUnavailableToolRegistry` exactly as a refused dial is, so under
`CORTEX_TOOLS_ON_UNAVAILABLE=skip` a hung sidecar now drops out of the advertisement with a warning
naming it, which is the behaviour that design always claimed and never had.

Wrapped the other way round, an overrun would escape the skip and fail the whole tool set, which is
the mutation table's ninth row.

### Decision 4: one number for both verbs, and it belongs to the deployment

`CORTEX_TOOLS_CALL_TIMEOUT_S`, `DEFAULT_TOOL_CALL_TIMEOUT_S = 60.0`, bounding a listing and an
invoke alike. Both reach the same sidecar over the same session, and a listing that hangs strands a
turn before any call is made, so a second knob would be two numbers for one failure. The default is
far past a healthy call and far short of forever: the runbook's own table measures a fresh-session
`invoke` at 154 ms and a listing at 146 ms against the shipped filesystem sidecar, so 60 s is some
four hundred times the slowest call this deployment has ever timed, leaving room for a mailbox
search nobody here has measured. A value at or below zero fails at boot rather than refusing every
call in silence.

**It bounds a call and not a turn**, which is the one thing about this number worth reading twice.
A loop lists its tools once before its rounds and dispatches inside them, and every one of those
reaches the bound on its own, so a single wedged sidecar costs a cortex loop's first dispatch two
spends (the advertisement walk, then the call) and a subagent's three, the extra one being the live
walk `UngatedToolRegistry` makes to strip gated names before it delegates. Two spends of 60 s land
**exactly on** the confirm card's own 120 s wait rather than under it, and a subagent's three land
half again past it, so the pairing of the two numbers says nothing about what a wedge can cost a
turn and is not offered as an argument here. What the bound buys is that a wedge ends in a
`ToolError` the model reads, rather than in a turn nobody can end, and that every layer already
built for a sidecar that refuses now covers one that hangs.

### What did not change, deliberately

`Converse` still announces nothing, `ModelHost` grows no per-call deadline, the `ToolRegistry` port
signature is untouched, and no handler reads `time_remaining()`. An overrun is a `ToolError`, so
the dispatcher turns it into the `is_error` result the model already knows how to recover from and
audits it like any other dispatch; nothing here logs a second line about it.

### Distrust green

Thirteen mutations, each applied to production code alone and run over one suite of 196 cases
(`packages/core/tests/test_tool_deadline.py`, `packages/tools/tests/test_registry_contract.py`,
`packages/orchestrator/tests/test_wiring.py`, `packages/orchestrator/tests/test_config.py`), then
restored and each file compared by checksum against the copy taken before the first mutation:

| Mutation | Reddens |
| --- | --- |
| a call spends a hundred times the bound it was given | 2 |
| a call spends ten times the bound it was given | 2 |
| a listing spends a hundred times the bound it was given | 2 |
| a listing spends ten times the bound it was given | 2 |
| the call is not bounded at all | 2 |
| the listing is not bounded at all | 2 |
| `invoke` drops the `expired()` guard | 1 |
| the listing drops the `expired()` guard | 1 |
| the listing's overrun message is reworded | 1 |
| a non-positive bound is accepted at construction | 2 |
| an overrun stops cancelling the call it gave up on | 2 |
| the wiring bounds an endpoint with a number the config did not carry | 1 |
| the bound is wrapped outside the skip rather than inside it | 1 |

The hundred times rows were **green** when they were first run, and finding that out is the reason
the table exists. The overrun message renders `self._timeout_s`, and the bound is a separate
expression over the same field, so an object that named one number and spent another satisfied
every assertion in the suite: the message read back a value it held rather than the one it had
waited.

**The first repair of that was itself a gate that could barely fail**, and this is the second. It
timed the raise and required it inside twenty five times the bound, which is a window rather than a
bracket: measured on the recorded pair, a bound multiplied by **ten** left all eight cases green,
because ten times 20 ms still lands inside a 500 ms window. Worse, the stub it timed waited on an
event nothing sets, so the production bound was the only way out of the case, and with the bound
deleted the recorded cases returned **no verdict at all**: they were still running after 90 s, and
there is no `pytest-timeout` here to end them.

Both are fixed by the same change, and it removes the clock rather than tightening it. The stub now
answers three bounds late instead of never. A bound that fires cuts it, and a bound that is widened
or deleted lets it through with a result where a `ToolError` was required, so each of those
mutations is a red in under a second: the four widening rows and the two deletion rows above are
that, measured. Both waits are timers on the one event loop and are popped in deadline order
whatever the machine is doing, so this brackets the bound without comparing any wall-clock reading
to anything, which is what the previous window did and what made it load-sensitive as well as
loose. The clock is still read for the **floor** (an overrun must not land before the bound), which
no load can push the wrong way. An `asyncio.wait_for` sits over each case besides, the shape the
composition-root bound check uses, for the mutation the stub cannot catch: a production path that
stops returning at all.

The cancellation row is the other assertion no message could make: `asyncio.shield` around the
inner call leaves the overrun raising exactly the same `ToolError` while the sidecar call runs on,
which would leak a session per dispatch. It reddens two cases rather than one now, the overrun
case having gained the same `cancelled` assertion.

The registry in `scripts/` was proved the same way and separately, its own gate being a different
one: retyping the runbook's `60.0` as `61.0` reports one untied constant naming the runbook, and
restoring it clears.

### Verified against a real socket

The claim the fakes cannot make is that cancelling through the real MCP client unwinds cleanly:
beneath `BoundedToolRegistry` sit an anyio task group, a cancel scope and an `except*`, and an
`asyncio.timeout` that cut through them badly would surface an `ExceptionGroup` or a bare
`CancelledError` rather than the `ToolError` every layer above expects. So the integration-marked
suite gained a case that stands up a listener which accepts the connection and answers nothing,
points the shipped registry stack at it, and measures what comes out. Both verbs raise `ToolError`
at the bound (1.50 s and 1.51 s against a 1.5 s bound), and the only task alive afterwards is the
fake server's own handler: no client task, and no socket, survives the cut.

### Consequences

- A wedged tool sidecar fails one call instead of holding a turn open indefinitely, and the model
  is handed a sentence naming the tool and the bound that it can act on.
- The skip-and-report degraded mode covers the failure it could not previously see, so
  "unavailable" finally means down *or* wedged.
- Every remote tool call in this brain now runs under a number this repo states, rather than under
  a default buried in a dependency.
- The built-in tools are untouched, so delegation and the confirm card keep the long waits they are
  designed to have.
- One more knob in the base compose file, tied by `scripts/crosscheck.py` to the runbook and the
  module contract that quote it.

### Deferred by this addendum

One bound covers every sidecar, so a mailbox search and a file read run under the same ceiling:
[R-362](../refinements/tasks/362-one-bound-for-every-sidecar.md). And the new bound and the
subagent run deadline are independent numbers with no ordering between them, where the neighbouring
bounds on that tier are ordered and checked at boot:
[R-363](../refinements/tasks/363-the-call-bound-and-the-run-bound-are-unordered.md).

The other two shapes of the entry this addendum closes were decided rather than built, and each
kept its own file: the early decline on a read that will not fit
([R-360](../refinements/tasks/360-a-read-that-will-not-fit-declines-early.md)) and the partial
answer whose cascade does not exist in any read path
([R-361](../refinements/tasks/361-a-read-rpc-recalls-nothing-to-omit.md)).
