# ADR-0009: Tools via MCP with ToolRegistry + audited dispatch, native function-calling

- **Status:** Accepted (Slice 6)
- **Date:** 2026-06-29

## Context

Slice 6 lets the cortex call tools, starting with a filesystem, then read-only
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
   compose default to 3, which fails the scan with the reason printed, then restoring it.

Three guards were mutation-proven rather than assumed. Dropping the threaded limit
(`RepeatSalience()` for `RepeatSalience(limit=self.salience_limit)`) fails exactly two tests:
the config one that asserts the configured number reaches the policy, and the wiring one that
asserts it reaches both the cortex dispatcher and the subagent dispatcher, which is the shape a
refactor threading the kind and dropping the number would take. Deleting the boot check fails
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

| Mutation | Tests that fail |
| --- | --- |
| the loop's stamp drops the turn id | 3 |
| the loop's stamp drops the task id | 2 |
| the dispatcher stops copying the three identities onto the record | 8 |
| the sink stops printing them | 2 |
| the sink prints them empty rather than leaving them off | 3 |
| the spawn tool stops writing the attribution onto the task | 2 |
| the Redis task record forgets the attribution it was handed | 1 |
| a subagent's messages regroup under the spawning turn | 1 |

The fourth row fails two of the sink's three cases and not the third, which is the point of the
third: it asserts the ids are **absent** from an unattributed line, so a sink that prints nothing
satisfies it truthfully, and the fifth row is what that case is there to catch. The seventh is the
narrowest and the one worth having: it fails only the Redis arm of the task-store contract, the
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
call with no explanation.

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

| Mutation | Tests that fail |
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
which would leak a session per dispatch. It fails two cases rather than one now, the overrun
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

## Ordering addendum (2026-08-21): the innermost bound is ordered against the run that holds it

The bound addendum above gave a tool call its first ceiling and related it to nothing. A subagent's
whole run is bounded too, by `CORTEX_SUBAGENTS_RUN_TIMEOUT_S`, and that deadline explicitly covers
the tool dispatches its loop makes, so the new bound sits **inside** it and the two numbers had no
ordering between them. Filed as
[R-363](../refinements/tasks/363-the-call-bound-and-the-run-bound-are-unordered.md).

### Re-derived first, and the entry understated its own failure

The entry was written the same night the bound landed and it holds: both numbers exist as it
describes, the shipped pair (60 s under 2400 s) is ordered correctly by a wide margin, and nothing
enforces that. What it did not say is what a misordered pair actually produces, and the answer is
worse than a truncation reported late. Driven through the shipped `PlacedAttempt` against a sidecar
that accepts a call and never answers:

| the pair | what comes back |
| --- | --- |
| call 0.05 s under run 1.0 s | the call is cut at its bound, the `ToolError` becomes the `is_error` result the loop recovers from, and the subtask **answers** |
| call 5.0 s over run 0.3 s | the run's deadline fires first, `AttemptFailure.TRUNCATED`, and **no text at all** |

So the inversion does not merely delay the failure. It deletes the recovery the bound was built
for: the whole point of decision 3 above is that a wedged sidecar now looks like a refused one, and
a delegated run whose call bound sits above its own deadline never reaches that path. The detail
the cortex then reads says the subtask "was still generating" and should be narrowed before it is
delegated again, which sends the reader to the model and the instruction when the cause was a
sidecar and a knob two settings away. And `TRUNCATED` is deliberately never re-placed, so the CPU
re-run a transport failure earns is skipped as well.

The entry's reading of where the fix belongs also holds. The two numbers are read by two settings
classes, `ToolsConfig` and `SubagentsConfig`, and neither can see the other, so the comparison
belongs at the composition root that holds both. That is where the model-host pairing ended up for
the same reason.

### Decision 1: a boot-time refusal, the shape both neighbouring checks already have

`check_tool_call_deadline` refuses a deployment whose delegated dispatch does not fit inside its
run bound, and it is the third such check rather than a new idea. `SubagentsConfig` already refuses a run
deadline that does not outlast its own stall ceiling, and `check_control_deadline` already refuses
a control deadline the model host's worst stop can outlast. The call bound is a fourth bound on the
same delegated run, and it was related to none of the others. The three `SubagentsConfig` declares
nest by the scope each bounds, one silent gap inside one whole run inside the queue for a run; this
one is the innermost's sibling rather than its child, bounding one tool dispatch where the stall
ceiling bounds one silent read, and both of them sit inside the run.

**A clamp was rejected.** It would retune a number the operator typed, and it would have to pick
which one. Lowering the call bound to meet the run bound leaves the two equal, which is the race
decision 2 exists to avoid. Raising the run bound spends more of the user's wall clock and holds a
model lease longer than the deployment asked for. Both are silent, and this repo refuses silent
holes at every comparable point: a non-positive bound, a price outside the dispatch budget, a
blank gate reason and an ask no admission could ever fit all fail at boot rather than quietly
becoming something else.

**A logged warning was rejected.** It leaves the misordering running, so the failure still arrives,
still reported with a diagnosis that names the wrong cause. The reason to check at boot in the first
place is that the reason is a knob two settings away that nobody would look at, and a warning line
in a container log at boot is exactly as invisible as the knob it describes. The one place a
warning **is** right is where `check_control_deadline` puts one, a far side that cannot be *asked*;
both numbers here are this process's own env and are always readable, so that arm has no analogue.

### Decision 2: what is compared is a whole dispatch, strictly under, where both capabilities are on

**The bound is spent per walk, not per dispatch**, and comparing the two numbers as they are typed
under-protects the very path this check exists for. Measured through the real composition root with
one wedged sidecar at a 0.25 s bound, counting how many times a single dispatch reaches
`BoundedToolRegistry`:

| dispatch | sidecars | `on_unavailable` | bounds spent |
| --- | --- | --- | --- |
| cortex | 1 | `skip` | 1 |
| cortex | 2 | `skip` | 2 |
| **subagent** | **1** | `skip` | **2** |
| **subagent** | **2** | `skip` | **4** |
| either | either | `fail` | 1, the walk aborting at the first overrun |

A delegated dispatch costs twice a cortex one because `UngatedToolRegistry.invoke` re-lists the
registry to strip gated names before it delegates, a live walk it keeps deliberately uncached so a
re-flagged tool fails closed. `AggregateToolRegistry.invoke` re-lists to route, which is the second
doubling, and it is absent at one endpoint, a lone registry being composed as itself. The run's own
advertisement, one more walk, is spent before any of it.

So `CORTEX_TOOLS_CALL_TIMEOUT_S=700` under `CORTEX_SUBAGENTS_RUN_TIMEOUT_S=900` passes a bare
comparison and then spends 1400 s inside a run allowed 900, which is exactly the failure at the
head of this addendum. What the check compares is therefore `delegated_call_bounds(tools)` times
the call bound, strictly under the run bound: one advertisement walk, one gated strip, one routing
walk and the call, each walk costing one bound per configured sidecar, which is 3 at one sidecar
and 7 at two.

**A fixed factor was rejected.** Any single number is either wrong above one sidecar or absurd at
one, and the endpoint count is sitting in the very config object the check is already handed, so
guessing at it would be a decision to know less than the process does.

**Widening it to a whole run was rejected too.** A run makes many dispatches over many rounds, so
the honest ceiling on what one wedged sidecar can cost a run multiplies this again by
`MAX_TOOL_DISPATCHES`. The shipped 60 s under 2400 s does not clear that, so the check would reject
the stack this repo ships. It would also be protecting the wrong thing: the failure here is a run
cut *mid call* and reported as a subtask that would not stop talking, and avoiding that needs the
model to reach the tool error at all, not the run to survive every possible wedge. What a passing
check promises is written in its own docstring, in those words, so the next reader does not have to
infer the promise from the arithmetic.

Strictly, the `ControlBounds.clears` rule for the reason that rule gives: a dispatch allowed the
whole of the run leaves which bound fires a race, and the expensive side of that race is the one
that reports a wedge as a runaway. Checked only when `CORTEX_TOOLS_BACKEND=mcp` and
`CORTEX_SUBAGENTS_BACKEND=llamacpp`, the shape of `check_control_deadline` returning early for a
deployment that never escalates: without `mcp` no `BoundedToolRegistry` is built, and without a
delegation backend there is no run for a call to sit inside. The cortex's own loop stays out of the
series deliberately, a `Converse` turn announcing no deadline for its calls to be ordered against
([ADR-0024](ADR-0024-transport-retry.md)), and so does the schedule ticker, which has none either.

### Decision 3: gated at the env read, in a module that builds nothing

The check runs on `SubagentsConfig` on its way out of the environment and into everything that
spends it, before a single adapter is built, so a refusal releases nothing at all. That is one
better than the control deadline's own check, which has a runtime to close before it raises because
asking the far side is what tells it there is a fault.

It lives in `cortex_orchestrator/bounds.py`, a new module for the orderings no single settings
class can check for itself, rather than in `builders.py` beside the builder whose registry spends
the bound. The line cap forced the question, the check taking that file to 319 lines, and the
answer it forced is the right one: a builder returns an adapter plus the coroutine that releases
it, and this returns a config and opens nothing, so it was never that kind of function. The module
also has a second tenant waiting, since a per-sidecar bound would make this check compare the
largest of several rather than one.

### What did not change, deliberately

The `ToolRegistry` port, `BoundedToolRegistry`, the two config classes and both defaults are
untouched: this addendum adds a relation between numbers, not a number. Neither knob gained a
ceiling of its own, because neither is wrong alone. And the shipped stack is unaffected: a
delegated dispatch on it costs 180 s of a run allowed 2400, a factor of thirteen, or 420 s with
both shipped sidecars layered on, which is what the two passing cases below pin.

### Distrust green

Eleven mutations, each applied to production code alone and run over the whole `brain/packages`
suite of 2836 cases (80 integration cases deselected), then restored and both files compared by
checksum against the copy taken before the first mutation:

| Mutation | Tests that fail |
| --- | --- |
| the comparison reads the two fields the other way round | 5 |
| the comparison accepts equality | 1 |
| **the dispatch is compared as one bare call bound** | **5** |
| the multiple stops counting the aggregate's routing walk | 3 |
| the multiple stops counting the endpoints a walk lists | 3 |
| the multiple stops counting the call itself | 8 |
| the misordering is logged and the deployment served anyway | 4 |
| the guard drops its `mcp` half | 1 |
| the guard drops its `llamacpp` half | 2 |
| the refusal renders the run bound where it names the call bound | 2 |
| the composition root stops calling the check | 1 |

**The third row is the one the table exists for now.** It is the check as it was first written,
comparing the two bounds as typed, and the five cases it fails are what the first version had no
way to notice: nothing in that suite drove a pair that was ordered and still lost a run. The case
that pins it is named for what it is, a pair the bare comparison admits, and it carries the
reviewer's own numbers, 700 s under 900 s.

The tenth row is the one the table has always existed for. This repo has now been bitten three
times by a test that pins a number by interpolating that same number into the string it asserts on,
most recently in the bound addendum above, where an object naming one value and spending another
satisfied every assertion in the suite. So the refusal's values are asserted as literals a reader
typed, at knobs a reader typed, and the set on the record is read through the shipped formatter
rather than out of `caplog.text`, which carries the message alone and would have passed for as long
as the numbers happened to be printed twice.

The first row is worth its own sentence too, because it fails the direction cases and not the
equality one: reversed, the comparison still refuses an equal dispatch, so the case that pins
strictness cannot tell a swapped comparison from the shipped one. Two mutations, two different
cases, and neither case is spare.

One row is reported rather than tidied. The whole sweep was run twice, and on the second run the
equality arm failed a second case, `test_abandon.py`'s reading of the time a dropped call had
left, which no comparison in this module can reach. The arm was run a third time on its own and
failed only its own case, as it had the first time, so that reading is load-sensitive rather than
caused by anything here, three processes having shared the machine on the run that saw it. It is
filed as
[R-370](../refinements/tasks/370-an-expiry-reading-is-asserted-exactly.md) rather than left as a
number somebody else has to explain.

### Consequences

- A deployment whose delegated dispatch does not fit inside its run bound is refused at boot with
  both knobs, both values, the multiple between them and the product, instead of serving until the
  first wedged sidecar and then blaming the model. The multiple is what makes the refusal readable:
  700 s under 900 s looks ordered and is not, and a sentence naming only the two bounds would have
  had to leave the operator to work out why.
- Both bounds that sit inside a delegated run, the stall ceiling on one silent read and the call
  bound on one dispatch, are now checked against the run that contains them, where before only the
  first of them was, and the relation is written where the numbers are read rather than in a
  runbook. The run's own place under the queue for it is the one relation in this series still
  written only in prose.
- The headroom a deployment has is a property of the **deployment** and not of the pair of numbers
  in it: adding a second sidecar more than doubles what a wedged dispatch costs without touching
  either knob. That is now on the boot line as `call_bounds_per_dispatch`, so an operator reading
  the log sees the term that would otherwise be invisible.
- `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` joins `scripts/crosscheck.py` as an ordinary equality, tied to
  the delegation runbook, the tool runbook and the module contract that spell it out. Its
  declaration and its two restatements were untied before this, and the pairing's own sentence in
  the tool runbook would have made a third restatement of a number nothing held together.
- A brain with tools or delegation switched off is untouched, which is CI and the no-GPU dev loop.

### Deferred by this addendum

The ordering is enforced against a **deployment's** numbers and not against the repo's own: the
constant scan already has a `Relation.ORDERED` for bounds that must sit under one another, but it
compares integers and every one of these bounds is a float, so a retune of a shipped default that
inverted the pair would ship and wait for a deployment to turn both capabilities on:
[R-367](../refinements/tasks/367-the-shipped-ordering-of-two-bounds-is-ungated.md). Note that a
registry row could only hold the weakest form of this relation, the shipped call bound under the
shipped run bound: the multiple depends on how many sidecars a deployment configures, and the repo
ships no such count. And the
composition root is now exactly at the 300-line cap, so the next capability wired there has to
split the file before it can add a line:
[R-368](../refinements/tasks/368-the-composition-root-has-no-headroom.md). Reading the series also
turned up the one relation in it that is documented and enforced nowhere, a run deadline that has
to sit under the wait a queued peer will spend, which is two fields of one settings class and so
the cheapest of the four to check:
[R-369](../refinements/tasks/369-the-run-deadline-under-the-queue-is-prose-only.md).

## Root-headroom addendum (2026-08-22): the part of the root that is not a composition step

The ordering addendum above landed one import line and left `wiring.py` at exactly 300, so the
next capability wired there had to split the file before it could add a line. Filed as
[R-368](../refinements/tasks/368-the-composition-root-has-no-headroom.md).

### Re-derived first, and every number in the entry held

The file was 300 lines with 52 comment lines and a 21-line module docstring, and the three nested
closures the entry names (`capabilities`, `make_turn_engine`, `make_engine`) spanned 74 lines,
closing over exactly the fourteen local names it counted. Its reading of why they had stayed also
held: each of the six earlier splits took a builder out one module at a time, and what was left
around them really is a sequence of config reads, builder calls and a `finally` that releases in
reverse order, with no economy in it to find.

### Decision 1: the seam is per-stream against per-process, not the largest block

What comes out is chosen by **how often it runs**, not by how many lines it saves. Everything else
in the root runs once at boot; those three closures run again for every Converse stream, because a
stream's confirmer and progress sink are what they add to the shared adapters. That makes them a
factory rather than a composition step, and it makes the extracted object's contract easy to state:
built once from parts that never change, called once per stream. `stores.py` was lifted out on the
same argument and is the precedent this follows.

Cutting instead by size was rejected. The largest single block is the boot ordering, and it is the
one part that cannot leave: what the root exists to say is which object is built before which, and
the comments arguing those orderings are the file's real content. Splitting it would have moved
the argument away from the code it is about and left the root reading as a list of calls to
elsewhere.

### Decision 2: an object with twelve fields, and the escalating three travel as one

