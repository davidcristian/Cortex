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
session cache/pool is a later optimization behind the unchanged `ToolRegistry` port and recorded in
the ROADMAP. The port, the audited `ToolDispatcher`, and the core combinators are unchanged;
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

Still remaining behind the same seam: the **salience** half (which calls *deserve* dispatching);
the **unbounded batch size** of `spawn_subagents` itself, now bounded in dispatches but still
unbounded in model runs (a per-call cap on `instructions` is the obvious next bound, and it is a
spawn-tool decision, not a budget one); and a **fair-share policy** if one greedy subagent
starving its siblings ever shows up in practice.