`StreamEngines` (in `engines.py`) takes twelve names where the closures captured fourteen. The
difference is not compression for its own sake: `BrainRuntimeConfig` arrives whole because four
of its fields are read (the window's three plus the model id), while the three settings objects
that were captured for one value each are reduced to that value, so the factory is handed a
`DispatchPolicy` and a bool rather than `ToolsConfig` and `MemoryConfig`. The bool is still mapped
at the root, where the string is read, which is where ADR-0019 put it.

The escalating arm's three parts are one `DeepTier(swap, builtins, scheduler)`, present exactly
when `CORTEX_ESCALATION` is on. They are meaningless apart: the deep tier's own vision-less
built-in set exists only for a handoff to run, and the subagent pool's scheduler is reached only
to be drained before one. As one value, a half-wired handoff cannot be expressed, and the branch
in the factory is one `is None` on a single field rather than a `swap is None` test standing in
for the state of three names.

### What did not change, deliberately

No behaviour. The two built-in sets are still assembled at the root, and the deep set is still
built whether or not escalation is on, which is what it did before. The window, the guardrail and
the dispatcher are still built per stream rather than hoisted to boot, since that is where they
were built and hoisting one would be a behaviour change presented as a refactor. Every
existing case in `test_wiring`, `test_swap_wiring` and `test_vision_wiring` passes unchanged
except for two `monkeypatch.setattr` targets in the vision suite, `build_cortex_tools` and
`BrainPhase`, which now name the module those two are called from. No assertion moved.

### Distrust green

Four mutations, each applied to `engines.py` alone with the 445 tests of `packages/orchestrator`
re-run over it. Caching the bundle so every stream gets the first stream's fails exactly one
case, the new suite's two-confirmer one, which is the property no end-to-end suite can see: each
of them opens a single stream, so all three stayed green under that mutation while the second
stream's gated call would have prompted the wrong overlay. Handing the deep phase the cortex's
built-in set fails two, the new deep-tier case and the vision suite's. Dropping the reply bound
from the bundle fails one. Returning the plain engine unconditionally fails four, which is the
whole escalating arm and no more.

### Consequences

- `wiring.py` is 230 lines, so the next capability wired at the root has 70 lines to arrive in
  rather than a split to perform first. The root reads as the sequence of composition steps it is,
  ending in one factory construction and the `serve` call it feeds.
- The per-stream contract is now testable without a socket. `test_engines.py` drives the factory
  over in-memory parts, which is what made the two-confirmer case cheap enough to write at all;
  through `run_from_env` it would have meant two live Converse streams over a real channel.
- Three module docstrings that justified an earlier placement with "the composition root is at its
  line cap" now say it was, since the sentence was load bearing for those decisions and is no
  longer true of the file it names.

### Deferred by this addendum

The factory is reachable only through the package's submodule attribute: `engines.py` exports
`StreamEngines` and `DeepTier` in its own `__all__`, but the `cortex_orchestrator` barrel lists
neither, following `stores.RedisStores`, which the barrel also omits. That is deliberate for a
composition-root internal and it leaves the module contract's own rule ("everything importable
from `cortex_orchestrator`; `__all__` is the API") describing something narrower than what the doc
now documents:
[R-378](../refinements/tasks/378-the-barrel-rule-omits-two-root-internals.md).

## Named-call addendum (2026-08-22): the line names the call, and the fired item beside it

The named-work addendum put the chat, the turn and the task on every audit line and left the
**call** itself unnamed. `ToolCall.id` is what correlates a call with its result across the loop,
and `ToolInvocation` never carried one, so `ToolDispatcher._audited` dropped the only string that
says which of a turn's dispatches a line is. The same gap is why a scheduled fire's line says
nothing about which item fired: the ticker spells the item into its call id and nowhere else.
Filed as [R-352](../refinements/tasks/352-a-dispatch-names-no-call.md).

### Re-derived first, and three of the entry's claims needed narrowing

The two structural claims held exactly. `ToolInvocation` has nine fields and none of them is a
call id, and `_audited` builds one from `call.name`, `call.arguments`, the result and the three
stamp identities, so the id is dropped at the one place that holds it. The ticker really does
build `ToolCall(id=f"schedule-{item.id}", ...)` in `_run_task`, and that really is the only place
a fired item's identity reaches the dispatch path: the stamp beside it carries `session_id` and
`tainted`, and the arguments carry the item's text and its requested model, never its id.
`VALUE_CHARS` really does bound a rendered value, at 2048 characters of **rendering** rather than
of value, spent after the credential pass and marked with the count that went.

Three claims were looser than the entry made them sound.

"Withheld by name like every other field" describes a mechanism the field is subject to and that
will never fire on it. `record_fields` withholds a value whose key contains one of nine secret
markers, and `call_id` contains none, so the honest statement is that the id joins a line whose
every field is screened, not that the id is screened out of anything.

"Paired with the `Role.TOOL` message it produced" is true only inside the turn. `store_codec`
encodes a message as role, text, timestamp and turn id, and nothing else, so no stored message has
ever carried a `tool_call_id`; the pairing an id buys is against the live working list, and
against the one durable place a call id already lands, the handoff record `handoff_codec` writes
when a turn escalates.

"Two identical calls in one turn write two lines nothing can tell apart" overstates what
`RepeatSalience` allows. An identical twin inside one round is refused outright and identical
calls across rounds are capped at two, so the shape is one served line and one refusal line, or
two served lines in different rounds, and those differ in `at` and often in `ok`. What no line can
do is say **which** dispatch it is, which is the real gap and the one this addendum closes.

### Decision 1: the call's own id goes on the line, model-authored and all

A cortex call's id is whatever the backend emitted: `finish_calls` reads it off the streamed
`tool_calls` fragments and hands it through unread. So the question the entry raised is real, and
the answer is that the audit trail is the wrong surface to refuse a model's string on.

This repo already refuses one, and the refusal is instructive because of where it sits.
`run_round` renders the overlay's tool chip from `spec.name`, never from `call.name`, precisely so
a display surface carries no string the model chose. The audit line is the opposite kind of
surface. It is the record of **what was asked for**, and it has always carried the model's own
strings: `tool` is `call.name` and `arguments` is the model's argument mapping, logged verbatim as
the audit's subject, which is a far larger and far more attacker-shaped value than an id. A trail
that recorded only strings the brain authored would be a record of the brain's reaction rather
than of the request, and the request is the thing an operator is reading the trail to see.

The narrower shape, recording an id only where the brain wrote one, was rejected on what it leaves
undone rather than on cost. Under it a cortex call gets no id at all, so the join to the working
list and to a handoff record does not exist, and the correlation gap the entry opened with stays
open for every dispatch a model makes, which is nearly all of them. Serving only the second
reading does not serve the first.

### Decision 2: the fired item is its own field, not a prefix read back out of the first

The other direction fails too. Putting `call_id` on the line does name the fired item, but only as
the text of a string the trail cannot vouch for: `call_id=schedule-abc` is what the ticker writes
when item `abc` fires, and it is also what a model writes by choosing that id. A reader could
recover the difference today by noticing that a genuine fire's line carries a chat and no turn and
no task, and that reading is exactly the kind of rule the named-work addendum refused when it
rejected one field meaning "turn or task": a fact that has to be reconstructed from the absence of
two other fields is the wrong thing to hand someone whose day has already gone wrong.

So `TurnStamp` gains `item_id`, the ticker sets it from the item it is firing, and the line prints
it beside the three identities it already prints. It is a work identity like they are, minted by
the brain, and the model cannot reach it for the same reason it cannot reach the others: the
dispatcher overwrites the call's stamp with the caller's before any branch can return.

That is also what distinguishes the two new fields on the line, and it is the field **name** that
carries the distinction rather than anything about the strings. `call_id` is the call's own
correlator, whoever wrote it, and is read the way `tool` and `arguments` are read: as what was
asked for. `item_id` is off the stamp, and is read the way `session_id`, `turn_id` and `task_id`
are read: as what the brain knows about the work. The line has had those two classes of field
since it had fields at all, and each addition joins the class it belongs to.

The ticker keeps its `schedule-` prefix, which is a perfectly good unique id and is what the
result message inside the fire is keyed by. It is decorative for the trail's purposes, and the
test suite pins that: a model-authored `schedule-` id produces a line with no `item_id` on it, so
the counterfeit fails structurally rather than by a reader's judgment.

### Decision 3: what bounds a model's string, and what it does not

Four things stand between a hostile id and the line, and none of them is new work.

`render_value` quotes any rendering that carries whitespace or a quote of its own, and quoting
means `json.dumps`, so a newline arrives as an escaped `n`, a carriage return as an escaped `r`,
and a NUL or an ANSI escape as a `\u` sequence. The two characters that could open a second field
are exactly the two that force the quoting, so **no model-authored value can add a field boundary
to a line**. A forged `INFO:cortex.tools.audit:tool.invocation ok=True` lands inside one quoted
value.

`VALUE_CHARS` cuts the rendering at 2048 with a marker naming the characters that went, and an
over-long id cannot buy its way out by staying bare: bare rendering is guarded by the same bound,
so a long id is quoted and cut like any other.

`record_fields` screens the key, which will never fire on `call_id` and is the reason the field is
named for the call rather than for anything a secret is named for.

And nothing reads it back. The id reaches a log record and no store, no branch, no cache key and
no decision. It is a fact written down, which is what an audit line is for.

What this does not buy is that no substring can appear. A model can put the characters
`turn_id=t-victim` inside its id, and the line will contain them inside a quoted value beside the
genuine `turn_id`. That is already true of `arguments` and of `tool`, both of which have carried
model-authored text since this ADR landed, and it is why the claim made here is about the line's
**structure** rather than about its substrings: the fields on a line, their names and their count
are the brain's, and only what is inside a quoted value is ever the model's.

### What did not change, deliberately

The message stays a bare `tool.invocation`. A success still logs its result size rather than its
content, arguments stay the audit's subject, and an id the dispatch does not have is still left
off the line rather than printed empty, which now covers five fields instead of three. `ToolCall`,
`ToolResult` and `Message` are untouched: the id already existed on all three, and this addendum
copies it rather than inventing it. A ticker-rooted subagent's own dispatches still name no item,
because `SubagentTask` carries the attribution it was given and `item_id` is not on it yet.

### Distrust green

Nine mutations, each applied to production code alone with the 2,865 tests of `brain/` re-run
over it (`pytest -q` at the repo's own fixed seed, integration cases deselected), then restored
and read back off disk:

| Mutation | Tests that fail |
| --- | --- |
| the dispatcher stops copying the call's own id onto the record | 5 |
| the record's call id is filled from the fired item instead of from the call | 5 |
| the dispatcher stops copying the fired item onto the record | 2 |
| the ticker stops stamping the item it is firing | 2 |
| the sink stops printing the call id | 6 |
| the sink stops printing the fired item | 1 |
| the sink prints the two new ids empty rather than leaving them off | 7 |
| a rendered value may stay bare even carrying whitespace | 11 |
| a bare rendering escapes the length bound | 7 |

The first two rows fail the same five cases, which is the point of the second: the five assert
the id the **call** carried, so a line that names an id truthfully and names the wrong one fails
exactly as one that names none does. The sixth row is the narrowest and the one worth having. It
fails only the case that asserts `item_id` is **present**, because the case beside it asserts
the field is absent from a model-authored `schedule-` line, and a sink that prints no item at all
satisfies that one truthfully; the seventh row is what that asymmetry is there to catch.

The last two rows are mutations of `log_fields.py` rather than of anything this addendum wrote,
and they are here because the adversarial cases are claims about a defence they do not own. A
`_BARE` pattern that tolerates whitespace lets a hostile id render unquoted, and the newline, the
quote and the control-character cases go red together with eight of the formatter's own; dropping
the length guard from the bare path fails the over-long case with six more. Without those two
rows the three cases would be assertions about behaviour that happens to hold rather than about a
defence that is load bearing.

The first attempt at the first row reported 39, and that number was a defect in the mutation and
not a reading. The anchor `call_id=call.id,` at that indentation matches the refusal's
`ToolResult` before it matches the audit record, so what ran was a `TypeError` on every dispatch
with a refusal in it. Recorded because the shape recurs: a mutation whose count is an order of
magnitude off is a mutation that did not do what its label says.

### Consequences

- A line says which dispatch it is, so a turn's audit lines join its live working list and a
  handoff record's serialized calls, and two identical calls in one turn stop being two lines that
  differ only by a timestamp.
- A scheduled fire names the item that fired, in a field the model cannot write, so the one caller
  nobody is watching is the one whose subject the trail now states outright.
- The audit line grows from at most nine fields to at most eleven, both additions being short ids
  that print only when the dispatch has them.
- `TurnStamp` gains its first identity that is not a conversational one, and the only caller that
  sets it is the ticker.

### Deferred by this addendum

A subagent spawned by a scheduled fire runs its own tool loop through the same dispatcher, and its
dispatches name the chat and the task and not the item, because `item_id` stops at the spawn call:
[R-380](../refinements/tasks/380-a-fires-delegates-do-not-name-the-item.md).

## Queue addendum (2026-08-23): the run deadline is ordered against the queue for it

The ordering addendum above related the innermost of the four bounds on a delegated run to the run
itself, and left the outermost relation where it had always been, in a runbook sentence.
`docs/runbooks/subagents-cpu.md` said the deadline "lands between the two bounds either side of it,
above the stall ceiling and below the admission wait", and only the first half was refused at boot.
Filed as [R-369](../refinements/tasks/369-the-run-deadline-under-the-queue-is-prose-only.md).

### Re-derived first, and the entry over-counted what was already enforced

The entry opens "three of the relations between them are now refused at boot" and then names two,
which is the true count. `SubagentsConfig._the_run_deadline_must_outlast_the_stall_ceiling` refuses
one and `check_tool_call_deadline` refuses the other; `ToolsConfig` declares no validator over
`call_timeout_s` at all, and nothing anywhere compares `run_timeout_s` with `admission_wait_s`.
Everything else the entry says held: both are plain fields of one class, the wait may be zero and
means never queue, and the neighbours are strict.

What the entry did not know is that the relation it quotes is not true of the numbers this repo
ships, and cannot be made true by a comparison. `SubagentRunner._placed` re-runs a GPU-placed
inference failure once on the CPU **inside the same admission**, and `PlacedAttempt` arms the
deadline fresh for that second attempt, which the runner's own docstring states outright: "a task
can therefore hold its admission for two deadlines rather than one". Twice the shipped deadline is
above the shipped wait, so a check comparing what a run can really hold would refuse the stack this
repo ships, at boot, on defaults nobody typed.

### Decision 1: a validator beside the stall-ceiling one, and strictly under

Both numbers are fields of `SubagentsConfig`, so this is not the composition-root shape the call
bound needed; it is the shape its other neighbour already has, a `model_validator(mode="after")`
that compares two of this deployment's own numbers and refuses. The failure it refuses is a pool
that works and reads as one that does not: a peer gives up while the run in front of it is still
inside the time the same deployment granted it, and the refusal the operator then reads names the
queue, which is the knob that did not cause it.

Strictly under, for the reason both neighbours are strict. Equality means the peer gives up at the
instant the room it queued for comes back, which is a race rather than a relation holding, and it
is the same race `check_tool_call_deadline` refuses one bound short of.

### Decision 2: a zero wait passes, because that deployment has no relation to keep

`admission_wait_s` is `ge=0` and zero is a policy the runbook states: never queue, refuse whatever
does not fit right now. Under a zero wait nothing ever queues behind a running spawn, so there is
no peer for a deadline to outlast and no relation between the two numbers at all. Read as a bare
inequality, zero is the smallest possible inversion and the loudest failure; read as what it means,
it is the one setting where the question does not arise. Refusing it would make "never queue"
unsettable beside any deadline whatsoever, which is every deployment that sets it, so the
comparison is guarded rather than the field re-typed: the guard is where the meaning lives, and
`ge=0` stays the field's own statement that zero is a number an operator may type.

### Decision 3: what is compared is one attempt's deadline, and the doubled hold is filed

The measured worst case is two deadlines, along the one path a dead GPU-placed backend opens. Three
answers were available and two were rejected.

Comparing the doubled hold refuses the shipped pair. Both numbers are measured (the deadline is
four times the longest whole subtask on the shipped entry, the wait twice the serial batch wait
these budgets produce), so clearing the doubled relation means retuning a measurement rather than
correcting an ordering, and it would take a re-measurement this change is not making. That is the
same reason the ordering addendum declined to widen its own comparison to a whole run: a ceiling
the shipped pair does not clear is a ceiling that refuses working deployments.

Warning instead was rejected for the reason it was rejected one addendum ago. A boot line nobody
greps is exactly as invisible as the knob it describes, and it leaves the misordering running.

So the validator compares one attempt's deadline, which is the misordering an operator can type,
and the doubled hold is recorded where a known gap belongs, in the backlog and in the two documents
that state the relation. The runbook sentence the entry quotes has been corrected rather than
merely enforced: it claimed a run can never hold its admission longer than a peer will queue for
it, and along the re-run path it can.

### What did not change, deliberately

No bound moved. The shipped deadline, wait, stall ceiling and call bound are the numbers they were,
and every deployment that boots today still boots, with one exception that is the point of the
change: a wait tightened under the run deadline is now refused where it used to run. The suite's
own admission-wait case was such a pair (a 900 s wait beside the shipped 2400 s deadline) and now
tightens to 3000 s, which is what that case was always testing, a deployment shortening the hour.

### Distrust green

Four mutations, each applied to `config_subagents.py` alone with the 2,875 tests of `brain/` re-run
over it (`pytest -q` at the repo's own fixed seed, integration cases deselected), then restored and
read back off disk:

| Mutation | Tests that fail |
| --- | --- |
| the run deadline is never compared with the admission wait | 1 |
| the comparison admits equality | 1 |
| a wait of zero is compared like any other | 3 |
| the pair is compared the other way round | 45 |

The first two fail the one case that asserts the ordering, which holds both arms of it, and the
third is the one worth having: it fails the zero case, the existing settable-including-zero case,
and the wiring suite's own never-queue build, which is the pool proving behaviourally that a zero
wait refuses rather than parks. The fourth row is not a subtler mutation but a sanity check on the
sweep: comparing the pair the other way round refuses the shipped defaults, so 45 cases across the
config, wiring and bounds suites fail at construction, and a first row of 1 beside a fourth row of
45 is what tells you the gate is narrow rather than absent.

### Consequences

- All three relations in the series a delegated run is bounded by are now refused at boot, two by
  validators on the class that declares both numbers and one at the root that reads two classes.
- A deployment tightening the admission wait must now bring the run deadline under it, which is a
  boot failure naming both knobs rather than a pool that refuses spawns for reasons no line states.
- The runbook says what is enforced and what is not, so the one relation this repo cannot keep
  under its own measured numbers is written down rather than claimed.

### Deferred by this addendum

The doubled hold on the CPU re-run path is unenforced and the shipped pair does not clear it:
[R-392](../refinements/tasks/392-a-re-runs-second-deadline-outlasts-the-queue.md). And the
admission wait's shipped default is spelled in two documents beside its declaration and tied by no
row of the constant scan, where the run deadline beside it is tied by three:
[R-393](../refinements/tasks/393-the-admission-waits-default-is-tied-to-nothing.md).

## Fired-work addendum (2026-08-23): a fire's delegate names the item that fired it

The named-call addendum above put the fired schedule item on the audit line and stopped at the
ticker's own dispatch. The subagent that dispatch spawns runs its own tool loop through the same
dispatcher, so the work a fire actually caused was audited under the chat and a task id and no
item, and `grep item_id=t1` reached the one line saying the item fired and none of the lines
saying what firing it caused. Filed as
[R-380](../refinements/tasks/380-a-fires-delegates-do-not-name-the-item.md).

### Re-derived first, and every hop the entry names was where it said

`TurnStamp.item_id` exists and only `ScheduleTicker._run_task` sets one; `ToolDispatcher._audited`
copies it onto the record; `SubagentTask` carried `session_id` and `turn_id` and no item;
`SpawnSubagentsTool.invoke` wrote those two off the stamp; `PlacedAttempt.run` read them back into
its `ToolLoopContext`; and `_stamp` built every delegated dispatch's stamp from that context
without an item. The entry's account of why neither existing field is a filter also holds: the
chat is on a conversation's lines too, and the task id is minted by `uuid4` inside the spawn tool,
printed on no other line, and stored under an hour's TTL.

One count in it needs correcting, and it is the count this addendum's own decision turns on. The
entry calls them "the four work identities on `ToolLoopContext`", which is what they become; there
were three before this change, and with the item there are four.

### Decision 1: the identity rides the stored task, and the entry's own argument is why

`SubagentTask` gains `item_id`, `SpawnSubagentsTool` writes it off the dispatch stamp,
`PlacedAttempt` reads it back into the loop context, and `_stamp` puts it on every dispatch the
delegate makes. Threading it down `SubagentRunner.run` and `PlacedAttempt.run` as a keyword beside
`budget` and `progress` was available and is wrong for the reason those two are threaded: they are
live handles a store cannot hold, and an id is a value. A subagent is a stateless function over
the `TaskStore` (the one hard rule), so an attribution living only in a parameter is the one fact
about the work that a re-read after a restart could not recover. This is decision 3 of the
named-work addendum applied to the third identity, and the record already carried the two
neighbouring ones for the same reason.

### Decision 2: the codec reads it as a required key, so a dropped id cannot read as an absence

`""` is already how this record says a spawn had no item behind it, which is every spawn a
conversation made. A codec that supplied `""` for a key it could not find would make an
attribution it dropped indistinguishable from an absence it was told about, and the trail would
then state something about the work, that nothing fired it, on the strength of a field nobody
wrote. So the key is required, exactly as `session_id` and `turn_id` are, and a record missing it
is corruption that fails loudly.

Tolerating a record written by an older build was weighed and refused on the module's own stated
model: task state is hot and ephemeral, written and read back by one deployment inside one turn
under an hour's TTL, which is why it carries no `v`/`kind` markers at all. A tolerant read would be
a legacy path for records this store says it does not have, bought at the price of the distinction
above. The suite pins it: a record carrying every other field and no item is read as corrupt.

### Decision 3: the four identities stay four keywords, and the bundle is declined

The entry asked whether they should travel as one value. They do not, and the criterion is the
one `DeepTier` was built on in the root-headroom addendum: a bundle earns its name when its parts
are meaningless apart, so that a half-wired state cannot be expressed. These four are the opposite.
Each is independently present or absent, and decision 4 of the named-work addendum makes each
absence a fact the trail states by leaving the field off. Every combination is a caller this tree
really has: a turn (chat and turn), a turn's delegate (chat, turn, task), a fire (chat, item), a
fire's delegate (chat, task, item), an unattributed dispatch (none). A bundle would exclude no
invalid state.

It would also cost more than it saves at both ends. Three places construct a `ToolLoopContext` and
this change adds one keyword to one of them. The same four identities are flat on `TurnStamp` and
flat on `ToolInvocation`, the latter deliberately, decision 2 of the named-work addendum having
chosen the strings over the stamp because a durable record cannot hold a live handle. So a bundle
on the context alone buys a translation in `_stamp`, and a bundle on all three puts a nested value
inside the audit record whose flatness is a decision already made. The fifth argument the entry
anticipates would change the arithmetic and not the criterion, and is filed as the trigger it is.

### What did not change, deliberately

No new field on `TurnStamp`, `ToolInvocation` or the log line: the item has been on all three since
the named-call addendum, and this addendum only carries the value further along the path it was
already on. The ticker is still the only caller in the tree that sets one, so a model still cannot
reach it. A subagent's own messages are still grouped under its task rather than under whatever
spawned it, and the delegate of a fire still names no turn, a fire not being one.

### Distrust green

Five mutations, each applied to production code alone with the 2,877 tests of `brain/` re-run over
it (`pytest -q` at the repo's own fixed seed, integration cases deselected), then restored and read
back off disk:

| Mutation | Tests that fail |
| --- | --- |
| the spawn tool stops writing the fired item onto the task | 1 |
| the stored record drops the fired item on the way in | 4 |
| the codec supplies a default for a record that carries no item | 1 |
| the attempt does not read the item back into its loop context | 1 |
| the loop stamp drops the item off every dispatch | 1 |

Three of the rows of one are three different hops of one path, and the case they fail is the
same one: the end-to-end delegation case that dispatches a fire-shaped call and asserts the item
on both the fire's line and its delegate's. That is the point of an end-to-end case over a chain
nothing else joins, and it is why a per-hop unit case was not written beside it: each would assert
the hop's own copy back, and none would say the chain carries an id from a fire to the work it
caused.

The third row is the narrow one and fails a different case, the record missing an identity being
read as corrupt. A codec that defaults a key it cannot find is invisible to every case that writes
a record before reading it, which is every other case in the suite, so without that one the
required key would be a decision nothing held.

The second row is the loud one and its shape is the reading: dropping the item on the way into the
store makes the record undecodable, so it fails the Redis arm of the task-store contract, its
timezone case and the `from_url` case, and leaves the in-memory arm green, which is exactly the
asymmetry a contract test over a fake and an adapter exists to catch.

### Verified against a real Redis

The suite's Redis arm is fakeredis, so the round trip was driven once against `redis:8-alpine`
through the real `RedisTaskStore`, the real `ToolDispatcher`, the real `LoggingAuditSink` and the
process entry's own `PlainFormatter`, with only the model faked. A fire-shaped dispatch carrying
`item_id=r-live-1` produced these two lines, which is the whole reading the entry was opened for:

```
INFO:cortex.tools.audit:tool.invocation arguments={"path":"/notes"} at=2026-08-23T03:00:00+00:00 call_id=s1 item_id=r-live-1 ok=True result_chars=18 session_id=chat-live task_id=live-task-1 tool=read trust=untrusted
INFO:cortex.tools.audit:tool.invocation arguments={"instructions":["summarize the notes"]} at=2026-08-23T03:00:00+00:00 call_id=schedule-r-live-1 item_id=r-live-1 ok=True result_chars=32 session_id=chat-live tool=spawn_subagents trust=untrusted
```

and the task read back out of Redis carried `item_id='r-live-1'` beside `turn_id=''`. Before this
change the first of those two lines carried no item at all.

### Consequences

- One grep by item reaches the fire and the work firing it caused, which is what the field was
  added for and what it did not yet do.
- `SubagentTask` now carries the whole of what the spawning dispatch knew about its work, so the
  runner audits a delegated call from the store alone whether a conversation or a fire spawned it.
- The four work identities are settled as four fields rather than a value, with the argument
  written down, so the next one to arrive has a criterion to be judged against rather than a
  precedent to follow.

### Deferred by this addendum

The ticker's own log lines spell the fired item `reminder_id` where the trail spells it `item_id`,
so the grep this addendum restores still misses the lines the ticker writes about the same fire:
[R-394](../refinements/tasks/394-the-fired-item-has-two-spellings-in-the-logs.md). And the four
identities are copied by hand across six hops with nothing structural tying them, which is what
makes a fifth one's arrival the moment to re-open the bundle:
[R-395](../refinements/tasks/395-a-work-identity-is-copied-by-hand-at-every-hop.md).

## Held-ordering addendum (2026-08-23): where an ordering between bounds is kept, and why not in the constant scan

The queue addendum above ordered the delegated run's deadline against the wait a queued peer will
spend, beside the older validator ordering it against the stall ceiling. Both are `SubagentsConfig`
validators. Within hours a backlog entry was filed asking for the same three bounds to be ordered
again in `scripts/crosscheck.py`, on the reading that the ordering the core module's comment states
was "held by nothing". This addendum records that the entry is declined, what its premise got
wrong, and the criterion the decline leaves behind.

### What the tree actually does

Three declarations, three modules, all decimals:
`DEFAULT_STALL_TIMEOUT_S = 600.0` in `config_subagents.py`,
`DEFAULT_SUBAGENT_RUN_TIMEOUT_S = 2400.0` in `cortex_core/subagents.py`, and
`DEFAULT_ADMISSION_WAIT_S = 3600.0` in `cortex_core/scheduler.py`. `SubagentsConfig` imports all
three as its field defaults and carries a validator for each relation between them:
`_the_run_deadline_must_outlast_the_stall_ceiling` and
`_the_run_deadline_must_fit_inside_the_queue_for_it`. Both run on every construction of that class,
whatever the backend, so the class cannot be built out of a misordered trio.

That is the load-bearing consequence and it is what the entry missed: because those three
declarations are the class's own defaults, **a bare construction is a reading of the repo's shipped
numbers**, and the orchestrator suite makes many. Retuning any one of the three into an inversion
fails on the commit that types it, with no deployment and no capability enabled. The zero wait is
carved out inside the second validator, meaning never queue, so nothing waits on a running spawn
and there is no relation to keep.

### Why the constant scan is the wrong home for it

The registry ties one value spelled in several places. An ordering is a relation between three
different values, and expressing it there would cost three concessions at once:

- `Relation.ORDERED` compares integers. All three bounds are decimals, and `values.py` reduces a
  decimal to the digits it is written with rather than to a number, deliberately, so that a needle
  spelled `5` does not go looking inside `5.0`. Teaching the ordering to compare decimals means
  parsing that text back into arithmetic in the one module that refuses to.
- `Relation.ORDERED` is non-decreasing, and every relation between these bounds is strict. The
  proposed entry would have gone green on all three set equal, which is precisely what both
  validators refuse.
- The registry suite requires an entry to span more than one language, and three Python
  declarations do not.

Three concessions to buy a weaker copy of a check that already exists is a bad trade, and a second
place stating a relation is a second place to let it go stale.

### The criterion this leaves

**An ordering between two numbers one settings class reads belongs in that class's validators. An
ordering between numbers no single class reads has nowhere else to go and is the constant scan's
business.** That is why the tool call bound under the run bound stays open as
[R-367](../refinements/tasks/367-the-shipped-ordering-of-two-bounds-is-ungated.md): its check is
`check_tool_call_deadline`, not a validator, and it runs only when a deployment enables both tools
and delegation, which CI never does. The subagent trio has the opposite shape, so it needs nothing.

### Measured, on `brain/packages/orchestrator/tests/test_config.py` (104 cases)

| Mutation | Tests that fail |
| --- | --- |
| the run deadline retuned to 4000.0, above the shipped wait | 11 |
| the run deadline retuned to 500.0, under the shipped ceiling | 10 |
| the stall ceiling retuned to 3000.0, above the shipped deadline | 13 |
| the admission wait retuned to 2000.0, under the shipped deadline | 10 |

Every row is a shipped default retuned into an inversion of a relation the core module's comment
states, and every row is red without a deployment. The first row fails 36 cases over the whole
brain workspace suite rather than 11. Restoring each file from a copy returns the suite to 104
passed, and the converse holds: with the three declarations as they ship, nothing here is red.

The registry alternative was measured too, in the negative. `relation_fault` under
`Relation.ORDERED` answers two decimal readings with "an ordering compares integers, and a site
here declares something else", and answers two equal integer readings with `None`, which is the
non-strictness above.

### Consequences

- The ordering the core module states is enforced, and the sentence saying so is now true. It had
  claimed only the first of the two orderings was refused at boot, which stopped being the case
  when the queue addendum landed and did not touch the sibling module that names it.
- The backlog keeps one entry about the constant scan's blindness to a decimal and to a strict
  relation instead of two, and that entry now records both halves.
- A future ordering has a criterion to be judged against rather than a precedent to copy.

### Deferred by this addendum

Nothing new. The one relation these validators still cannot make true along the CPU re-run path is
already
[R-392](../refinements/tasks/392-a-re-runs-second-deadline-outlasts-the-queue.md), unchanged by
this.

## One-vocabulary addendum (2026-08-24): one name per work identity, and the two that were spelled twice

The named-work and named-call addenda gave the audit trail four work identities off the dispatch
stamp and a fifth off the call, and said the five print alike and are read differently, which is
the field name's job. That is only true if each has one name. Two of them had two, and the two
splits were filed separately:
[R-339](../refinements/tasks/339-two-spellings-of-one-conversation.md) for the conversation and
[R-394](../refinements/tasks/394-the-fired-item-has-two-spellings-in-the-logs.md) for the fired
schedule item, the second explicitly asking to be read beside the first. They are one decision and
close together here.

### Re-derived first, and both counts had moved

**The conversation.** R-339 counted five sites under `session_id` against two under `session`, and
its own trail raised the first to six when the tool audit line landed. It is seven against two:
`engine.py`'s unreadable-tool-call warning attaches `session_id` beside `turn_id`, and it landed at
05:40 on 2026-08-20, fifteen minutes after the entry was written at 05:25, and the trail entry added
the next day did not notice it. Counting lines rather than sites, which neither the entry nor its
trail does, it is ten against three, `summarizing.py` carrying two of the ten. Every recount since
the entry opened has moved the same way.

The runbook cost it named is real and was verified on the file rather than taken from the entry:
[memory-pgvector.md](../runbooks/memory-pgvector.md) tells an operator to join a fallback to its
trail line with `grep "session=<id>"`, and reads `session=None` as a recall that arrived unnamed.

**The fired item.** R-394's account of the ticker holds exactly: three `_logger` records under
`extra={"reminder_id": ...}`, the fire that failed, the release that failed, and the push that fell
back to pull. Its account of the other side is narrower than the tree. Besides the audit trail,
`cortex_session/schedule_claims.py` names a schedule item `item_id` on two more lines, the
quarantine of a corrupt record and the undecodable record on the claim path, and
[scheduling.md](../runbooks/scheduling.md) prints the second of those verbatim. So the split was
three lines against three and not three against one trail.

**A third surface, which is what R-394 said it was waiting for, and it was already there.** Eleven
lines on the swap path name their work with a bare noun: `swap_conductor.py` writes
`extra={"turn": turn_id}` four times, which is a second spelling of an identity in the vocabulary
below, and seven lines across `swap_settle.py`, `swap_recovery.py` and `brain_phase.py` name a
handoff `handoff`, which is a sixth identity the stamp does not carry. Neither entry mentions it and
both are older than none of it. It is filed rather than fixed here, for the reason given under what
did not change.

### Decision 1: a line names a work identity with the dispatch stamp's own name for it

The vocabulary is the five the stamp and the audit record already carry: `session_id`, `turn_id`,
`task_id`, `item_id`, `call_id`. Both renames follow from that one rule and neither needed a
separate argument, which is why the two entries closed together.

For the conversation the rule and the count agree: seven sites to two, and `session_id` is
additionally what the seam declares (`ClientEvent`, `SessionSummary`, `DueReminder`), what all
three Redis codecs write, and what sits beside `turn_id` on the same lines. R-339 worried that
moving the other five to `session` would leave `turn_id` looking odd; that worry is the argument
for this direction, since the family is uniform only if the suffix stays.

For the fired item the count does not decide it and the rule does. R-394's objection, that
`item_id` puts a name on the line that does not match the seam message the line is about, answers
itself on the tree: two of the ticker's three lines are about a fire that never reached the seam,
one of them being the release of a claim whose fire failed, so there is no `NotifyRequest` for them
to be named after. A log line is the brain's reading of its own work, and the brain fired an item.
The seam's `reminder_id` is untouched, and that the two differ is the decision rather than a drift.

The alternative R-394 raised, carrying both fields on those three records, is refused for the
reason it anticipated: the formatter renders every field a record carries, so both names would
print on every one of the three lines and a reader would meet two names for one id in the same
line, which is a larger version of the same defect.

### Decision 2: the runbook cost is payable, because the interface has one consumer

R-339 called a shipped trail's field names the closest thing this repo's logs have to an interface.
That is true and the interface's whole consumer list is two sentences in a runbook two directories
away, both updated in this change. AGENTS.md freezes a key once anything beyond the host machine
depends on it, and nothing outside this tree reads these logs, so the rename is still cheap and
this is the moment named in that rule for healing a mismatch.

### Decision 3: the vocabulary is declared once, and one sink spends it

`cortex_core.log_fields` declares `SESSION_FIELD`, `TURN_FIELD`, `TASK_FIELD`, `ITEM_FIELD` and
`CALL_FIELD`, beside `RESERVED_ATTRS` and `SECRET_NAMES`, because a field's name is the same kind
of fact those two lists hold: what a field is rather than what it holds. Five constants and not a
collection, because each is a separate answer a separate set of places must agree with, and because
a collection reduces to no single value the constant scan could tie a far side to.

`LoggingAuditSink` spends all five and nothing else does. That is a line rather than an
inconsistency: the audit sink is the one place that writes the whole vocabulary out as a list, where
naming each element costs a reader nothing, and every other site names one identity inside its own
`extra=` dict, where the literal is the string an operator greps and hiding it behind an identifier
would take it out of the one place a reader looks for it. The same trade the registry already makes
for a docstring restating a number rather than importing it.

### Decision 4: the rest is held by the constant scan, and R-339's reason it could not was wrong

R-339 closed by saying a log field's name is neither declared nor spent, so registering the family
would need a new kind of entry. It is spent, as the string key opening an `extra=` dict, which is
the bare-literal case the registry vocabulary already covers; what was missing was a declaring
site, and decision 3 is that one line. `scripts/logcouplings.py` is a tenth registry part with five
ordinary entries, tying each declaration to every module that spells the name and every runbook
that tells an operator to grep it. The part, its naming and its two pinned counts are argued in the
ADR-0029 addendum that adds it.

### What did not change, deliberately

The swap path keeps its bare nouns, filed as
[R-415](../refinements/tasks/415-the-swap-path-names-its-work-with-bare-nouns.md). Renaming the
conductor's four is mechanical, but the seven beside them are a sixth identity that would have to
join the vocabulary first, and one of those lines is printed verbatim in the swap runbook as
`handoff=<turn id>`, which is a second question about whether that id is a turn's. Doing either
inside a close about the conversation and the fired item would have buried both.

No line gained or lost an identity, no seam field moved, no record on disk changed: the Redis
codecs still spell their own hash keys, which outlive the deployment that wrote them and must stay
free to move apart from a log field. `NotifyRequest.reminder_id` is untouched.

### Distrust green, over the brain suite

Four mutations, each applied to production code alone with the 2,877 tests of `brain/` re-run over
it (`pytest -q` at the repo's own fixed seed, integration cases deselected), then restored and read
back off disk. All four restorations matched by digest.

| Mutation | Tests that fail |
| --- | --- |
| the recall trail reverts to the older `session` spelling | 1 |
| the rank's two fallbacks revert to it | 3 |
| the ticker's three lines revert to `reminder_id` | 1 |
| the tool audit writes its own name for the conversation | 2 |

The third row is the one to read. Reverting **all three** ticker lines fails a single case, and
that case asserts two of them: no test in this repo has ever pinned the field name on the
push-that-fell-back-to-pull line, which is the line an operator meets when the body is down. Its
name is held by the registry mention alone, whose count of 3 is what notices a line leaving the
set. That is the division of labour the registry part was added for, written down here rather than
left to be inferred from a small number.

The second row is three because the judge's pair is asserted from three angles, the record, the
rendered line and the no-content case, which is what the named-recall addendum built. The fourth
row is two and is the one that proves decision 3 is load-bearing rather than cosmetic: a sink that
stops spending the vocabulary and writes its own name for the conversation is caught by the audit
suite, not only by the scan.

### Distrust green, over the crosscheck registry

Twelve planted disagreements, one at a time on the real tree, all twelve exiting 1 and all twelve
restorations matching by digest. The counts there are over the crosscheck registry rather than over
any suite, and the table is in the ADR-0029 addendum beside the part it measures.

### Consequences

- One grep by conversation reaches all ten lines that name one, where it used to reach seven or
  three. One grep by item reaches the fire, the work firing it caused, the ticker's own account of
  how it went and the claim path's two failures.
- The five ids the named-work addendum said are told apart by their field names now have one field
  name each, so that sentence is true rather than nearly true.
- A rename of any of the five moves the declaration, and the scan then names every place that did
  not move with it, including the runbook sentences no import could ever have reached.

### Deferred by this addendum

The swap path's bare nouns
([R-415](../refinements/tasks/415-the-swap-path-names-its-work-with-bare-nouns.md)), and the
registry's blindness to a module nobody has listed: a new file writing `extra={"chat_id": ...}` is
spelled in no mention, so every mention still resolves and the gate stays green
([R-416](../refinements/tasks/416-a-new-log-line-can-name-its-work-anything.md)).

## Sixth-name addendum (2026-08-24): the swap path names a turn, because a handoff id is one

The one-vocabulary addendum above settled that a brain log line names its work with the dispatch
stamp's own name for it, and left the swap path's eleven bare-noun records outside that rule,
filed as [R-415](../refinements/tasks/415-the-swap-path-names-its-work-with-bare-nouns.md). It
left them because seven of them looked like a **sixth** identity, one the stamp does not carry, and
admitting a sixth name is a bigger decision than repeating a rename. This closes that entry, and
the sixth name is not needed.

### Re-derived first, and the counts hold

Four records in `swap_conductor.py` write `extra={"turn": turn_id}`: the claim already held, the
opaque turn, the unrostered deep tier, and the store that still has a record in flight. Seven name
a handoff `handoff`: three in `swap_settle.py`, one in `swap_recovery.py`, and two spellings in
`brain_phase.py` serving three lines, the reading and the no-reading arms of the cadence report.
Eleven records, as filed. One of the conductor's four also carries `active_handoff`, which is the
second question below.

### The question the entry could not answer: what is a handoff id?

It is the escalating turn's id, and the proof is at the mint rather than at any site that logs one.
`EscalationSlot.snapshot(turn_id=..., session_id=..., requested_at=...)` returns
`HandoffRecord(handoff_id=turn_id, ...)` and is the only production construction of a record other
than the codec that reads one back off Redis under the key it was written to. `HandoffRecord`'s own
docstring has said so since the record existed (*"``handoff_id`` is the escalating ``turn_id`` (one
handoff per turn at most)"*), the conductor is handed `turn_id` and passes it straight through, and
`EscalatingTurnEngine` names the handoff it claims by the `turn_id` it was handed rather than by
anything the inner runner produced. The runbook was already saying it out loud in the one place a
reader meets the field, printing `handoff=<turn id>`.

So there is no sixth identity. Seven records were **misnamed**, in exactly the way the conductor's
four were: a second name for something the vocabulary already names.

### Decision 1: all eleven name the turn, and the vocabulary stays at five

`turn_id` on every one of them. What this buys is the reading the entry named: `grep turn_id=t-...`
now returns a turn's failures, its tool calls, the tool calls its subagents made, **and** every
line about the handoff that turn asked for, which is the set an operator wants at the one moment
they are reading any of it. The alternative, a sixth `handoff_id` name, would have been a second
number to grep for a fact that is one number, and the runbook would have had to explain that the
two ids are equal, which is a sentence no reader should need.

`HandoffRecord.handoff_id` itself does **not** move, nor does the codec's hash key, nor the Redis
key `cortex:handoff:<turn id>`. Those are a record's own schema and address: they outlive the
deployment that wrote them, and the store is genuinely keyed by handoff, one per turn being a fact
about the escalation and not about the record's identity. Renaming the field would also make the
store's port read as though it took the turn store's key. The log field and the wire field are
free to differ, which is the same line the one-vocabulary addendum drew against the seam's
`reminder_id`.

### Decision 2: a line naming two of one identity qualifies the name in front

The conductor's refusal-while-the-store-holds-one line carries two ids that are now both turns:
the turn being refused, and the turn whose handoff the store is still holding. Naming both
`turn_id` is impossible (one dict, one key) and would be wrong if it were possible. The rule: the
line's own work keeps the plain name, and the other instance takes a qualifier **in front of the
family word**, here `active_turn_id`, after the store's own `active()` verb that produced it.

In front rather than behind, because that is what keeps `grep turn_id=` reaching both: the
qualified name ends in the family's own token, so the family grep finds the qualified line too,
which is exactly the property the whole vocabulary exists for. `turn_id_active` or `handoff_turn`
would each hide the line from the grep that should find it. This is written down as the rule for
the next line that names two of anything, and it is currently the only such line in the brain.

### Decision 3: the runbook moves with the field, and says what it now means

[model-swap.md](../runbooks/model-swap.md) printed the failed-handoff line verbatim as the thing to
look for while somebody is waiting. It now prints `turn_id=<turn id>` and says in one sentence why
the two words are one number, and that the Redis key below is the one place the id still carries the
word `handoff`, being the record's address. [tools-mcp.md](../runbooks/tools-mcp.md)'s sentence
about what `grep turn_id=t-...` gathers gains the swap path, which is the consequence rather than a
second instruction.

### Decision 4: the registry holds them, including the qualified spelling

`scripts/logcouplings.py`'s turn entry grows from four mentions to eleven: the four swap modules,
the qualified spelling, and the swap runbook's two sentences. Two of the module mentions pin an
exact count, the conductor's four and the settler's three, each being one module's whole account of
one thing. The qualified name is tied to the **same** declaration through a template that renders
the qualifier in front of it (`"active_{value}":`), so a rename of `TURN_FIELD` moves the qualified
spelling with it and cannot leave it behind. That template is the part of this change worth reusing:
a qualified name is not a second constant, it is the same constant written under a longer key.

### Distrust green, over the brain suite

Seven mutations, each planted in production code alone with the 2,877 tests of `brain/` re-run over
it (`uv run pytest -q --no-cov`, the repo's own fixed seed, the 82 integration cases deselected as
always), then restored and compared by digest. All seven restorations matched.

| Mutation | Tests that fail |
| --- | --- |
| the settler's failure line reverts to the bare `handoff` | 2 |
| all three of the settler's lines revert to it | 2 |
| the conductor's two-turn refusal names them the other way round | 1 |
| the conductor's four revert to the bare `turn` | 1 |
| the conductor drops the qualifier, naming both turns alike | 1 |
| the deep phase's two cadence lines revert to `handoff` | 2 |
| boot recovery's stranded line reverts to `handoff` | 1 |

The second row is this change's version of the reading the one-vocabulary addendum recorded about
the ticker: reverting **all three** of the settler's lines fails the same two cases as reverting
one, because the only settler line any test names is the one the runbook prints, and it is named by
a parametrized case that runs twice. Before this change **no test in the repo pinned any of the
eleven field names**; after it six records are pinned by a test (the failed settle, the two-turn
refusal, and the deep phase's three, which two spellings and two cases cover) and five are held by
the registry's counts and presence checks alone: the settler's other two, and three of the
conductor's four. That division is deliberate and is the reason the two counts are pinned rather
than left as presence checks. Reverting the conductor's four fails exactly the one case that
reads a whole line, which is what the count of four is there to catch instead.

The fifth row is the one that proves decision 2 is load-bearing: a conductor that names both turns
`turn_id` loses one of them to the dict, and the case that reads the whole line catches it. The
third row is the same case catching the two ids swapped, which is the failure that would send an
operator to restart the turn that asked rather than the handoff that is wedged.

### Distrust green, over the crosscheck registry

Ten planted disagreements over the registry, one at a time on the real tree, tabled in the
ADR-0029 addendum beside the part they measure, since their counts are over the registry rather
than over any suite.

### Consequences

- The five names stay five. A sixth was proposed by the shape of the code and refused by what the
  code actually does, which is the kind of question a re-derivation answers and a count does not.
- One grep by turn now reaches the swap path. The refusals a turn met, the settle that ended its
  handoff, the deep tier's decode rate for it, and the boot that found it stranded all carry the
  same id under the same name as its tool calls.
- The one line that names two turns says which is which, and both are still reachable by the
  family grep.
- A future line naming a second instance of any identity has a rule to follow and a template in
  the registry to be held by.

### Deferred by this addendum

The record's own `handoff_id` and the store keyed by it are deliberately untouched, and nothing
ties the log field to them; that is the decision above rather than a deferral.

**The swap path names a turn and never the conversation**
([R-417](../refinements/tasks/417-the-swap-path-never-names-the-conversation.md)), which reading
every one of the eleven records is what turned up. Seven other modules attach `session_id` and the
audit sink writes it on every call, and none of these do, so a grep by conversation reaches a
chat's recalls, summaries, mid-turn failures and
tool calls and nothing about the handoff it asked for. It is the opposite shape to this addendum's
defect, no line being wrong and every line missing a field, and it is a change to what those
records carry rather than to what they call it, so it wants its own argument, particularly on the
cadence lines where a tier's throughput is arguably not about a chat at all.

The other deferral is unchanged from the one-vocabulary addendum: a new module writing a work
identity under a name nobody has registered is still invisible to the scan
([R-416](../refinements/tasks/416-a-new-log-line-can-name-its-work-anything.md)), and this change
adds four more registered modules to the set that entry is about.

## Hold addendum (2026-08-25): the queue is ordered against the hold, not against one attempt

The queue addendum above ordered the delegated run's deadline against the wait a queued peer will
spend, and recorded that what it compares is **one attempt's** deadline while a task can hold its
admission for two. It listed three answers, took the one that could be taken without a
re-measurement, and named the other two as things the shipped numbers could not clear. That
re-measurement has now been taken (the ADR-0005 batch addendum), and this addendum makes the
comparison the one the invariant actually needs.

### Re-derived first, and one sentence of the record was wrong about the mechanism

Everything structural the entry claimed holds. `SubagentsConfig._the_run_deadline_must_fit_inside_the_queue_for_it`
compared the bare `run_timeout_s`; `PlacedAttempt.run` arms `asyncio.timeout(self._bounds.timeout_s)`
per attempt; `SubagentRunner._placed` calls that attempt twice inside one `scheduler.admit`, and
`_persist` runs inside it as well. Twice the shipped 2400 s deadline is 4800 s and the shipped wait
was 3600 s, so the shipped pair really did not clear the relation the class states.

One sentence of the entry's own re-derivation was wrong, and it matters because it sized the
window. It said a stalled stream reaches `AttemptFailure.INFERENCE` through the attempt's
`TimeoutError` arm, "whenever the timer that fired was not the attempt's own". It does not.
`CORTEX_SUBAGENTS_STALL_TIMEOUT_S` is httpx's **read** timeout, and `httpx.ReadTimeout` is not a
subclass of the builtin `TimeoutError`; `LlamaCppBackend` catches `httpx.HTTPError` and
`_transport_failure` turns it into `InferenceError`, which reaches the attempt's `InferenceError`
arm instead. The verdict is the same, `INFERENCE` and therefore re-placeable, so the conclusion
survived a wrong mechanism.

**What the wrong mechanism cost was the size of the window**, and the corrected reading widens it
rather than narrowing it. The entry reasoned that a stall fires at the ceiling and so the common
doubled hold is 600 s plus a fresh 2400 s, comfortably inside the wait, leaving only "a backend
dying late in a stream that never went quiet". But a read timeout bounds **one socket read**, so it
fires at *the last chunk plus 600 s*, not at 600 s. A GPU-placed stream that produces chunks for
more than 600 s and then wedges therefore holds its room for more than 1200 s before the re-run's
fresh deadline even starts, and the batch above measured whole subtasks holding their admission for
up to 595.2 s serialized. So the window is not exotic: it is any wedge after the first ten minutes
of a stream, plus every mid-stream transport failure at any elapsed time at all.

### Decision 1: the comparison is over the hold, and the factor is a named constant

`ATTEMPTS_PER_ADMISSION` is declared in `cortex_core.subagents` beside the two bounds it relates,
and the validator compares `ATTEMPTS_PER_ADMISSION * run_timeout_s` with `admission_wait_s`. Two
things make that better than a bare `2 *`. The number is the runner's property rather than the
config's, so it belongs where the runner's other shipped numbers are declared; and it can then be
**held to the runner** instead of to a sentence, which
`test_runner.py::test_the_cpu_re_run_happens_exactly_once_and_both_failures_are_recorded` now does,
asserting the counting backend's calls against the constant and against the literal both. A third
attempt appearing in `_placed` fails that case rather than silently making the boot check
under-protect the queue by a whole deadline.

The refusal names the product it computed, not just the two knobs, because the number an operator
has to move under is the hold and neither field spells it.

### Decision 2: the wait moves and the deadline does not, which is what the measurement decided

The queue addendum rejected this comparison because clearing it "means retuning a measurement
rather than correcting an ordering". The batch says which measurement can move. The deadline is
four times the longest whole subtask **and** four times the longest hold a full serialized batch
produced, 595.2 s, two independent routes to the same 2400 s, so lowering it would cut work that
was going to finish on the slow end of a 2.2x interval. The wait's own derivation, twice the
1624.6 s the last spawn of a serialized batch actually waited, comes to about 3250 s, so the wait
had roughly 350 s of slack and the hold needs 4800 s: the wait is the number with room to move and
raising it can never refuse a spawn that the old bound admitted.

`DEFAULT_ADMISSION_WAIT_S` becomes **7200 s**, stated in deadlines rather than in measured seconds:
three of them, the two a task can spend inside one admission plus one of margin so the relation is
a margin rather than a race. That is still an upper bound over both placements, about four times
the serialized batch wait and eight times the overlapping one, and it now covers **two** full
batches queued at once on either placement (about 3800 s serialized, about 2100 s overlapping),
where the hour it replaces covered only the overlapping case.

**What raising it costs**, said plainly: a spawn that was never going to be admitted is told so
after two hours instead of one. That is the only cost, because the bound refuses rather than
admits, and the case it delays is one where the delegated turn had already failed.

### Decision 3: the derivation stops being purely a measurement

The wait was derived from a measured batch alone, which is why it went stale in the direction that
mattered: the hold it has to outlast is a **relation** over another bound, and no batch measurement
would ever have revealed it. It is now derived from both, the larger term winning, and the larger
term today is the relation. A future retune of the deadline therefore moves the wait with it or
fails at boot, which is the property the whole series of orderings here exists to have.

### What did not change, deliberately

The run deadline, the stall ceiling, the token cap, the tool call bound and the batch cap are the
numbers they were. The zero-wait carve-out is untouched and still means never queue. The re-run
still gets a deadline armed fresh, which is the thing all three of the entry's candidates traded
against and the one this decision does not touch: a second attempt handed the remains of a spent
clock is a certain failure, and the fix here is to widen the room the two attempts sit in rather
than to shrink either of them.

### Distrust green

Five mutations, each applied to production code alone with the 2,878 tests of `brain/` re-run over
it (`pytest -q`, integration cases deselected), then restored and read back off disk.

| Mutation | Tests that fail |
| --- | --- |
| the hold is not multiplied, so the bare deadline is compared again | 2 |
| the comparison admits equality | 1 |
| `ATTEMPTS_PER_ADMISSION` retuned to 3 | 40 |
| `DEFAULT_ADMISSION_WAIT_S` restored to 3600.0 | 36 |
| a wait of zero is compared like any other | 3 |

The first row is the defect this addendum closes and it is narrow on purpose: the shipped pair
clears the bare comparison as easily as the doubled one, so what catches the factor is the case
written for it plus the ordering case's own boundary arm. The last two rows are the sweep's sanity
check rather than subtler mutations, both refusing the shipped defaults and failing every bare
construction of `SubagentsConfig` across the config, bounds, wiring, swap-wiring and vision-wiring
suites; a first row of 2 beside a third of 40 is what says the gate is narrow rather than absent.

**The second row was 0 on the first sweep, and that is the row worth reporting.** The rewritten
ordering case tested a hold of twice and of two and two thirds the wait and never a hold exactly
equal to it, so the strictness the neighbours' rule insists on was enforced by nothing. The
boundary arm was added because the sweep said so, not because the code changed.

### Consequences

- The relation this class states is the relation it refuses. The runbook's "that half is recorded
  rather than enforced" is gone, because there is no longer a half that is only recorded.
- A deployment that pinned both knobs to the old defaults now fails at boot, naming the hold. That
  is the intended loud failure and the same one the queue addendum accepted for the tightened wait.
- The delegated tier's own wall clock is on record as an interval rather than a point, so the next
  agent to retune one of these bounds knows which end to size on.

### Deferred by this addendum

The doubled hold is enforced but not *observed*: nothing counts how often the CPU re-run actually
fires, so the window this addendum widened its own estimate of is still sized from reasoning about
`_placed` rather than from a deployment's own numbers
([R-429](../refinements/tasks/429-nothing-counts-how-often-the-cpu-re-run-fires.md)). And every
bound in this series is a multiple of a subtask measured on an idle box, where a saturated one runs
the same subtask five to eight times slower, within 28% of the run deadline
([R-430](../refinements/tasks/430-the-bounds-are-sized-on-an-idle-box.md)).

## Named-conversation addendum (2026-08-25): which swap-path lines name a chat, and which name neither

The sixth-name addendum above put all eleven of the swap path's log records onto the turn's own
name and, reading each one, found that not one of them named the **conversation** that turn
belongs to. Seven other modules attach `session_id` and the tool audit sink writes it on every
call it records, so a grep by conversation returned a chat's recalls, its rank fallbacks, its
mid-turn failures, its summaries and every tool call it made, and nothing at all about the handoff
that chat asked for, which is the most expensive thing that happens in it. That was deferred as
[R-417](../refinements/tasks/417-the-swap-path-never-names-the-conversation.md), explicitly as a
question to be answered per line rather than per module. This addendum answers it.

### Re-derived first, and the entry's split holds exactly

The eleven records, at HEAD before this change: `swap_conductor.py` writes four
(`run_handoff`'s claim refusal at 137, `_prepare`'s opaque turn at 192, its unrostered deep tier
at 202, its store-still-holds-one at 218), `swap_settle.py` three (`fail` at 82, `_write_state` at
99, `_release_claim` at 113), `swap_recovery.py` one (`_fail_stranded_handoff` at 85), and
`brain_phase.py` two spellings serving three lines (`_report_cadence` at 214 and the shared
`extra` at 216, which the spilled and measured arms both spend). The two `_logger.exception` calls
in the conductor that carry no `extra` at all are not among the eleven and are not touched here.

The entry's cost claim is the rare one that survived checking. Six of the eleven already had the
conversation in scope: `run_handoff` and `_prepare` are both handed `session_id` as a parameter,
which covers four, and `HandoffSettler.fail` and `_fail_stranded_handoff` each hold a
`HandoffRecord`, whose `session_id` field has existed since the record did. The other five needed
it plumbed, exactly as filed: `_settle`, `_write_state` and `_release_claim` took a bare
`handoff_id`, and `_report_cadence` took a bare `handoff_id` too.

### Decision: all eleven name the chat, and the rule is what the line is about

Per line, as the entry asked, and the per-line reading converges on one boundary rather than on a
scattering:

**The conductor's four refusals: yes.** A refusal is about a turn somebody is waiting on. The
reader who arrives at one arrives from a chat, because a user said something went wrong, and the
turn id is precisely what that reader does not have. This includes the unrostered-tier refusal,
whose sentence is aimed at whoever configured the deployment: it is still one turn being refused,
and the deployment-wide statement of the same fact is a different line in a different module
(`_clear_deep`, said once per boot), which is where that reader is served.

**The settler's three: yes, all three.** They are one account of settling one handoff, and the
registry already pins them as a set for that reason. A conversation on the failure but not on the
store failures that explain it would hand a reader grepping the chat the symptom and hide both
causes. This is the plumbing the entry priced: `_settle`, `_write_state` and `_release_claim` now
take the `HandoffRecord` rather than its id, which both callers already hold.

**Boot recovery's stranded record: yes.** It is the one line here whose turn nobody is holding,
the process that ran it having died, so the chat is the only handle a reader can arrive with. The
residency lines beside it in the same module stay as they are and name neither identity, and that
contrast is the rule stated in code: `_clear_deep`, `_clear_peer` and `_settle_cortex` are about
the card, they name the `model` and carry no work identity at all, and there is no one turn or
chat they are about.

`residency_moves.py` is the boundary case worth naming, because it looks like a counterexample and
is not. Its lines are written during a handoff and one of them says so out loud (*a tier evicted
for the handoff could not be restarted*), yet they name only the `model`. Their subject is a
tier's state, which is the deployment's fact and not one chat's: the tier is down for everybody
who delegates until somebody fixes it, and the place that failure is recorded for a reader is
`StandingTiers` and the residency report, exactly as the cadence verdict's deployment-wide half
goes to `PaceSink`. So they stay as they are, by the rule rather than in spite of it.

**The deep phase's cadence lines: yes, and this is the one the entry doubted.** The argument
against is real: the decode rate is a fact about the machine, the line already carries seven
fields and eight on a spill, and a conversation is not a variable in the reading. What decides it
is which reader is left out. Every other swap-path line is a **failure** path; a handoff that
worked writes none of them. The cadence report is the only record a successful handoff produces at
all, so a chat that escalated, got its answer, and was slow about it has exactly these lines and
nothing else, and without the field it is unreachable from the conversation. The deployment-wide
reading of the same measurement already has its own destination that carries no chat: `_note_pace`
publishes the verdict to the residency record the seam's readiness report is composed from. The
two destinations differ in exactly the way they should.

So the rule, written in the swap runbook where a reader of these lines will meet it: **a line
about one handoff names both the conversation and the turn; a line about the card names neither.**
The field count is not a constraint here, and it was worth checking rather than assuming: the
bound in `log_fields.py` is on a rendered *value* and its seven-field headroom is about fields cut
at 2,048 characters, while every id on these lines is a short token.

### Decision 2: the two-turn line still names one conversation

The conductor's store-still-holds-one refusal names two turns, and both of them have a chat. It
names only its own. The held handoff's conversation is on the held handoff's own lines, every one
of which now carries it, and the qualified `active_turn_id` is the pointer that reaches them. A
second qualified field would put a fourth id on the line to save a reader one grep they can
already run. The qualified-name rule the sixth-name addendum wrote down is unchanged and still has
exactly one line following it.

### Decision 3: the registry holds the new half, and the runbook sample is corrected

`scripts/logcouplings.py`'s conversation entry grows from nine mentions to fifteen: the four swap
modules, and the swap runbook's two new sentences. The two counts are pinned the same way the turn
entry pins them, the conductor's four and the settler's three, each being one module's whole
account of one thing. The deep phase's two spellings are pinned at two here where the turn entry
left them a presence check, because these two are the only lines a successful handoff writes and
losing either loses a whole class of handoff from the chat's evidence. The four swap modules now
appear under both of the first two entries, so a refusal or a settle that names one identity and
forgets the other is caught by whichever count it broke.

The runbook's verbatim sample had a second defect, found while editing it and unrelated to the
conversation. It printed `turn_id=<turn id> reason="<what happened>"`, the order the call site
writes, and the shipped formatter prints fields in **name** order (`render_fields` sorts, ADR-0038
rendered-fields addendum), so what a container emits is `reason=... turn_id=...` and always was.
The sample is now the line the code really renders, in name order, with the conversation between
the two, and it says so. Nothing checks that class of claim, which is filed below. The registry's
needle for that line moved with it: it was anchored on the message plus the field, and the message
no longer touches either id, so it is anchored on the field alone.

A third instance of the same class was found and deliberately **not** fixed here. Two runbooks
tell an operator to run `grep turn_id=t-...`, and no id in this system has ever carried a prefix:
`new_turn_id` returns a bare `str(uuid4())` and the overlay mints a session with
`crypto.randomUUID()`. The `t-` and `s-` are the swap harness's fixture ids leaking into prose,
and the registry pins the sentence that spells one, so a gate is holding the fiction in place.
Fixing it spans two runbooks and two needles and wants its own pass; what this change owes is not
to add a third, so the sentence it adds writes `grep session_id=` with no prefix at all.

### Distrust green, over the brain suite

Eight mutations, each planted in production code alone, with the 2,878 tests of `brain/` re-run
over each. `pytest -q --no-cov` from `brain/`, one mutation at a time on the real tree, reverted
between.

| # | mutation | brain suite | crosscheck |
| - | -------- | ----------- | ---------- |
| 1 | the settler's failed line drops `session_id` | 2 failed, 2,876 passed | red |
| 2 | the settler's failed line swaps the two ids | 2 failed, 2,876 passed | green |
| 3 | the conductor's two-turn refusal drops `session_id` | 1 failed, 2,877 passed | red |
| 4 | boot recovery's stranded record drops `session_id` | 1 failed, 2,877 passed | red |
| 5 | the cadence reading arm drops `session_id` | 1 failed, 2,877 passed | red |
| 6 | the cadence no-reading arm drops `session_id` | 1 failed, 2,877 passed | red |
| 7 | the conductor's opaque refusal drops `session_id` | **2,878 passed** | red |
| 8 | the settler's `_write_state` drops `session_id` | **2,878 passed** | red |

Row 1 fails two cases rather than one for the reason the sixth-name addendum recorded: the only
settler line any test names is the one the runbook prints, and it is named by a parametrized case
that runs twice. Row 2 is the row that says what a suite can and cannot see. Swapping the two ids
leaves both field names in place, so the registry is silent by design and only a test reading the
whole line catches it, which is the same division the qualified-name decision relies on.

Rows 7 and 8 are the two that stay green, and they are the point of the table. Six of the eleven
records are pinned by a test (the settler's failed line, the conductor's two-turn refusal, boot
recovery's stranded record, and the deep phase's three, which its two spellings cover) and five by
the registry's counts alone: three of the conductor's four refusals, and the settler's other two.
That is the same six-to-five division the turn entry has, deliberately, and it is why both counts
are pinned rather than left as presence checks.

### Distrust green, over the crosscheck registry

Five planted disagreements, one at a time on the real tree, `python3 scripts/crosscheck.py` after
each. Counts here are over the registry rather than over any suite.

| # | planted disagreement | crosscheck |
| - | -------------------- | ---------- |
| 1 | the conductor's pinned count claims five where four are written | red, naming the file, `found 4, pinned 5` |
| 2 | `SESSION_FIELD` is renamed at its declaration | red, naming all eleven modules and both runbooks |
| 3 | the runbook's sample line loses the conversation | red on that needle, and it says the file still spells the name elsewhere, so the shape moved rather than the value |
| 4 | the runbook's grep sentence renames the field | red on that needle, with the same distinction drawn |
| 5 | the runbook's sample renames the turn field | red on the **turn** entry's re-anchored needle, which is what proves the re-anchoring still ties |

One trap is worth writing down for whoever mutates this registry next, because it produced a
phantom failure in three of these runs before it was noticed. `crosscheck.py` imports the registry
as a module, so a mutation planted in `scripts/` and reverted within the same second leaves a
stale `__pycache__` behind: source mtime has one-second granularity and the reverted file is the
same size, so the interpreter reuses bytecode that still carries the mutation. Three later runs
reported the count error from a mutation that was no longer on disk. Clear `scripts/__pycache__`
between plants, or a registry sweep will read its own ghosts.

### Consequences

- One grep by conversation now reaches the swap path. A chat's refusals, the settle that ended its
  handoff, the deep tier's decode rate for it and the boot that found it stranded carry the same
  id under the same name as its recalls, its summaries and its tool calls.
- A handoff that **worked** is visible from the chat for the first time, which is the half of the
  gap that attaching the field only to the failure paths would have left open.
- Two writes stopped taking a bare id and started taking the record, which is the shape that made
  the five plumbed lines cheap and is worth repeating: a line that names its work takes the object
  the work is, not one of its fields.
- The residency lines are now the written-down contrast rather than an accident. A future line
  about the card has a rule saying it names neither identity.

### Deferred by this addendum

Nothing compares a documented log sample against what the formatter would render, which is how
the swap runbook printed a field order the code never emits for as long as it did
([R-435](../refinements/tasks/435-a-runbook-prints-a-log-line-the-formatter-never-renders.md)).
The registry ties the field names in that sample to their declarations and says nothing about
their order, the message they follow, or whether the line is one the code could produce.

The deferral from the one-vocabulary addendum is unchanged and now covers a wider set: a new
module writing a work identity under a name nobody has registered is still invisible to the scan
([R-416](../refinements/tasks/416-a-new-log-line-can-name-its-work-anything.md)), and both of the
first two registry entries now name the same four swap modules, so an unregistered twelfth line
would be missed by both.

## Bare-id addendum (2026-08-25): the ids the runbooks tell an operator to grep carry no prefix

The named-conversation addendum above found a third instance of one class while it was fixing the
second, and left it: both runbooks told an operator to run `grep turn_id=t-...`, and no id this
brain has ever minted carries a prefix. That was filed as
[R-435](../refinements/tasks/435-a-runbook-prints-a-log-line-the-formatter-never-renders.md),
together with the open question the class raises, which is that nothing compares a documented log
sample against what the shipped formatter would render. This addendum answers both.

### Re-derived first, and one half of the entry was already closed

The entry's headline defect is not in the tree. `docs/runbooks/model-swap.md` prints the
failed-settle line in name order at HEAD (`reason`, `session_id`, `turn_id`), and says in the
sentence under it that name order is what the formatter emits. That correction landed with the
named-conversation addendum, hours before the entry was filed, and the entry says so in its own
second paragraph. What was left is the prefix fiction and the gate question.

The fiction re-derives exactly as filed. `new_turn_id` in `cortex_core/conversation.py` returns
`str(uuid4())`; `_uuid4_task_id` in `spawn.py` and `_uuid4_id` in `schedule_tools.py` do the same
for a delegated task and a scheduled item; the overlay mints a chat with `crypto.randomUUID()` in
`useOverlay.ts`. The `t-` and `s-` are `brain/packages/core/tests/swap_harness.py`, which sets
`SESSION = "s-handoff"` and `TURN = "t-handoff"` so its assertions read, and those two tokens
walked out of the suite into prose. The one id that really can wear a prefix is the fifth,
`call_id`, and only when the ticker mints it: `ticker.py` writes `id=f"schedule-{item.id}"`, which
the tools runbook already reads correctly as what was asked for rather than as what the brain
knows.

### Decision 1: the sentences are corrected, and each runbook says what an id looks like

Both greps lose the prefix and gain the id the reader actually holds: `grep turn_id=` on that id
in the swap runbook, `grep turn_id=` on one id in the tools runbook. The correction alone would
leave the next writer free to invent the shape again, so each runbook now states the fact at the
place a reader meets it. The tools runbook states it for the whole vocabulary, beside the
enumeration of the four work ids, and names the harness fixtures as fixtures so a reader who meets
`t-handoff` in a test knows what they are looking at. The swap runbook states it in one clause on
the line that tells you to grep, because that is the only id it hands you.

The fiction is worth naming precisely, because it is cheaper than it looks and more expensive than
it reads. `grep turn_id=t-` returns nothing on a real stream, which is a fast failure. The cost is
that an operator who runs it and gets nothing concludes the line is not there, which is the wrong
conclusion at the one moment the runbook is open.

**This document spells it twice more**, in the sixth-name addendum's first and third decisions,
each quoting the runbook sentence it was moving at the time. Those stay as written: an addendum
records what was decided on the day it was decided, and editing one to match a later reading would
leave a chain of decisions nobody can read back. This paragraph is what supersedes them. The
sentences those two decisions describe are the corrected ones above, the prefix in them is the
same fixture leak, and a reader who arrives at either should grep the field with an id rather than
with a shape.

### Decision 2: the registry moves onto the corrected sentences rather than off them

Two needles in `scripts/logcouplings.py` spelled the prefix, `"grep {value}=t-"` for the tools
runbook and "`` `grep {value}=t- ``" for the swap one, so the scan was holding the fiction in
place: correcting the prose alone would have failed the gate, and a correction that fails a gate
is a correction somebody reverts. They now carry the corrected sentence around the field rather than the
field plus the invented shape. A needle that quotes prose is the house style here already, the
task and call entries both doing it, and it buys exactly what is wanted: the prefix cannot come
back without the scan noticing.

### Decision 3: no re-rendering gate, and the sample's order is pinned by an anchor instead

The entry offered three shapes and asked for one to be argued. None of the three is built.

A scripts-side gate that parses fenced log samples and re-renders them through `PlainFormatter`
is the precise one, and it wants the brain importable from `scripts/`, which imports nothing today
and is the reason every scan there reads Python as text. That seam would be opened for one live
runbook sample. It also cannot render what the runbook actually prints: the sample's values are
placeholders, and `<what happened>` and `<chat id>` carry spaces, so the real formatter quotes
both and the doc quotes one, correctly, because `reason` is a sentence and an id is a token. A
re-rendering gate would have to be taught which placeholders stand for what before it could agree
with a sample that is already right.

A brain-side test asserting the runbook's text is the cheap one, and it puts a doc assertion in a
code suite where a reader of that suite will not expect one, for the same single sample.

Generated samples remove the question and cost a build step, which is a larger bill than the
exposure: two live samples exist, this one and the audit transcript this ADR records.

What is built instead is a third thing the entry did not list, and it is free. The conversation
entry's needle for that sample was `"{value}=<chat id>"`, the field alone. It is now
`'failed reason="<what happened>" {value}=<chat id>'`, anchored on the end of the message and on
the field that sorts in front of this one. Because the line has three fields and `reason` sorts
first, that anchor plus the turn entry's existing `"{value}=<turn id>"` pins the whole order: no
permutation of the three satisfies both, and a fourth field sorting anywhere before `session_id`
breaks the anchor too. The exact defect this entry is named for, a documented order the formatter
never renders, is now caught by the scan that already runs, with no new gate, no new import and no
build step. What it does not catch is filed below.

### Distrust green, over the constant scan

Seven mutations, each planted alone and `cd scripts && uv run python crosscheck.py --root ..` run
over the whole tree with `scripts/__pycache__` cleared between plants, then restored and compared
by digest. All seven restorations matched. The count is the untied readings the scan reports.

| Mutation | Tests that fail |
| --- | --- |
| the swap runbook's grep reverts to the `t-` prefix | 1 |
| the tools runbook's grep reverts to the `t-` prefix | 1 |
| the sample prints the fields in the order the call site writes them | 1 |
| the sample moves the conversation to the end of the line | 1 |
| the sample gains a field the call site never attaches | 1 |
| the conversation field is renamed at its declaration | 15 |
| the turn field is renamed at its declaration | 11 |

The three middle rows are the new property and the reason this addendum claims the order is held:
none of them was catchable before it, all three being rearrangements of a sample whose field names
were all still present and correct. Rows six and seven are the sweep's sanity check, a rename at
the declaration failing every reading of that constant across both trees, and a first row of 1
beside a sixth of 15 is what says the new anchor is narrow rather than absent.

### Consequences

- Both greps in both runbooks now work when typed. The one that did not was in the runbook a
  reader opens while a user is waiting.
- The order of the one verbatim log sample this repo prints is held by the gate that already runs,
  rather than by whoever last edited the line.
- A needle can pin a rendering's shape and not only its vocabulary. The anchor is a neighbouring
  field plus the fixed text in front of it, which costs one line of registry and no new machinery,
  and it is the pattern to reuse the next time a doc prints a line the code renders.

### Deferred by this addendum

The anchor pins one sample's order and not its membership. A field the call site stopped attaching
would leave the sample printing something the code never emits, and a field it started attaching
that sorts after `session_id` would be missing from the sample, and neither is visible to the scan
([R-438](../refinements/tasks/438-a-documented-log-sample-can-still-print-the-wrong-fields.md)).
The audit transcript this ADR records and the redaction sample in ADR-0038 are pinned by nothing
at all, being evidence of a live run rather than instructions.

## Sample-membership addendum (2026-08-26): a documented log line is held to the call that writes it

The bare-id addendum above pinned the ORDER of the one verbatim log sample it knew about and left
its membership open, on the argument that the anchor it built was free and membership was not.
This closes that, and the first thing the re-derivation found is that the premise was wrong about
how much was exposed.

### Re-derived first, and the count was low

The defect re-derives exactly as filed. `swap_settle.fail` attaches `session_id`, `turn_id` and
`reason`; `log_fields.render_fields` sorts, so the line prints `reason`, `session_id`, `turn_id`;
`docs/runbooks/model-swap.md` prints that. Delete the reason from the call and every gate stays
green with the runbook still printing it, because the two needles in `scripts/logcouplings.py`
read the runbook and nothing reads the call.

What was wrong is the sentence that says two live samples exist. A sweep for a rendered line in
every document here returns three inside `docs/runbooks/` and eleven inside two ADRs. The runbook
ones are the failed settle, the seam server's boot line in the WSL runbook, and the quarantine
pair in the scheduling runbook, and all three are instructions rather than transcripts: each is
printed to tell an operator what to expect on a stream. So the bill the earlier decision priced
against one sample was always being paid for three, and a fourth arrives every time somebody
documents a line.

### Decision 1: a scan of its own, `scripts/samplecheck.py`

Four things per sample have to agree: the level, the logger, the message and the field list. Fields
are compared as a sequence rather than as a set, so one comparison holds membership and order at once:
the printed order is name order and therefore a function of the key set alone, which means a
sequence comparison says everything a set comparison would and one more thing besides.

The scan is not folded into `crosscheck.py`, and the reason is that a field list is not a value.
That registry ties one value spelled in several places, compares it after reduction, and renders
it into a needle; a set of keys reduces to nothing a needle can spell, and the doc side of this
question is read rather than searched for. The house pattern for a new subject with a reader of
its own is a scan beside the others, which is what `stubcheck.py` and `backlogcheck.py` both are.
So `logsamples.py` reads what a page claims and `logcalls.py` reads what a call attaches, and the
gate compares the two.

`logcalls.py` is the one reader in `scripts/` that parses Python rather than matching it. An
`extra=` dict spans five lines at the failed settle, and a brace counter written to follow that is
a Python parser with the corners missing. `ast` executes nothing, so the seam the bare-id addendum
declined to open, an import of the brain from `scripts/`, stays shut: this reads the brain's text
the way every other scan here does and merely reads it with the right tool.

One line shape is refused rather than read, and named as itself. `logger.log(level, message, ...)`
takes its level from a variable, which the model host's request failure really does, so there is
no method name to read a level from and no level a sample could be held to. That is reported as
what it is instead of as a message nothing logs, because the message is in the module and a fault
denying it would send a reader hunting for text they can see.

### Decision 2: field names, and never field values

The re-rendering gate that addendum refused would have had to be taught which placeholder stands
for what before it could agree with a sample that is already right, `<what happened>` and
`<chat id>` both carrying spaces the real formatter would quote. That objection is answered by not
asking: this scan compares names and drops every value.

It is also the only answer compatible with a decision the constant registry already made. The WSL
runbook's `port=50051` is registered there as a dated reading rather than a coupling, on the
argument that a captured line stays true after the default it quotes moves. Holding values here
would overturn that from a second gate, which is how two gates come to disagree about one line.

### Decision 3: runbooks are contract, and an ADR's transcripts are evidence

The samples in this document and in ADR-0038 are declared evidence rather than contract, in
writing, which is the other half of what the entry asked for. An addendum records what was decided
on the day it was decided, and this document already refuses to edit an older one into agreement
with a later reading. A transcript is the same kind of thing: it is what a run printed on a day,
kept beside the decision it justifies. Holding it to today's code would make a record of the past
into a thing that must be edited to stay green, and the first such edit would destroy the evidence
it was kept for. A runbook is the other kind, written in the present tense and opened while
something is broken, so the walk reads `docs/runbooks/` and stops there.

The honest cost is stated rather than argued away: a reader who copies a field list out of a
recorded transcript is reading it as a statement about what the code emits today, and it is not
one. What answers that is the date on the addendum around it, not a gate.

### Decision 4: found rather than registered

There is no list of samples to keep current. The walk reads the runbooks and checks every fenced
line shaped like a rendered one, so a sample written tomorrow is held tomorrow. A registry would
have left each new one unpinned until somebody remembered it, which is the same silence this scan
closes, one indirection further back. What that costs is that a runbook quoting a line no brain
module writes fails rather than skips, and that direction is the intended one.

Two narrowings keep the find honest. A sample is a line inside a fence, never a sentence, because
reading prose would make every inline mention of a line owe a field list and push a writer away
from naming one at all. And the message ends at the first `name=` that opens outside a quoted
value, which is the rule a reader applies by eye; a message that spelled a `word=` of its own would
be reported as a message no call logs, which is loud and in the safe direction.

### Distrust green, over two suites at once

Fourteen mutations, each planted alone, both suites run, then the file restored from a copy and
compared by digest. All fourteen restorations matched. The first column counts
`scripts/tests/test_samplecheck.py`, `test_logsamples.py` and `test_logcalls.py`, 66 tests
together; the second counts `scripts/tests/test_crosscheck.py`, 144 tests, which is where the
order anchor this addendum builds on lives.

| Mutation | New | Anchor |
| --- | --- | --- |
| the runbook prints the three fields in the order the call site wrote them | 3 | 4 |
| the settle stops attaching the reason | 3 | 0 |
| the settle starts attaching a field that sorts last | 3 | 0 |
| the settle is demoted from a warning to an info | 2 | 0 |
| the runbook names a logger no module declares | 3 | 0 |
| a candidate inside a quoted value opens a field | 1 | 0 |
| a wrapped sample is not folded back into one line | 4 | 0 |
| the comment marker on a continuation is left where it stands | 4 | 0 |
| a line outside a fence is read as a sample | 1 | 0 |
| fields come back in the order the call wrote them | 8 | 0 |
| an `extra=` that is not a literal mapping is shrugged at | 1 | 0 |
| a runtime level is reported as a message nothing logs | 1 | 0 |
| the gate compares the level and not the fields | 6 | 0 |
| the walk reads every document rather than the runbooks | 5 | 0 |

The first four rows are the reading. Row one is the interaction: a reordered sample fails both
gates, so the anchor is intact and the new scan agrees with it rather than replacing it. Rows two
and three are the entry's own defect in both directions, and a 3 beside a 0 is the whole claim of
this addendum: neither was visible to the scan that already ran, and the anchor's blindness there
is a property rather than an accident of the alphabet. Row four is the level, which nothing held
before and which the runbook tells an operator to grep for.

The last row is worth reading twice. Widening the walk from the runbooks to all of `docs/` fails
five and reports seven misses on the committed tree, which is decision 3 paid for rather than
asserted. Three are the model host's `before` block in ADR-0038, whose messages ended in a colon
until the rendered-fields work took the colon off, so that record is a recording of the defect it
fixed. Three are the audit transcripts, whose sink builds its field dict in code rather than at
the call. One is the model host's request failure, written through `logger.log` at a level chosen
while it runs, which is the shape this reader rejects by name.

### Consequences

- Three operator-facing log samples are held to the calls that write them, and a fourth is held
  the day it is written.
- A field a call site stops or starts attaching now fails a gate rather than leaving a runbook
  printing a line nothing emits. That is the whole of what the order anchor could not see.
- `scripts/` gained the ability to read a call site rather than a declaration, without gaining an
  import of the brain. The next question of this shape has a reader to build on.
- The gate count in AGENTS.md moves from eight to nine, and the argument for a scan of its own is
  written above rather than left as a precedent to copy.

### Deferred by this addendum

The walk reads `docs/runbooks/` and holds every sample it finds, but nothing holds a runbook to
quoting the lines an operator actually needs: a line the brain writes and no runbook mentions is
invisible here by construction, and the coverage question is a different one from the agreement
question
([R-444](../refinements/tasks/444-nothing-says-which-log-lines-a-runbook-should-print.md)).

The new doc reader is also the third module in `scripts/` to spell the markdown fence for itself,
beside the backlog's heading reader and the commit-message linter, and this repo already holds
that a question several gates ask should be answered once
([R-445](../refinements/tasks/445-three-gates-each-spell-the-markdown-fence-for-themselves.md)).

## Audit-logger addendum (2026-08-28): the name this trail is selected by, held to what restates it

The recall trail's logger gained a declaration and a registry entry the day before this
([ADR-0038 named-logger addendum](ADR-0038-ranked-recall.md)), and that close said in as many words
that it left its sibling asymmetric: `cortex.tools.audit` was written once, as an argument of a
`getLogger` call, and restated by places that could not import it. This addendum is the other half,
built on the mechanism that one built.

### Re-derived first, and the count was one low

The entry named four places and the tree holds five. The four it named are the sink itself, the
tools runbook saying the dispatch is audited with one such line per call, the local-dev runbook
naming it among the two per-line trails worth knowing about, and the docstring of
`config_logging.py`, which names it to argue that INFO is not a knob here. The fifth is that
docstring's own suite: `test_config_logging.py` writes a record under the literal name and asserts
the rendered line back, because the claim being tested is what a line looks like once it leaves the
process. That is a restatement like the others and silent in the same way. The suite renames with
itself, both of its spellings moving together, so nothing in it goes red; what it would then prove
is that the shipped level carries a logger the brain no longer writes.

The entry's other claim, that a rename is green everywhere, is false for this trail in the same
loud way it was false for the recall trail, and the entry itself said as much: thirteen of the
tools package's fifty three checks read a line back through `caplog` under this name. The mutation table
below measures both halves rather than asserting them. The asymmetry that makes leaving the
documents plausible is the same one the sibling recorded: the suite goes green the moment its own
tests move onto the new name, and nothing then says the five documents and one sibling suite did
not.

### Decision 1: the sink declares the name it writes under

`cortex_tools/audit.py` binds `_LOGGER_NAME` and hands it to `getLogger`, which is what gives the
constant registry a declaration to compare the restatements against. The argument is the one the
recall trail's sink already made and is not re-argued here: a module-private constant asks nothing
of any importer, it puts the name where the rest of this brain's log vocabulary already lives, and
`scripts/logcalls.py` reads that spelling, so `samplecheck.py` goes on resolving a documented
sample of this trail against the call that writes it.

One consequence of doing it the second time is worth recording. Both self-named sinks now bind
their name above the call, so the literal spelling inside `getLogger` is a spelling this brain no
longer writes anywhere. `logcalls.py` keeps reading it, because such a call is legal Python that a
module may write tomorrow and a reader that stopped matching one would drop that logger out of its
answer without reporting it, but the guard test that used to assert the brain writes all three
spellings now says what is true: two spellings, one of them twice.

### Decision 2: the docstring and the suite are mentions, and the entry asked why

The entry asked one question before anything was built. Three of the places are the trail's own
instructions, and the others are a sibling module's argument about log levels and the test that
proves it, which is a different kind of claim: not an instruction to select a stream by this name.
Register them or leave them, it said, but say which.

They are registered, and the reason is that the registry holds places that restate a value rather
than claims of one kind. What a rename does to an argument is exactly what it does to an
instruction: the docstring would be arguing that the shipped level protects a durable record
written through a logger nothing writes, in the module a reader goes to when asking why the level
is fixed, and its suite would be demonstrating that argument on an abandoned name. The precedent is
already in the constant registry, where a docstring restating a subagent budget is tied for the
same reason, and the suite's two spellings are two needles rather than one counted twice, the call
it writes and the line it asserts having different shapes and a rename having to move both.

The half this cannot hold is stated in the part's own docstring rather than left for a reader to
find: that same docstring sentence names the recall trail in prose and not by its logger, so it is
tied to one of the two loggers it is about, and no rename of the other could be noticed in a file
that does not spell it.

### What did not change, deliberately

The module contract for the tools package gained a sentence about the declaration and did **not**
gain the name. `docs/modules/brain-tools.md` describes this line in full without ever naming the
logger, which the recall trail's contract does name; adding the name there would have been a fifth
restatement written in order to be gated, which is the gate choosing its own subject rather than
holding one it found. The contract points at `_LOGGER_NAME` instead, so a reader is one hop from
the name and the registry is holding what the repo already said.

No new part, either. The entry offered `trailcouplings.py` or a part beside it, and the logger
belongs in that file by its own docstring's test: it is one word of one line on one stream, which
is the seam that file was split on. It is now the couplings around both per-line trails, four
entries rather than three, and it stands at 177 lines.

### Distrust green, over three suites at once

Nine mutations, each applied alone to the committed tree with three suites re-run: the **1,426
checks of the gate suite** (`scripts/tests/`), the **53 of the tools package's**
(`brain/packages/tools/tests/`), which is the tree that pins this name from the other side, and the
**451 of the orchestrator package's** (`brain/packages/orchestrator/tests/`), which holds the
docstring's claim and is where the fifth restatement lives.

| Mutation | scripts | tools | orch |
| --- | --- | --- | --- |
| the sink renames the logger it writes through | **8** | **13** | 0 |
| the sink drops the declaration and spells the name inside the call again | **10** | 0 | 0 |
| the tools runbook keeps the name and loses the sentence around it | **7** | 0 | 0 |
| the local-dev runbook stops naming the logger among the two trails | **7** | 0 | 0 |
| the process entry's docstring stops naming the logger its argument rests on | **7** | 0 | 0 |
| its suite moves both its spellings onto another name at once | **7** | 0 | 0 |
| GATE: the entry drops the suite, and the suite renames with itself | 0 | 0 | 0 |
| GATE: the four document needles render the name alone | 0 | 0 | 0 |
| GATE: that, and the tools runbook loses its sentence | 0 | 0 | 0 |
| GATE: the sink keeps the declaration and spells the literal in the call too | 0 | 0 | 0 |

Row one is the entry in one line: thirteen reds where the trail is written, none at all in the
package that argues about its level, and now eight in the gate. Row two is why the declaration is
the thing being compared: take it away and the registry reports a site it cannot find rather than
going quiet.

Rows three to six are the restatements, one each. Row six is the place the entry did not count, and
its zero in the third column is the whole reason it needed holding: the suite renames with itself,
both spellings moving together, so it passes while proving the shipped level protects a trail
nothing writes. Row seven is what registering it buys, since without those two needles row six is
green everywhere.

Rows eight and nine are the same honest non-claim the recall trail's close recorded. A needle
rendering the name alone holds a rename exactly as well, each of these places spelling the name
once, so the sentence in each template buys nothing against the mutation this entry was filed for.
What it buys is row nine against row three: with bare needles, a document that keeps the name and
loses the instruction around it is green, where the templates fail seven.

Row ten is the one thing this addendum does not hold, found by a mutation that was meant to be row
two and measured zero instead. The registry compares the declaration against the places restating
it and never asks that the call passes it, so a sink keeping `_LOGGER_NAME` while spelling the
literal in `getLogger` again is green with two names to keep in step, and the day one of them moves
the documents are held to the wrong one. That is
[R-488](../refinements/tasks/488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md).


### Consequences

- A rename of the tool audit's logger fails `just check` on the day it is made, and the two
  runbooks, the docstring and the suite move with it or the gate names the ones that did not.
- Both of the brain's per-line trails are now held by name, which is what closes the asymmetry the
  recall trail's close opened rather than leaving it as a standing exception.
- The constant registry stands at 77 entries over 87 declaring sites and 257 mentions, in twelve
  parts, with the second per-line trail joining the first rather than arriving as a thirteenth.
- The literal `getLogger("name")` spelling is now supported and unwritten, which is recorded in
  `logcalls.py` and in the guard test rather than left for the next reader to discover.
- What the registry holds is the declaration, not that the sink's own call passes it, which the
  mutation table measures rather than assumes.

### Deferred by this addendum

The message stays where the logger was. `tool.invocation` is spelled in the sink, restated by the
tools runbook in prose and written by the orchestrator suite that proves the shipped level, and
held by nothing: the runbook describes the message instead of printing a rendered line, so
`samplecheck.py` never sees this trail at all
([R-487](../refinements/tasks/487-the-tool-audits-message-is-spelled-in-three-places-and-held-in-none.md)).

And the gate compares a declared name against what restates it without asking that the sink's own
call passes it, which the last row of the table above is: green, with two names to keep in step
([R-488](../refinements/tasks/488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md)).


## One-name addendum (2026-08-28): a module writes its logger name once

The addendum above ends by naming the one thing it does not hold, and it names it because a
mutation written to be a red row measured zero: a sink that keeps `_LOGGER_NAME` and spells the
same string inside `getLogger` again passes every suite and every scan. The constant registry ties
the documents restating a name to the declaration; nothing tied the declaration to the call. This
addendum closes that, and it is a rule about the shape rather than about either trail, which is why
it landed apart from the two closes that preceded it.

### Re-derived first, and the claim held

The mutation was applied to `cortex_tools/audit.py` on the committed tree and the tree stayed
green: `just check-crosscheck` (77 entries), `just check-samplecheck` (3 samples over 37 loggers),
`ruff` and `pyright` over the package, and the 504 checks of the tools and orchestrator suites
together. Nothing objects to a module holding two spellings of one name, and the unused constant is
not an unused import, so no linter sees it either. The entry's account of the reach was right as
written: both sinks are shaped this way and any sink named this way later would be.

### Decision: the rule is one name written once, and it lives with the reader that resolves them

`scripts/logcalls.py` already parses each `getLogger` call and already resolves a bare identifier
against its module's own top level, so it holds both halves at the point a mismatch is visible. It
now refuses a literal whose string that module also binds, naming the binding and asking the call to
pass it. A fault there is a fault of the sample gate, which runs unconditionally.

The narrow rule was chosen over the two wider ones the entry offered. "A module binding
`_LOGGER_NAME` must pass it" would name a convention, and a gate that runs over a convention has to
spell the convention's own identifier, which is a third spelling of the very thing this repo would
then want tied. "One name written once" needs no convention at all: it is a fact about a module's
own text, it reaches any module rather than the two sinks, and it catches the mutation that was
filed. Putting it in the constant scan was declined for the reason the scan is written the way it
is: that scan compares places against a declared value and knows nothing about what a logger is,
and teaching it would make the registry's data a place where a subject is decided.

What it deliberately leaves is stated below rather than implied.

### Distrust green, over the gate suite

Seven mutations, each applied alone to the committed tree, with the **1,429 checks of the gate
suite** (`scripts/tests/`) re-run. The two sink rows also ran the gate itself, which is where a
real violation surfaces, and the brain's own suites, which is where it does not.

| Mutation | scripts | `just check-samplecheck` |
| --- | --- | --- |
| the tool audit's sink spells the literal beside its declaration | **5** | **fails** |
| the recall sink spells the literal beside its declaration | **5** | **fails** |
| GATE: the rule never fires | **2** | passes |
| GATE: the literal branch returns before reaching the rule | **2** | passes |
| GATE: the bindings are matched by name rather than by value | **2** | passes |
| GATE: only the first binding is named | **1** | passes |
| GATE: the bindings are named in the order the module wrote them | **1** | passes |

Rows one and two are the row that measured zero in the addendum above, now five and five, on both
sinks rather than the one the mutation was written against. Neither moves the brain's own suites:
the 504 checks of the tools and orchestrator packages are green under row one, because a module
that spells one name twice writes exactly the lines it wrote before. That is the whole reason the
hole is worth a gate rather than a reader's attention.

Rows three to five are the rule itself, held by the two tests that describe it. Rows six and seven
are the fault's own text, held by the module that binds one name twice: a reader told to pass one
of two bindings, in whichever order the module happened to write them, is a reader sent to guess.

### Consequences

- A sink that inlines its logger name into the call, which is what an editor offers to do with a
  constant used once, fails `just check` on the day it is offered rather than on the day the
  literal moves.
- The literal `getLogger("name")` spelling stays read, and a module that writes one while binding
  nothing is untouched: the rule is about two spellings of one name, not about literals.
- The reader now stands at exactly 300 lines, which is the cap. The next rule it gains splits it,
  and the seam is the one its own docstring draws, between which module owns a logger name and what
  one call under it puts on its line.

### Deferred by this addendum

A module that binds one logger name and passes a different one is still green here: the rule sees
two names rather than one spelled twice, and neither the registry nor the sample gate asks which of
them the call passed unless a document happens to quote a sample of that trail. Reaching it means
either naming the declaration convention or teaching the registry what a logger is, both of which
this addendum declined
([R-489](../refinements/tasks/489-a-declared-logger-name-and-a-different-name-in-the-call.md)).


## Audit-message addendum (2026-08-29): the word every audited line opens with

The addendum above ends by naming what it left, and this is that: the message sitting beside the
logger on the same rendered line. `tool.invocation` is what an operator looks for once the logger
has selected the stream. It is written in `cortex_tools/audit.py`, restated by
[tools-mcp.md](../runbooks/tools-mcp.md), which says the line carries this and nothing else before
its fields, and written twice more by `test_config_logging.py`, which logs it under the trail's name
to prove the shipped level is not a knob. Nothing tied the three. A rename in the sink left the
runbook describing a message nothing writes and that suite passing on both its spellings at once,
having renamed with itself.

### Re-derived first, and the option worth having ruled out by measurement

The entry named three options and asked for an argument before anything was built. The one worth
having was a rendered sample in the runbook, which would have brought the whole sample gate to bear
on the level, the logger, the message and the fields at once and made a second constant unnecessary.
So it was tried on the committed tree rather than reasoned about. A fenced line of this trail was
added to the runbook and `just check-samplecheck` refused it:

```
docs/runbooks/tools-mcp.md:221: the sample brain/packages/tools/src/cortex_tools/audit.py:93: extra= is not a mapping written out at the call
```

That is a defect in neither gate. `LoggingAuditSink` builds its fields across statements and by
condition: a success carries a size where a failure carries an error, and four of the five
identities ride only when the dispatch had them. `logcalls.py` reads a field list off an `extra=`
written out at the call and refuses anything else, deliberately, and this line has no single field
list to be held to in the first place. **The sample gate cannot reach this trail at all**, which is
a harder answer than the entry's own, that a rendered sample would cost a captured line that has to
stay honest, and it is recorded on
[R-444](../refinements/tasks/444-nothing-says-which-log-lines-a-runbook-should-print.md), whose
question about which lines a runbook owes an operator now has a second half: which lines the
mechanism can hold at all.

Doing nothing was the third option, and it fails on what the runbook says. "That line is a bare
`tool.invocation` message followed by its fields" is how a reader knows what to look for, in the
present tense, in a document opened while something is broken. That is an instruction and not prose
about the trail.

The entry's account of the code was otherwise accurate: three places, four spellings, and no
declaration to tie them to. One file it leaves out is right to be left out.
`brain/packages/tools/tests/test_audit.py` spells the word five times and asserts the rendered line
rather than writing the message, so a rename in the sink fails it instead of moving with it, which
is the difference between it and the level suite and is what row one measures.

### Decision: a second constant in the sink, handed to the call that writes the line

`_MESSAGE` sits beside `_LOGGER_NAME` and is passed to `_logger.info`, which is the shape the
logger's own close took and the shape `cortex_orchestrator/abandon.py` already had, for the reason
its comment gives: a suite asserts the line an operator greps for. It is passed rather than left
beside a literal of itself because the one-name addendum made that rule for logger names, and a
module spelling one word twice has two of them to keep in step. The registry entry is the fifth in
`trailcouplings.py` and holds the runbook sentence and the suite's two spellings, which are two
needles rather than one counted twice: the call the suite makes and the line it asserts have
different shapes, and a rename has to move both.

A constant added for a gate's benefit is a cost this repo pays only with an argument. The recall
trail needed none, its declaration already sitting in a reader outside the brain; this one has no
reader, and the paragraph above is why it has no sample either.

### The two entries meet on one asserted line, and each renders its own half

`INFO:cortex.tools.audit:tool.invocation tool=read` spends both of this trail's registered words at
once. The logger's needle used to spell the message as fixed text, which made registry data a place
restating a value it does not declare: a message renamed everywhere would have been reported against
the logger, sending a reader to the constant that did not move, and the repair would have been an
edit to the registry rather than to the tree. Each needle now renders its own value and anchors on
the punctuation the format puts around it, the logger on the colon that closes it and the message on
the colon that opens it together with the field that follows.

### Distrust green, over three suites at once

Seven mutations and a control, each applied alone to the committed tree with three suites re-run and
the gate itself run beside them: the **1,432 checks of the gate suite** (`scripts/tests/`), the
**53 of the tools package's** (`brain/packages/tools/tests/`), which pins this word from the other
side by asserting rendered lines, and the **451 of the orchestrator package's**
(`brain/packages/orchestrator/tests/`), which holds the level argument and writes the word twice.

| Mutation | scripts | tools | orch | `check-crosscheck` |
| --- | --- | --- | --- | --- |
| CONTROL: nothing edited | 0 | 0 | 0 | passes |
| the sink renames the word it opens every audited line with | **10** | **5** | 0 | **fails** |
| the tools runbook keeps the word and loses its sentence | **9** | 0 | 0 | **fails** |
| the level suite moves both its spellings at once | **10** | 0 | 0 | **fails** |
| GATE: the three needles render the word alone | **1** | 0 | 0 | passes |
| GATE: that, and the tools runbook loses its sentence | **1** | 0 | 0 | passes |
| GATE: the logger's needle spells the message as fixed text again | **1** | 0 | 0 | passes |
| GATE: the sink keeps the declaration and spells the literal too | 0 | 0 | 0 | passes |

Row one is the entry in one line, and its shape is the argument for the whole change: loud where the
word is written and in the package that asserts the rendered result, silent in the runbook and in
the suite that proves the level, both of which go on describing a message the brain stopped writing.
Rows two and three are the restatements one each, and row three is the one the entry called out,
since the level suite spells the word twice and moves both together.

Rows four to six are all the same single red, the test holding the suite's asserted line to the
word that moved on it, and the gate itself passes in each: what these three measure is which entry
a fault lands on rather than whether a rename is noticed at all. Rows four and five are the honest
non-claim the two closes before this one recorded, restated for a case where it does not quite
hold. A needle rendering the word alone holds a full rename exactly as well, and the sentence in
each template buys row five against row two, a document that keeps the word and loses the
instruction around it, nine reds against one. What a bare needle does lose is the suite's
half-applied rename: two occurrences in one file collapse into a single presence check, so the
asserted line may move while the call above it goes on satisfying the needle. Row six is the
relaxation from the other side, putting the message back into the logger's needle as fixed text.

Row seven measured zero and is a finding rather than a proof, exactly as the last row of the
addendum above was. A sink that binds `_MESSAGE` and spells the literal in the call as well is green
everywhere, the one-name rule reaching a logger's call and stopping one word short of a message's.
That is
[R-490](../refinements/tasks/490-a-declared-log-message-may-be-spelled-again-in-the-call-that-logs-it.md).

### Consequences

- A rename of the word the tool audit's lines open with fails `just check` on the day it is made,
  and the runbook and the level suite move with it or the gate names the one that did not.
- Both words on this trail's rendered line are held now, as all three of the recall trail's are,
  which closes the last of the asymmetries the two closes before this one opened.
- The constant registry stands at 78 entries over 88 declaring sites and 260 mentions, in twelve
  parts, the second per-line trail carrying two of them rather than one.
- Registry data no longer spells a value another entry declares, which is a rule this addendum
  states and a test holds rather than a tidiness anyone has to remember.
- A line whose fields are built by condition cannot be documented as a rendered sample. That is a
  property of the sink rather than of this trail, and it is written down now where a runbook author
  meets it rather than discovered at the gate.

### Deferred by this addendum

The declaration is compared against the places restating it and nothing asks that the sink's own
call passes it, the one-name rule reaching `getLogger` and no other call
([R-490](../refinements/tasks/490-a-declared-log-message-may-be-spelled-again-in-the-call-that-logs-it.md)).

And the fault a writer meets on trying to sample one of these lines names the sink rather than
saying the line is unsampleable, which is recorded against the coverage question already open
([R-444](../refinements/tasks/444-nothing-says-which-log-lines-a-runbook-should-print.md)).


## Declared-name addendum (2026-08-29): what already held a declaration to its call

The two addenda above each end by naming what they left, and both name the same thing: the registry
compares a sink's declaration against the places restating it and never asks that the sink's own
call passes it. `getLogger(_LOGGER_NAME)` and `_logger.info(_MESSAGE, ...)` carry an identifier, and
an identifier says nothing about the string inside it, so a module binding one name and passing a
different literal is two names rather than one spelled twice, which is exactly the shape the
one-name rule sees and lets through. The entry asking for this asked for an argument before a rule
was built. The argument turned out to be about the entry's own premise.

### Re-derived first, and the premise did not survive

The entry says that state is green "unless some document happens to quote a rendered sample of that
trail". It is not green. The mutation was applied alone to the committed tree on each sink in turn,
and `just check` is red for both, in two places neither of which was written for this:

- **`scripts/tests/test_logcalls.py`** carries a guard on that reader's own fixtures, asserting that
  the brain declares `cortex.tools.audit` in the tool audit's sink and `cortex.memory.recall` in the
  recall trail's. `logcalls.loggers` answers with the name the **call** carries, so a call passing
  another literal fails those lookups with a `KeyError`. Holding a declaration to its call is a
  second job that guard has always done and that nothing said it was doing.
- **Each sink's own package suite** asserts a whole rendered line, `LEVEL:logger:message` followed
  by the fields. The same mutation is 13 reds in the tools package and 9 in the memory package, and
  the message half of the same question is 5 in the tools package.

The scans stay green under all three, which is the half the entry saw: `check-crosscheck` compares
each declaration against the documents restating it, and `check-samplecheck` cannot reach either of
these trails at all, one sink's fields being built by condition and the other's line being one no
runbook prints.

### Decision: no rule, because the rule exists in effect

The entry's own criterion was whether the gap is worth a rule at all, and the answer is that the gap
is not there. A second mechanism asserting what an existing one asserts cannot catch a fault the
first misses, and it doubles what an honest rename has to move, which is a cost paid for nothing.
The shape the entry proposed as cheapest, marking a registry site as a logger name so the sample
gate could read that one fact, is declined for that reason and for the one the one-name addendum
already gave: it puts a subject inside data whose every other entry is a value and the places that
spell it.

### What did ship: the accident, said out loud

Two unrelated assertions happened to hold one property between them, and neither file said so. A guard
rewritten to assert about the sinks rather than about these names, or four assertions folded into a
helper taking the logger as a parameter, would each remove the property without a failure, and the next
renamed call would land in a tree that reads as though it were covered.

So the places already holding it are registered. The two logger entries in `trailcouplings.py` gain
a mention on that guard, rendered as `names["{value}"]`, which is the lookup a call passing another
literal fails. The audit message entry gains one on that sink's own suite, rendered as `:{value} "`,
which is the message half and is held by that suite alone, the guard reading loggers and asking
nothing about a message. The recall trail's message needs none: its sink spells the word inside the
call, and that call has been a registered mention since the trail was tied. The guard's docstring
now names the second job it does, so the two spellings a reader might otherwise tidy away are
labelled load bearing.

Nothing was written in order to be gated. Both assertions predate every entry in that part, which is
the line the audit-logger addendum drew when it declined to add a fifth restatement to a module
contract for the gate's benefit.

### The closing quote in the message needle

`brain/packages/tools/tests/test_audit.py` proves that a hostile call id cannot forge a second line
by sending one through a field, so a whole rendered head of this trail sits in that file inside a
longer string no assertion is about. A needle ending at the word would go on being found there after
all four real assertions had moved, which is a needle that cannot fail. It ends at the quote closing
the literal instead, and the last row below holds that.

### Distrust green, over four suites at once

Eight mutations and a control, each applied alone to the committed tree, with four suites re-run and
the gate run beside them: the **1,436 checks of the gate suite** (`scripts/tests/`), and the **544
of the three brain packages** that write or assert one of these lines, the tools package's 53, the
memory package's 40 and the orchestrator package's 451
(`brain/packages/{tools,memory,orchestrator}/tests/`), counted together in one column since a row
failing two of them at once is what half the table is about.

| Mutation | scripts | brain | `check-crosscheck` |
| --- | --- | --- | --- |
| CONTROL: nothing edited | 0 | 0 | passes |
| the audit sink passes a logger literal beside its declaration | **1** | **13** | passes |
| the recall sink passes a logger literal beside its declaration | **1** | **9** | passes |
| the audit sink passes a message literal beside its declaration | 0 | **5** | passes |
| the guard stops naming the audit logger | **12** | 0 | **fails** |
| the audit suite stops asserting the word before its fields | **11** | **4** | **fails** |
| GATE: the guard mention is dropped from both logger entries | **2** | 0 | passes |
| GATE: the asserted message mention is dropped | **1** | 0 | passes |
| GATE: the message needle stops at the word rather than the quote | **1** | 0 | passes |

Rows two to four are the entry in three lines, and they are a finding rather than a proof of
anything built here: the state the entry calls green is red in the gate suite for either logger and
in the sink's own package for either logger and for the message, and nothing in this change moves
them. They also say the faults land where a reader can act: the guard names the logger it could not
find, and a package suite prints the line it expected beside the line it got.

Rows five and six are what registering buys, and neither had a scan behind it before. A guard
retargeted onto another name and a suite that stops asserting the word are each a green tree with
the property gone, and each is now a `check-crosscheck` failure naming the entry whose declaration
lost its holder. Their scripts counts are large for a reason worth reading rather than counting:
both mutate a real file that many registry entries name, so every control test that copies the tree
unedited and both tests running the scan over the repo itself fail beside the two written for this.

Rows seven to nine are the needles themselves. Seven and eight are the mentions removed, which turns
rows five and six back into the silence they were, and their counts are exactly the tests written
for them. Nine is the anchor: with the needle ending at the word, the forged line that suite feeds
through a field satisfies it, so a suite whose four real assertions had all moved would go on
counting as holding the message.

### Consequences

- The property the entry asked for is held, was held before this change, and is now named in the two
  files holding it rather than being a coincidence of how two tests happen to be written.
- The constant registry stands at 78 entries over 88 declaring sites and 263 mentions, in twelve
  parts. Three of those mentions are a kind of far side this part had not carried: a place that
  restates nothing and asserts what the code did.
- A gate suite's own fixture guard can be load bearing for something outside itself. This one is,
  for two trails, and the way that is recorded is a coupling plus a sentence in its docstring rather
  than a rule somewhere else.
- A backlog entry's account of the tree is a claim with a date on it. This one was accurate when it
  was written about a registry and wrong about `just check`, because the entry was reasoning from
  the scans and the reds were in two suites nobody had connected to the question.

### Deferred by this addendum

The guard names its two sinks by hand, so a third self-named sink is held by nothing until somebody
remembers to add a line, where `flagcheck.py` beside it derives its set from the tree
([R-491](../refinements/tasks/491-the-guard-holding-a-declared-logger-to-its-call-names-two-sinks-by-hand.md)).

The one-name rule still reaches a logger's call and stops one word short of a message's, which is
untouched here and stays its own question about a module's own text
([R-490](../refinements/tasks/490-a-declared-log-message-may-be-spelled-again-in-the-call-that-logs-it.md)).

## Derived-sink addendum (2026-08-30): the guard reads its sinks off the tree

The addendum above ends by naming what it left: the guard holding a sink's declaration to the call
handed it looked up two logger names by hand, so a third self-named sink was held by nothing until
somebody remembered to add a line. That is the shape the ADR-0029 addendum on deriving the set a
rule runs over is against, and the shape `flagcheck.py` already answers by deriving its
servers from the stack's own wiring. The entry asking for this asked for three things to be weighed
before anything was built, and all three are decided below on what the tree does.

### Re-derived first, and the premise held in both directions

A third self-named sink was written into the committed brain, a module binding `_LOGGER_NAME` and
handing `getLogger` a different literal, which is the exact fault the two hand-written lookups
exist to catch on the sinks they name. The gate suite passed, `check-crosscheck` passed, and
`check-samplecheck` passed, reporting one more logger than before and asking nothing about it. The
same probe written the other way, binding the name under `_TRAIL_NAME` and passing that, is equally
green. So the entry is right about its own subject: what holds two sinks holds two sinks.

### Decision 1: two readings compared as sets, which holds every direction at once

`logcalls.loggers` already answers with the name the **call** carries, against the file carrying it.
A sink that named itself is therefore a logger that is not its own module's dotted path, which is a
reading of the tree rather than a list. The other reading is what the modules themselves bind under
`_LOGGER_NAME`, walked out of the same packages. The guard holds the two dictionaries equal.

That single comparison is what covers the four shapes a hand-written lookup could not:

- A call passing another name is a self-named logger the brain declares nowhere.
- A declaration the call stopped passing, `getLogger(__name__)` beside a live `_LOGGER_NAME`, is a
  declaration the documents are still tied to and nothing writes through. The hand pair caught this
  one; a guard deriving only the first direction would not, which is why the comparison is an
  equality and not a containment.
- A sink naming itself with a bare literal has no declaration for the registry to tie documents to,
  and is now told so on the day it is written rather than when a document quotes it.
- A sink binding its name under some other identifier falls outside the naming the first set is
  read by, which is the circularity the ADR-0029 addendum on that question warns about: a rule
  whose domain is the convention it checks cannot fail for the misspelling it exists to catch. The
  domain here is structural, "a logger that is not its module's path", and the convention is what
  the rule then asks for, so the misspelling is a red.

### Decision 2: it belongs in the suite, and not in `logcalls.py`

The entry asked this first, since a rule in the reader would arrive with the split its docstring
draws, that file standing at exactly the line cap. The split is not what decides it. `logcalls.py`
is a reader of any tree, and its one existing rule, that a module may not spell one logger name
twice, is about an ambiguity in the reading itself: two spellings leave the registry no single
declaration to tie documents to. Nothing about `getLogger("cortex.x")` is ambiguous, so refusing it
would not be the reader answering better. It would be the reader legislating this brain's naming
over every fixture tree it walks, and the fixture it would break first is the one written a slice
ago to keep a bare literal readable, whose argument is that dropping a logger from the answer with
no report is worse than a spelling nothing exercises. Refusing loudly answers that argument, which is why the rule is
worth having somewhere; it does not answer why a reader should carry it. The claim is about the
committed brain, so it sits with the other claims about the committed brain, in the section of
`scripts/tests/test_logcalls.py` written for them, where the guard it replaces already lived.

### Decision 3: what the registry ties is the naming, not a sink

The entry's third question was whether a derived guard leaves the registry a spelling to tie the
documents to. It does, and it was never the guard's: the documents are tied to `_LOGGER_NAME` in
each sink, which has not moved. What the guard's two literals gave the registry was a different
thing, a far side that made deleting or retargeting the guard loud, and a derived guard spells no
logger name for such a needle to hold.

So the two logger entries drop their mention of the guard and a sixth entry is added beside them
whose value is the identifier `_LOGGER_NAME` itself: declared by the guard, which is the file that
has to spell the naming it reads its set by, and spent by both sinks and by both module contracts,
each of which already explains why its sink declares the name rather than writing it in the call.
One entry now covers every self-named sink there will ever be, where the old pair covered exactly
the two it named. The registry rejects an entry whose places are all one language, and the two
contracts are what make this one a coupling rather than a Python file agreeing with itself; both
sentences predate this change, so nothing here was written in order to be gated.

### What this does not reach, deliberately

A module that declared its own dotted path as `_LOGGER_NAME` and passed it would be read as
module-named by the first set and as a declaration by the second, and would go red. That is the
right answer rather than a false one: a module whose logger is its own path writes `__name__`, and
a brain that started restating paths would be spelling in a constant what the language already
says.

### Distrust green

Eight mutations and a control, each applied alone to the committed tree, measured over the **gate
suite** (`scripts/tests/`), 1,453 checks before this change and 1,455 after, with
`check-crosscheck` run beside it. The two count columns are the whole argument: the first four rows
are what the property was worth before and after, and the last three are what the new needle holds.

| Mutation | before | after | `check-crosscheck` |
| --- | --- | --- | --- |
| CONTROL: nothing edited | 0 | 0 | passes |
| the audit sink passes a logger literal beside its declaration | **1** | **1** | passes |
| the recall sink stops passing the name it declares | **1** | **1** | passes |
| a third self-named sink names itself in the call | 0 | **1** | passes |
| a third self-named sink binds its name under another identifier | 0 | **1** | passes |
| GATE: the guard stops asking for the declaration | n/a | **12** | **fails** |
| GATE: the two sink mentions are dropped from that entry | n/a | **1** | passes |
| GATE: the two contract mentions are dropped from that entry | n/a | **2** | passes |

Rows two and three are the property the old pair held, held identically by the new guard, which is
the floor a replacement has to clear before anything else counts. Rows four and five are what the
entry was about, and they are the whole of what this change buys: zero to one, on a sink nobody has
written yet, in both of the shapes such a sink can be written wrong.

Row six is the naming, and its count is large for a reason worth reading rather than counting: the
guard's own assertion fails, and so does every test that copies or scans the real tree, the entry
having lost all four of its needles at once. Rows seven and eight are those needles measured
apart, and eight carries a second red beside its own test, the registry's rule that an entry's
places may not all be one language, which is what the module contracts are doing in this entry.

### Consequences

- A self-named sink written tomorrow is held to declaring its logger and passing that declaration,
  the day it is written, with no line to remember to add.
- The constant registry stands at 79 entries over 89 declaring sites and 265 mentions, in twelve
  parts. One of them ties an identifier rather than a value a line carries, which is new: what a
  derived rule reads its set by is a spelling several places have to share like any other.
- A gate suite's guard can be the right home for a rule about the tree. The reader it sits beside
  answers questions about any tree, and the difference between the two is what decided where this
  went.

### Deferred by this addendum

The sink's declared message is where the logger was: `_MESSAGE` is held to the call handed it by
one registered assertion in one package suite, named by hand, and a second sink declaring a message
would be held by nothing. The derivation that closed the logger half has no reader behind it there,
`logcalls.logged` matching a call whose first argument is a literal
([R-503](../refinements/tasks/503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md)).

## Handed-message addendum (2026-08-30): the reader reads both spellings, and refuses a doubled one

Two entries asked one question from opposite ends. One asked whether a module may spell its own log
message twice, binding a constant and writing the same word inside the call
([R-490](../refinements/tasks/490-a-declared-log-message-may-be-spelled-again-in-the-call-that-logs-it.md)),
and named the question to decide first: is the rule about any log call's message, or only about a
call whose binding some document restates? The other asked what holds a declared message to the
call handed it, the logger half having just been derived while the message beside it stayed with one
assertion in one package suite
([R-503](../refinements/tasks/503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md)).
Both are answered here, and the answer to the second is what decides the first.

### Re-derived first, and both entries were understated

Three facts came out of reading the tree rather than the entries.

**The shape R-503 called hypothetical is already five calls.** It supposed a third sink written the
way the tool audit is written. The brain has five such calls in three modules today:
`cortex_tools/audit.py` binds `_MESSAGE` and hands it to `_logger.info`; `cortex_orchestrator/
abandon.py` binds `ABANDONED_MESSAGE` and hands it to `_logger.warning`; and
`cortex_core/brain_phase.py` binds three, the spill warning and the two readings beside it, and
hands each to its own call. Two of the four outside the tool audit are held about as firmly as a
thing can be, their package suites importing the constant and asserting the emitted record against
it, which no gate arranged and nothing states. The other two are held by nothing and restated by
nothing, which is why they cost nothing.

**The reader really cannot see any of them, and that is a live fault rather than a gap.**
`logged` matches a call whose first argument is a string literal, so it answers `audit.py logs no
message 'tool.invocation'` about the module that visibly logs it. The consequence is not a missing
rule, it is `check-samplecheck` failing on a correct document: a runbook that printed a rendered
sample of any of those five lines would be told the brain writes no such message. The spill
warning's own comment sends a reader to `docs/runbooks/model-swap.md`, so this fell on exactly the
lines a runbook has the most reason to quote, and the gate's answer would have pushed the author
away from quoting them.

**The naming R-490 hoped to lean on does not exist.** The brain binds about twenty top-level
strings whose names say `MESSAGE` or `MSG`, and only five of them are log messages. The rest are
model-facing sentences: `BUDGET_EXHAUSTED_MSG`, `REDUNDANT_MSG`, `DENIED_MSG`, `TAINTED_TASK_MSG`
and a dozen more, each a refusal a tool call is answered with. So the mechanism that closed the
logger half is unavailable here: that guard reads a structural set off the calls and compares it
with the names bound under `_LOGGER_NAME`, and a message has no `_LOGGER_NAME`. Inventing one would
place a new convention one letter from a large group of names meaning something else, and holding
it would fail every model-facing constant in the core.

### Decision 1: the reader learns the second spelling, and the sample gate is what wanted it

A message is written out at the call or handed to it by name, and the formatter renders the string
either way, so the line on the stream is identical and the page quoting it cannot tell which the
module wrote. That settles what a sample of such a line is: the same sample as any other. There was
never a second question there, only a reader that could not follow the second spelling.

So a bare name is resolved against the module's own top level and nothing wider, by
`moduleconstants.py`, which is the reading `loggernames.py` already makes of a logger claimed the
same way, and the two halves of this reader now follow a word the same distance. A name from an
import stays unmatched rather than chased, for the reason that paragraph gives: an importer of the
brain is what `scripts/` may not become. A message assembled at the call is still not a message a
page could quote.

### Decision 2: the rule is about any log call's message, because that domain is a call

R-490 offered two domains and warned about the wider one: a message is a sentence, so a module that
binds some string for another purpose and happens to log the same literal would be refused a
spelling nothing is wrong with. The narrow domain, a binding some document restates, is the
registry, and it needs the registry to say which of its sites is a message, which it does not.

The wider domain turns out not to have the cost the entry feared, because it is not a domain over
names at all. Nothing is asked about a binding: a literal has to be the message of a log call
before the rule looks at it, and only then is the module's own top level consulted for the same
string. A module that binds a refusal for a model to read and logs something else is never in the
domain. What the rule then says is what the one-name rule beside it says: only the declaration is
what the constant registry ties documents to, so a module holding both spellings can move the
literal alone and leave those documents restating a word the brain no longer writes. The measured
surface is the argument's other half: the brain writes 90 literal log messages today, and not one
of them is also bound at its module's top level, so the rule rejects nothing that exists and holds
every module written tomorrow.

It runs over the tree rather than over the modules a document names. `messages` walks every
package's `src/`, and `samplecheck.py` calls it beside the loggers it already collected, so a
doubled spelling is refused the day it is written rather than the day a runbook happens to quote
that line. The success line states the messages it read for the reason it already states the
loggers, and a brain that logs none is a failure rather than a quiet pass.

### Decision 3: the split R-490 predicted, along the seam its docstring had drawn

`logcalls.py` stood at exactly 300 lines, which the entry named as a cost with a floor, and it was
right. The seam is the one that module's own opening sentence drew: which module owns a logger
name, and what one call under it puts on its line. `loggernames.py` is the first half and
`logcalls.py` keeps the second along with the reading of the brain's source both stand on. The
guard holding a self-named sink's declaration to its call moves with the half it is about, and the
constant registry's entry on that guard follows it, which is one line of data and the only thing
the move cost anything.

### What this does not reach, deliberately

A sink that binds `_MESSAGE` and hands its call some OTHER word is still two words rather than one
spelled twice, and neither rule sees it. What refuses that today is what refused it this morning:
`brain/packages/tools/tests/test_audit.py` asserts four whole rendered lines, and the registry names
that assertion so it cannot be deleted without a failure. A guard deriving that would have to
identify which declaration is a log message, which the section above shows this brain cannot say,
so the residue is written down with the two paths worth weighing rather than guessed at
([R-504](../refinements/tasks/504-a-declared-message-and-a-different-word-in-the-call.md)).

### Distrust green

Seven mutations and a control, each applied alone to the committed tree, measured over the **gate
suite** (`scripts/tests/`), 1,455 checks before this change and 1,464 after, with
`check-samplecheck` run beside it and reported in its own column.

| Mutation | before | after | `check-samplecheck` |
| --- | --- | --- | --- |
| CONTROL: nothing edited | 0 | 0 | passes |
| the tool audit writes its message as a literal beside the binding | 0 | **3** | **fails** |
| a module no runbook quotes does the same | 0 | **3** | **fails** |
| a runbook prints a rendered sample of a line handed its message by name | **2** | **0** | **fails before, passes after** |
| GATE: the reader stops refusing a doubled message | n/a | **3** | passes |
| GATE: the reader stops resolving a name | n/a | **2** | passes |
| GATE: the sample scan stops reading the messages | n/a | **1** | passes |

Rows two and three are R-490's question measured: the doubled spelling was green everywhere, and is
now three reds and a failing scan whether or not any document quotes that line. The third row is the
one that shows the rule reaching a module the sample gate never opens, which is what running it over
the tree buys.

Row four is the fault this slice fixes, and it runs the other way: the mutation is a correct
document, and it is the tree BEFORE this change that fails on it, `check-samplecheck` exiting 1
with the miss `brain_phase.py logs no message`. After, the sample is checked like any other and
the gate is quiet. A gate that fails on a correct document is the most expensive kind to live
with, because the author trusts the gate and edits the document back to the fault.

Rows five to seven are the needles. Five is the rule itself: both fixture faults and the walk over a
miniature brain go red together. Six is the second spelling: the call handed a name stops being
found, and the walk stops reporting it. Seven is thinner and worth saying so rather than dressing
up: replacing the scan's reading of the tree with a stub of the same shape fails the floor test
alone, that floor being the only thing asserting the scan reads a brain at all.

### Consequences

- A runbook may print a rendered sample of any line the brain writes, including the five whose call
  is handed its word. Before this, five lines were undocumentable by a gate that says it is found
  rather than registered.
- A module that spells one log message twice is refused with the same sentence a doubled logger name
  gets, and the fault names every binding of it, so the reader never picks one of two.
- `scripts/` gains `loggernames.py`, which is the logger half of a reader that had grown two
  subjects. Both halves now sit under the line cap with room, and each is named for the question it
  answers.
- The constant registry is unchanged in shape: 79 entries over 89 declaring sites and 265 mentions.
  One site's path moved with the guard it names.

### Deferred by this addendum

- A declared message and a different word in the call, held by one package's own suite
  ([R-504](../refinements/tasks/504-a-declared-message-and-a-different-word-in-the-call.md)).
- The spill line the swap runbook describes in prose and never prints, now that a sample of it
  would be held
  ([R-505](../refinements/tasks/505-the-spill-line-a-runbook-describes-and-never-prints.md)).

## Quotable-line addendum (2026-08-30): what a page can print back, and the field list that decides it

The addendum above ends with a consequence stated one word too wide: *a runbook may print a
rendered sample of any line the brain writes, including the five whose call is handed its word.*
The entry it deferred was written on that sentence and asked the next question, which of the five
an operator is helped by seeing rendered
([R-505](../refinements/tasks/505-the-spill-line-a-runbook-describes-and-never-prints.md)).
Re-deriving it against the shipped reader answers an earlier one instead: three of the five cannot
be printed at all, and the message was never the only thing standing in the way.

### Re-derived: the message half was one half of two

`logged` resolves all five messages now, and refuses three of the five calls anyway:

```
scripts/logcalls.logged, asked for each of the five in turn on the committed tree:

brain_phase.py, the spill warning   REFUSED at 242: extra= is not a mapping written out at the call
brain_phase.py, the decode reading  REFUSED at 244: extra= is not a mapping written out at the call
brain_phase.py, no reading          line=222 level=INFO fields=(model, session_id, turn_id)
abandon.py, the abandoned call      line=72 level=WARNING fields=(method, time_remaining)
audit.py, the tool trail            REFUSED at 100: extra= is not a mapping written out at the call
```

`_report_cadence` builds one `extra` above its two number-carrying calls and hands it over, the
warning as `extra | {"shortfall": reading.shortfall}` and the reading as `extra`. Neither is a
mapping written out at the call, so `_keys` refuses to read a field list off either, exactly as it
refuses the tool audit's `fields`, which the entry and the constant registry both already said of
that one. **The line the entry is named after is the line still not quotable.** It says the
opposite in as many words, that the abandonment warning and the spill trio each write a literal
`extra=` at the call and would be held, and one third of that is true.

What remains quotable is two lines: the no-reading INFO in `brain_phase.py`, carrying `model`,
`session_id` and `turn_id`, and the abandonment WARNING in `abandon.py`, carrying `method` and
`time_remaining`.

### Decision 1: print the no-reading line, in the list that already describes it

Of the two, the abandonment warning is described by no runbook at all. Printing it would mean
writing the passage around it first, and a rendered line with no procedure attached is not what a
sample is for: a sample tells an operator what to expect on a stream while somebody is waiting, and
that presumes a page telling them what to do about it.

The no-reading line has the opposite standing. `docs/runbooks/model-swap.md` describes it in the
spill watch's own list, and it is the one of the three an operator is likeliest to misread, which
is why that bullet already says **is not a pass** in bold. Rendered, it shows the one thing the
prose cannot: it carries the three work identities and no numbers whatever, which is how to tell it
at a glance from the two lines that carry the decode rate. So it is printed there, and the two
beside it stay prose.

The same reading corrected that prose. The warning's bullet named six fields, in an order it does
not print, and omitted `model`, `session_id` and `turn_id` outright; the INFO beside it claimed
"the same numbers" for a line that differs by one field. A sample is held to the printed field list
and prose is held by nothing, which is what unheld prose drifts into. All nine are now named in the
order the formatter renders them.

### Decision 2: a call is not rewritten to become quotable

The obvious way to print the spill warning is to write both dicts out at their calls. It is
declined. The two lines carry the same measurement and differ by one field, which is why one dict
is built above them; writing them out means nine keys at one call and eight at the other, the same
eight spelled twice, and the day one moves the other does not. A gate holds a document to the code.
Code bending to the gate's reader inverts that, and the price is paid in the module a spilled
handoff is debugged from.

So the residue is the reader's, not the brain's: teach `logcalls.py` to follow an `extra=` composed
above its call, which is the field half of the reading the addendum above made for the message
([R-516](../refinements/tasks/516-a-field-list-composed-above-its-call-cannot-be-quoted.md)).
Until then, a line whose fields are assembled rather than written is a line the runbooks describe
and do not print, which is where all three of them were this morning and where two remain.

### Distrust green

Four mutations and a control, each applied alone to the working tree and reverted, with
`check-samplecheck` the column that moves. This change is documents only, so the **gate suite**
(`scripts/tests/`, 1,564 checks, 100% covered) is unmoved by every row and is stated once rather
than per row.

| Mutation | `check-samplecheck` |
| --- | --- |
| CONTROL: nothing edited | passes, over 5 samples in 12 runbooks |
| the new sample renames `session_id` to `chat_id` | **fails**: prints model, chat_id, turn_id where `brain_phase.py:222` attaches model, session_id, turn_id |
| the new sample prints its three fields in another order | **fails**: prints turn_id, session_id, model, the same miss on order alone |
| the new sample prints WARNING, the level an operator scanning for trouble might assume | **fails**: prints WARNING where `brain_phase.py:222` logs at INFO |
| the spill warning is fenced as a sample beside it | **fails**: `extra= is not a mapping written out at the call` |

The second row reaches further than the sample it edits: the field is spelled the same way in the
failed-handoff sample lower down the same runbook, and both go red on one edit, which is the gate
being over the tree rather than over a line. The third row is the one worth having on its own,
since a hand writing a sample from a field list has the prose order in front of it and the printed
order nowhere, and that is exactly the mistake this sample was one edit away from carrying. The
fourth row is this addendum's finding run as a mutation: the failing document is the correct,
well-intentioned one, which is the same shape as the fault the addendum above fixed and a different
cause.

### Consequences

- The consequence sentence above narrows: a runbook may print a rendered sample of a line whose
  message the module binds or writes **and** whose fields are a mapping written out at the call.
  Five of the brain's lines pass the first test and two pass both.
- The runbooks print five rendered samples where they printed four, and the swap runbook's spill
  watch names every field of all three of its lines in the order they render.
- Nothing in `scripts/` changed. The gate that would hold a new sample is the one built this
  morning, and this addendum is the first document written against it.

### Deferred by this addendum

- A field list composed above its call cannot be quoted, which is what keeps the spill warning and
  the tool audit's own line out of the runbooks
  ([R-516](../refinements/tasks/516-a-field-list-composed-above-its-call-cannot-be-quoted.md)).

## Held-call addendum (2026-09-02): the call a registered message is handed is a place the registry reads

The handed-message addendum above ends with the residue it could not close. The tool audit binds
`_MESSAGE` and hands it to `_logger.info`, the registry ties four places to that binding, and a call
handed some other word leaves all four restating a word the brain does not write, with every scan
green; one package suite held it, named by hand. The entry asking for this weighed two paths, a
mention of the emitting call rendering the identifier, and a field in the registry saying which of
its values is a log message
([R-504](../refinements/tasks/504-a-declared-message-and-a-different-word-in-the-call.md)). The
first is built here, with the guard the entry said it would need, and the second is declined on a
ground already recorded.

### Re-derived first, and one claim had been overtaken

Every claim about the sink held. `brain/packages/tools/src/cortex_tools/audit.py` binds
`_MESSAGE = "tool.invocation"` at line 30 and hands it to `_logger.info` at line 89; the entry in
`trailcouplings.py` ties the tools runbook, two spellings in the process entry's suite and the
sink's own suite to that binding; that suite asserts four whole rendered lines; and the derivation
that closed the logger half reads a set the modules bind under `_LOGGER_NAME`, which a message has
no counterpart of. The measurement behind that last point was repeated: the brain binds 22
top-level strings whose names say `MESSAGE` or `MSG`, and five of them are log messages,
`_MESSAGE`, `ABANDONED_MESSAGE` and the three in `cortex_core/brain_phase.py`. The state the entry
describes was measured as well as read. The sink handing its call `"tool.dispatch"`, or handing it
`_LOGGER_NAME`, is green in the gate suite, green under `check-crosscheck` and
`check-samplecheck`, and five reds in the tools package alone.

One claim had been overtaken on the day it was written. The entry counts two of the four other
declared messages as held by their suites, `ABANDONED_MESSAGE` by `test_abandon.py` and the spill
warning by `test_brain_phase.py`, each importing the constant and asserting the emitted record
against it. That is still true, and a third is held as well: the quotable-line addendum printed
the no-reading line in `docs/runbooks/model-swap.md`, so that call handing another word fails
`check-samplecheck` as a message the module no longer writes, which the last row below measures.
Only the decode reading's message is held by nothing, and it is restated by nothing either. The
spill warning turned out to be restated after all, in the same runbook's prose, as a wrapped prefix
of the sentence in italics, which nothing ties and which the registry as written cannot tie; that
is filed rather than fixed here.

### Decision 1: the emitting call is a mention of the message's own entry

The registry already has the form this needs. A mention renders `{name}` where a far side names a
value rather than restating it, which is how `var(--roll)` is held beside the declaration paying
it, and `_logger.info(_MESSAGE,` names the value in exactly that sense. So the entry gains
`Mention(AUDIT_SINK, "_logger.info({name},", name="_MESSAGE")`. A call handed another literal, or
another binding, leaves that needle unfound and `check-crosscheck` fails naming the entry. A
renamed value leaves it found, which is right: the call goes on handing the binding whatever the
binding says, and the four mentions rendering the value are what a renamed value has to move.

The one cost the entry priced is paid the cheaper way. `spend_fault` refused a name pinned as a
spend that no mention of the same entry renders the value under, and here the value is paid by the
entry's own `Site`. A site pays the name it declares: reading `_MESSAGE = "tool.invocation"` is
reading the value under that name, which is the act `{name}: {value}ms;` performs on a stylesheet
the scan has no declaration syntax for. The rule now reads the sites as well as the mentions. The
alternative, a second mention re-reading the declaration line so that a mention pays the name, was
rejected as a place written for the rule's sake that would spell the declaration twice in the
registry.

### Decision 2: the set a call mention is required over is the registry against the tree

The entry was right that the logger's derivation does not transfer, and the marker field it
weighed as the other path is declined on the ground the declared-name addendum gave for a logger
marker: it puts a subject inside data whose every other entry is a value and the places that spell
it. What the entry did not say is that the set here needs no naming at all. The set is not "which
bindings are log messages", which this brain cannot say. It is "which registry sites a log call in
that module is handed", and both halves of that are readable: the registry says which bindings
documents restate, and `logcalls.handed` says which bindings a module's calls are handed by name. A
site in both is one whose call mention can be forgotten, and there is one today.

The guard, `test_every_registered_binding_a_brain_log_call_is_handed_is_held_at_that_call` in
`scripts/tests/test_crosscheck.py`, requires of every such site a mention on the sink rendering
that name whose needle lands on the line handing it. The line is what keeps a mention aimed at the
declaration from satisfying it: `{name} = "` renders the same identifier and holds nothing about
the call. The guard sits with the registry's other claims about the real trees rather than beside
the logger guard, because the claim is about the registry's completeness against the brain, where
the logger guard compares two readings of the brain and needed no registry.

A call handed a binding writes that binding's value, so nothing is wrong on the day a site is
registered; the guard fires then, when the mention is missing, and the mention holds from then on.
A site whose call hands a literal from the day it is registered is outside the set, since nothing
says that site is a message, and it is held by the sink's own suite where one exists. The entry
measured that no convention can derive that case, and nothing here changes it.

### What was written down, and what was not gated

The convention doing most of the work outside the registry is now stated: a package suite imports
the message constant and asserts `getMessage()` against it, as `test_abandon.py` and
`test_brain_phase.py` do. It is not gated. A binding no document restates has no far side to drift
from, so a call handed another word there leaves an unused binding and nothing false, and a guard
over it would detect a hazard with no consequence.

### Distrust green

Eight mutations and a control, each applied alone to the working tree and restored, measured over
the **gate suite** (`scripts/tests/`), 1,572 checks before this change and 1,587 after, with
`check-crosscheck` and `check-samplecheck` run beside it. The tools package
(`brain/packages/tools/tests/test_audit.py`, 13 checks) was run for the second row as well, since
the sink's own suite is what held it before: five reds, before and after.

| Mutation | before | after | `check-crosscheck` | `check-samplecheck` |
| --- | --- | --- | --- | --- |
| CONTROL: nothing edited | 0 | 0 | passes | passes |
| the audit sink hands its call another literal | 0 | **13** | **fails** | passes |
| the audit sink hands its call the logger's binding | 0 | **13** | **fails** | passes |
| a second registered binding is handed to a call, with no call mention | n/a | **1** | passes | passes |
| GATE: the call mention is dropped from the entry | n/a | **2** | passes | passes |
| GATE: the call mention is aimed at the declaration | n/a | **2** | passes | passes |
| GATE: a site stops paying the name it declares | n/a | **16** | **fails** | passes |
| GATE: the guard stops checking the line | n/a | **2** | passes | passes |
| the no-reading call in `brain_phase.py` hands another word | 2 | 2 | passes | **fails** |

Rows two and three are the entry measured. Both were green everywhere but the tools package, and
both are now a failing scan naming the entry whose call moved, plus thirteen reds: the tests that
run the scan over the repo, every doctored-tree test that copies the audit sink and expects the
unedited copy to pass, and the guard itself through its non-emptiness floor, since a tree in which
no registered binding is handed to any call is one its fixtures describe and the brain does not.
Row four is what the guard buys, and the whole of it: a binding registered tomorrow and handed to
its call with the mention forgotten is one red naming the site, the line and the mention to add,
where before this change it was green.

Rows five to eight are the needles. Five and six are the mention removed and the mention
retargeted, each caught by the guard and by the doctored-tree test that hands the sink another
word; six is the row the line check exists for, a mention of the same identifier over the
declaration holding nothing about the call. Seven is the registry rule: with a site no longer
paying its name, the audit entry is refused as written, the scan fails on a clean tree, and sixteen
tests go red, the four written for the relaxation among them. Eight removes the line check and is
caught by the two fixture tests written for it, the real-tree guard staying green because the one
registered call mention does land on its call.

Row nine is the correction to the entry, run as a mutation: the no-reading message is held by the
sample gate before and after this change, identically, because the quotable-line addendum printed
that line and `logged` resolves the name. This change did nothing to it and claims nothing about it
beyond having measured it.

### Consequences

- The tool audit's message is held to its call by the registry, and any registered binding a brain
  log call is handed will be, from the day it is registered.
- The constant registry stands at 79 entries over 89 declaring sites and 266 mentions, in twelve
  parts. One mention is on the same file as its entry's site, which is new: the call and the
  declaration are one module, and the scan reads them as two places.
- A rename of the identifier `_MESSAGE` is two registry edits, the site and the mention's name,
  where it was one. A rename that moves only the site fails the scan naming the entry.
- The doctored-tree test that renames the value now expects every value-rendering mention to fault
  and the call mention to hold, and says why.

### Deferred by this addendum

- A registered binding handed at a call the formatter wraps has its name on the line after the
  call, so the template the guard's failure message suggests does not land there
  ([R-518](../refinements/tasks/518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md)).
- The swap runbook restates the spill warning's message in italics, as a prefix wrapped over two
  lines, and no needle can render a prefix or cross a wrap
  ([R-519](../refinements/tasks/519-a-runbook-restates-a-declared-message-as-a-wrapped-prefix-nothing-ties.md)).

## Composed-fields addendum (2026-09-02): a field list bound above its call is read, and the spill watch is printed

The quotable-line addendum above left its residue on the reader's side: `logcalls._keys` read a
field list off `extra=` only when that keyword's value was a mapping written out at the call, so the
spill warning and the decode reading in `cortex_core/brain_phase.py`, whose one `extra` is built
above both calls and handed over bare and unioned, and the tool audit's trail, whose `fields` grows
across statements, were lines the runbooks described and could not print. The entry it deferred
proposed a tractable middle, a bare name bound to a mapping in the same function and that name
unioned with a mapping at the call, and argued that the audit should stay unquotable rather than
guessed ([R-516](../refinements/tasks/516-a-field-list-composed-above-its-call-cannot-be-quoted.md)).
That middle is built here, with the conditions that make it a reading rather than a guess, and the
three lines of the spill watch are printed in the swap runbook. Printing the warning also closes the
entry the held-call addendum filed about that runbook's italic restatement of it
([R-519](../refinements/tasks/519-a-runbook-restates-a-declared-message-as-a-wrapped-prefix-nothing-ties.md)),
by removing the restatement rather than tying it.

### Re-derived: every claim held, and only the line numbers had moved

`_keys` raised on anything but an `ast.Dict` at `scripts/logcalls.py:149`. `_report_cadence` binds
`extra` at `brain_phase.py:199` and hands it over at 210, unioned with `{"shortfall": ...}`, and at
212, bare; `LoggingAuditSink.record` binds `fields` at `audit.py:65`, grows it by `update` at 72 and
by a key set under a condition at 86 and 88, and hands it over at 89. Asked for each of the four
messages on the committed tree, `logged` refused three:

```
brain_phase.py, the spill warning   REFUSED at 210: extra= is not a mapping written out at the call
brain_phase.py, the decode reading  REFUSED at 212: extra= is not a mapping written out at the call
brain_phase.py, no reading          line=190 level=INFO fields=(model, session_id, turn_id)
audit.py, the tool trail            REFUSED at 89: extra= is not a mapping written out at the call
```

The quotable-line addendum recorded the same three refusals at 242, 244 and 100; the modules were
shortened by the plain-language pass since, and nothing else about them changed. The swap runbook's
warning bullet named all nine fields in printed order, as that addendum left it, and quoted the
warning's first clause in italics over two lines, as the held-call addendum found it. No commit
since 2026-08-25 touched the field reading.

### Decision 1: three spellings are read, under four conditions, and the rest are refused

`scripts/logfields.py` reads a call's `extra=` in three spellings: a mapping written out at the
call, a bare name, and that name unioned with a mapping written out at the call. A name is followed
under four conditions, each of which is what stands between a reading and a guess:

1. **Inside the function the call is written in, and no wider.** The innermost function holding
   the call is the scope, a module-level binding is not followed from inside one, and a call at the
   module's top level has no scope to follow a name in. A mapping bound at a module's top level
   could be grown by any function in it.
2. **Bound by one statement at the top of that function's body, above the call.** A binding inside
   a branch is the mapping of the runs that took the branch, and nothing in the source says which
   those are; a binding below the call is not the call's. A statement at the body's top level and
   above the call runs on every path that reaches the call.
3. **Bound to a mapping written out**, with plain string keys. `dict(...)`, a call, and a spread
   are each refused as they were.
4. **Named nowhere else in the function** except as the `extra=` of a log call, bare or as the
   left half of a union. A call on the name, a key set on it, a rebinding in a branch, a `global`
   or `nonlocal` declaration, and a hand-over to any call that is not a log call are each a use
   after which the mapping reaching the call may not be the one written out. Which calls are log
   calls is handed in by `logcalls.py`, so the field reader carries no level table.

Under those four, the mapping reaching the call is the one written out, and the fields are its keys
plus the unioned literal's, sorted and deduplicated, since a key both halves carry is one key on the
record. Everything else is refused with a fault naming the line and the reason, in three shapes:
`extra= names extra, which the enclosing function does not bind above the call to a mapping written
out`; `binds more than once above the call (lines 2, 3)`; and `bound at line 2 and used again at
line 3, so the mapping reaching the call is not the one written out`. The entry weighed exactly
this: a field list read from a branch that does not run would hold a document to a line nothing
prints, which is worse than raising, and refusal is the cheaper side of that trade to be wrong on.

### Decision 2: the tool audit stays unquotable, on purpose

`audit.py` is the fourth condition's case. Its mapping is bound, then grown by `update` with the
identities the dispatch carried, then given `result_chars` or `error` by whether the call succeeded,
and only then handed over. No one sample could print what it attaches, because what it attaches is
a set that varies by condition; a reader that followed the growth would have to choose a branch,
which is the guess the entry declined. The reader refuses it at the first use after the binding,
`bound at line 65 and used again at line 72`, and the line stays one the tools runbook describes in
prose. That prose is held by nothing, which is the same shape this addendum closes for the spill
warning, and it is filed rather than fixed.

### Decision 3: the spill watch's three lines are printed, and the prose stops restating them

With both number-carrying calls readable, the swap runbook prints all three lines of the spill watch
in one fence, the warning, the decode reading and the no-reading line, every value a placeholder.
The quotable-line addendum's standard was that a sample earns its space by showing what the prose
cannot, and the warning does: nine fields in the order they print, with `shortfall` among them, on
the one line the runbook exists to explain. The decode reading is printed beside it rather than
described as "the same fields except `shortfall`", because a description relative to a held sample
is still prose held by nothing, and it is the line an operator reads the next floor off.

The bullets above the fence no longer enumerate field names or quote the message. The warning's
bullet named nine fields in printed order and quoted the sentence's first clause in italics, wrapped
over two lines, which no registry needle could render or cross; the entry filed about that weighed
quoting the whole sentence on one line of prose, splitting the constant, and teaching the registry
to fold whitespace and render a prefix. None of the three is taken. The restatement is removed, and
the message is held by the sample gate, which compares the fenced line's message to the binding's
value whole. Row D below is that hazard run as a mutation: the constant reworded leaves the brain's
own suite green, since it imports the constant, and fails the sample gate.

### The split, and what the reader is handed

`logcalls.py` stood at 280 lines and the reading needed about a hundred, so the field half moved
out as `scripts/logfields.py` and `logcalls.py` translates its fault into a `LogCallError`. The one
question the new module cannot answer alone is which calls are log calls, since a name handed to a
log call as `extra=` is a use it accounts for and a name handed to a helper is not. That rule is
passed in as a predicate rather than read from a level table copied across, so `logcalls.py` keeps
the one table.

### Distrust green

Eleven mutations and a control, each applied alone to the working tree and restored from a copy,
measured over the **gate suite** (`scripts/tests/`, 1,591 checks before this change and 1,621
after), with `check-samplecheck` beside it, now over seven samples where it was over five. The brain
package's `test_brain_phase.py` (30 checks) was run for row D, since that suite is what held the
warning's message before. The first attempt at this table restored the runbook with `git checkout`,
which discarded the uncommitted samples on the first row and left the gate green over five samples
for every row after; it was thrown away, and the table below was measured with every file restored
from a copy.

| Mutation | gate suite | `check-samplecheck` |
| --- | --- | --- |
| CONTROL: nothing edited | 0 | passes, 7 samples |
| A: the bound mapping renames `samples` to `completions` | **3** | **fails**: two samples, each attaching `completions` where the runbook prints `samples` |
| B: the warning stops unioning `shortfall` at the call | **4** | **fails**: prints `shortfall` where `brain_phase.py:210` attaches eight fields |
| C: a key is set on the mapping between its binding and the calls | **4** | **fails**: `bound at line 199 and used again at line 209`, both samples |
| D: `SPILLED_LOG_MSG` is reworded | **2** (brain suite: 0) | **fails**: `logs no message` |
| E: the printed warning renames `shortfall` to `deficit` | **2** | **fails**: prints `deficit` where the call attaches `shortfall` |
| F: the printed warning rewords its first clause | **2** | **fails**: `logs no message` |
| G: GATE the reader stops refusing a name used again | **6** | passes |
| H: GATE the reader stops requiring the binding above the call | **1** | passes |
| I: GATE the reader reads a binding anywhere in the function | **2** | passes |
| J: GATE the outermost function wins instead of the innermost | **2** | passes |
| K: GATE the handed set is built from the wrong node | **8** | **fails**: both samples, `used again at line 210` |

Rows A to C are the code moving under a printed sample, which is what the entry asked to be caught,
and each is red in two places: the real-tree tests in `test_logfields.py` and the gate itself. Row D
is the runbook's restatement hazard measured: the brain suite imports the constant and stays at 30
green, and the sample gate reports the message the module no longer writes. Rows E and F are the
document moving under the code. Rows G to K are the reader's conditions and its bookkeeping, each
disabled alone; G is the one that matters most, since without it the tool audit's line would be read
off its first literal and reported as five fields where it prints up to eleven, and six tests name
that.

### Consequences

- A runbook may print a rendered sample of a line whose message the module binds or writes and
  whose fields are a mapping written out at the call, or bound to one above the call under the four
  conditions. All five of the brain's handed lines pass the first test and four pass both; the tool
  audit's is the one that does not.
- The runbooks print seven rendered samples where they printed five, and the swap runbook's spill
  watch restates none of its three lines in prose.
- `scripts/` gains `logfields.py`, and the module contract, the repo map and the docs index name it.
- The reader accepts the two composed spellings the brain writes and no other; a third spelling
  arriving is a refusal naming its line rather than a five-field answer.

### Deferred by this addendum

- A union spelled as a `**` spread of the bound name, `{**extra, "shortfall": ...}`, is still
  refused as a spread, though it prints the same line as `extra | {...}` does
  ([R-522](../refinements/tasks/522-a-union-spelled-as-a-spread-of-the-bound-name-is-still-refused.md)).
- The tool audit's line is described in the tools runbook in prose because its field set varies by
  condition, and that prose is held by nothing
  ([R-523](../refinements/tasks/523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md)).
- The registered-binding needle for a call the formatter wraps is unchanged
  ([R-518](../refinements/tasks/518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md)):
  this addendum reads fields, and the needle it names belongs to the registry.

## Addendum (2026-09-04): the wrapped-call needle is re-derived and its trigger has not fired

The composed-fields addendum deferred the registered-binding needle for a call the formatter wraps,
and the entry was re-derived against the tree as it stands rather than taken on its own word. It
stays open, with the count that fires it written down so the next reader starts from a reading
rather than from a rebuild.

`logcalls.handed` reports eleven brain log calls whose message is a bare name. Five of those names
are bound by the module's own top level, which is the kind a registry `Site` can declare:
`_NO_READING_LOG_MSG`, `SPILLED_LOG_MSG` and `_MEASURED_LOG_MSG` in `cortex_core/brain_phase.py`,
`ABANDONED_MESSAGE` in `cortex_orchestrator/abandon.py`, and `_MESSAGE` in `cortex_tools/audit.py`.
The other six are handed a local `msg` the function builds, which no site declares. Two of the five
are wrapped, the abandonment warning and the no-reading line, and neither is registered. Running the
guard's own reading over the real registry returns one row, `_MESSAGE` at `audit.py:89`, whose call
is on one line, so the shape this entry is about has no instance today.

The miss the entry predicts is confirmed rather than assumed. Rendering the template the guard's
failure message suggests, `<the call>({name},`, against each wrapped call finds it zero times in the
file that writes it: `_logger.warning(ABANDONED_MESSAGE,` in `abandon.py` and
`_logger.info(_NO_READING_LOG_MSG,` in `brain_phase.py`, where the same rendering for the audit sink
finds `_logger.info(_MESSAGE,` once. An author registering either binding would therefore reach the
guard's suggestion and get an unfound needle from `check-crosscheck`, which is the day the two
spellings weighed in the entry have to be decided between.

### Records

[R-518](../refinements/tasks/518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md),
which stays open with a dated trail entry and a trigger that now says how it is counted,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it, and this
addendum.

## Addendum (2026-09-04): the spread spelling is re-derived and the brain still writes none

The composed-fields addendum deferred the `**` spread of a bound name, and the entry was re-derived
against the brain's source rather than taken on its own word. It stays open, with the reading that
fires it written down.

The brain's log calls attach 94 `extra=` expressions. 85 are a mapping written out at the call, six
are a bare name the enclosing function binds, one is the `|` union at `cortex_core/brain_phase.py`
line 210, and two are a call, `_pairing(subagents, tools)` at `cortex_orchestrator/bounds.py` lines
129 and 144, which `logfields.py` refuses as neither a mapping written out nor a name bound to one.
None of the 85 carries a `**` entry, so the spelling this refinement is about has no instance in the
brain and a reader case for it would still be written against no example. `_literal` goes on
reporting a spread as a field name that is not a plain string, which is the answer the entry argues
is right for a spread of any name the reader would not follow.

### Records

[R-522](../refinements/tasks/522-a-union-spelled-as-a-spread-of-the-bound-name-is-still-refused.md),
which stays open with a dated trail entry and a trigger that now says how it is counted,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it, and this
addendum.
