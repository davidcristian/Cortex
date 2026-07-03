# Audit of Slice 6 (Tools via MCP: files, then email)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Slice 6 is substantively fully implemented and matches its ROADMAP text closely: the pure tool-dispatch core (ports, values, typed errors, fakes, ToolDispatcher with exactly-one-audit-record semantics), native function-calling (InferenceEvent, Message tool fields, the bounded MAX_TOOL_STEPS loop behind TurnCapabilities, LlamaCppBackend tools payload + streamed reassembly), the cortex_tools MCP adapter behind an injected McpSession port with opt-in CORTEX_TOOLS_BACKEND wiring and a read-only filesystem sidecar compose, and the standalone cortex_email FastMCP server with three read-only tools enforced by construction, EXAMINE, and mark_seen=False. Host validations (EROFS containment, live Bridge dogfooding, the readable-string and HTML-fallback refinements) have a complete paper trail in the ADR-0009 addenda, integration-marked tests, and runbooks, and the four consciously deferred refinements are all in the ROADMAP ledger. Two low-severity discrepancies remain: the filesystem server is not actually version-pinned in the committed compose despite ADR-0009 asserting it is (the punt is written only in a compose comment and runbook, not the deferral ledger, the one undocumented item forcing the strict verdict), and the --jinja flag ADR-0009 promises for the cortex GPU compose upon live tool-path validation was never committed, with no recorded end-to-end validation of the cortex model natively emitting a tool call. Both are mitigated (the read-only mount is the proven boundary; the runbooks describe the override), so the verdict is undocumented-gaps on the letter of the rules, not on substance.

## Claims checked (25)

- **✅ verified**. ToolRegistry + ToolAuditSink ports exist in the pure core
  - Evidence: brain/packages/core/src/cortex_core/ports.py:113-136 (ToolRegistry.describe_tools/invoke, ToolAuditSink.record as Protocols)

- **✅ verified**. ToolSpec/ToolCall/ToolResult/ToolInvocation value types live in tools.py with no ports import (mirroring memory.py)
  - Evidence: brain/packages/core/src/cortex_core/tools.py:32-97 (all four frozen dataclasses; module imports only stdlib); ToolInvocation rejects naive timestamps at tools.py:94-97

- **✅ verified**. Typed ToolError / ToolNotFoundError cross the port
  - Evidence: brain/packages/core/src/cortex_core/errors.py:24-34 (ToolNotFoundError subclasses ToolError)

- **✅ verified.** InMemoryToolRegistry + RecordingAuditSink fakes exist and behave as the contract twins
  - Evidence: brain/packages/core/src/cortex_core/fakes.py:154-193; behavior tests in brain/packages/core/tests/test_tools.py

- **✅ verified**. ToolDispatcher writes exactly one audit record per dispatch and turns a registry ToolError into an is_error ToolResult the model can recover from
  - Evidence: brain/packages/core/src/cortex_core/dispatch.py:58-104 (every path funnels through _audited once; ToolError caught at 75-80); tests brain/packages/core/tests/test_dispatch.py:61-104 assert single-record trails for success, unknown tool, and tool failure

- **✅ verified.** InferenceBackend.stream gained a tools parameter and yields InferenceEvent = TextChunk | ToolCall
  - Evidence: brain/packages/core/src/cortex_core/inference.py:14-21 (type InferenceEvent = TextChunk | ToolCall); brain/packages/core/src/cortex_core/ports.py:46-47 (stream(..., tools: Sequence[ToolSpec] = ()))

- **✅ verified**. Message gained tool_calls/tool_call_id and Role gained TOOL
  - Evidence: brain/packages/core/src/cortex_core/conversation.py:19 (TOOL = "tool"), :41-42 (tool_calls: tuple[ToolCall, ...] = (), tool_call_id: str | None = None)

- **✅ verified**. TurnEngine runs the bounded (MAX_TOOL_STEPS) inference-to-tool loop behind an optional TurnCapabilities bundle, dispatch audited, results fed back as ASSISTANT tool_calls + Role.TOOL messages
  - Evidence: brain/packages/core/src/cortex_core/engine.py:52-61 (TurnCapabilities), :111 (stream_tool_loop); brain/packages/core/src/cortex_core/tool_loop.py:30 (MAX_TOOL_STEPS = 8), :83-111 (bounded loop, _call_message/_result_message feed-back); bound asserted in brain/packages/core/tests/test_engine.py:434-435. Note: since Slice 7 the loop body lives in the shared tool_loop.py, driven by TurnEngine. A recorded extraction, not a contradiction (tool_loop.py:6 docstring)

- **✅ verified**. Tool context is in-turn only in v1: only the user turn and final assistant answer are persisted; the exchange rolls into one memory record at turn end
  - Evidence: brain/packages/core/src/cortex_core/engine.py:98-129 (only user and final assistant Messages appended to the store; tool-step messages live in the local working list; single memory.record at 127-128)

- **✅ verified**. LlamaCppBackend sends the OpenAI tools payload and reassembles streamed tool_calls fragments into ToolCall events (needs --jinja on the server)
  - Evidence: brain/packages/inference/src/cortex_inference/backend.py:65-77 (_to_openai_tools), :80-120 (_consume_chunk/_finish_calls reassembly), :144-145/:168-169 (payload + yield); tests brain/packages/inference/tests/test_backend.py:151-259 cover payload serialization, streamed reassembly, empty-args, malformed-args

- **✅ verified**. cortex_tools package: McpToolRegistry over the official mcp SDK pinned >=1.23,<2, behind an injected McpSession port with a CI fake (covered without a server)
  - Evidence: brain/packages/tools/src/cortex_tools/registry.py:31-83 (McpSession Protocol, describe_tools/invoke mapping, connect over streamable_http_client, ToolError wrapping); brain/packages/tools/pyproject.toml:8 ("mcp>=1.23,<2"); brain/packages/tools/tests/test_registry.py:27-121 (FakeSession-based tests); 100% gate enforced workspace-wide at brain/pyproject.toml:66 (--cov --cov-branch --cov-fail-under=100)

- **✅ verified**. LoggingAuditSink writes one structured logging record per invocation (result size on success, error detail on failure)
  - Evidence: brain/packages/tools/src/cortex_tools/audit.py:17-32

- **✅ verified**. Wired into run_from_env opt-in via CORTEX_TOOLS_BACKEND (default none), endpoint required when mcp
  - Evidence: brain/packages/orchestrator/src/cortex_orchestrator/config.py:106-124 (ToolsConfig backend default "none", validator requiring CORTEX_TOOLS_ENDPOINT); wiring.py:113-125 (build_tool_registry), :215/:226 (run_from_env wiring into TurnCapabilities)

- **✅ verified**. docker/docker-compose.tools.yml adds the filesystem MCP server as a read-only-mounted sidecar over streamable-http and flips the brain to CORTEX_TOOLS_BACKEND=mcp
  - Evidence: docker/docker-compose.tools.yml:19-20 (brain env), :25-49 (supergateway-bridged @modelcontextprotocol/server-filesystem, bind mount read_only: true at :42-45, loopback-only publish :48)

- **📄 verified-as-documented (host-only run; paper trail checked)**. Increment-3 host validation: live sidecar passed the integration test and the read-only mount blocked a write with EROFS, recorded in the ADR-0009 addendum
  - Evidence: docs/adr/ADR-0009-tools-mcp.md:124-144 (dated 2026-06-29 addendum: 14 tools listed, read_text_file success, write_file EROFS); integration-marked live test brain/packages/tools/tests/test_registry_live.py:22; runbook docs/runbooks/tools-mcp.md:28-39 describes the run

- **✅ verified**. cortex_email is a standalone FastMCP server exposing exactly three read-only tools (list_folders, search_emails, read_email) over imap-tools with STARTTLS
  - Evidence: brain/packages/email/src/cortex_email/server.py:36-58 (the three @server.tool() handlers, no others); imap.py:13,32-39 (MailBoxStartTls when security==starttls); email/pyproject.toml:7-8 (mcp>=1.23,<2 and imap-tools>=1.7); __main__.py provides python -m cortex_email

- **✅ verified**. Read-only enforced three ways: only read tools register, folders open with EXAMINE (readonly=True), fetches never set Seen (mark_seen=False)
  - Evidence: brain/packages/email/src/cortex_email/server.py:36-58 (three read tools only); imap.py:49+58 (box.folder.set(folder, readonly=True)); imap.py:50+59 (mark_seen=False on both fetch paths)

- **✅ verified**. cortex_email is 100%-covered without a server (fake Mailbox for reader/tools, fake imap-tools MailBox for ImapMailbox)
  - Evidence: brain/packages/email/tests/test_email_server.py:36-86 (fake Mailbox + FastMCP.call_tool in-process), test_imap.py, test_reader.py; workspace-wide --cov-fail-under=100 at brain/pyproject.toml:66; live half is the integration-marked test_email_live.py:13

- **✅ verified**. docker/docker-compose.email.yml runs the email server as a sidecar reaching the host ProtonMail Bridge (host.docker.internal:1143, STARTTLS, credentials via env only)
  - Evidence: docker/docker-compose.email.yml:26-46 (mcp-email service, CORTEX_EMAIL_IMAP_HOST=host.docker.internal, PORT 1143, SECURITY starttls, required env for user/password, extra_hosts host-gateway, loopback-only publish 9100); brain flipped to mcp at :20-21

- **📄 verified-as-documented (host-only run; paper trail checked)**. Increment-4 host validation: sidecar reached the live Bridge, dogfooding McpToolRegistry returned exactly the three read-only tools, 17 real folders, a formatted search line, and a real message body
  - Evidence: docs/adr/ADR-0009-tools-mcp.md:146-170 (dated 2026-06-29 addendum with all figures); runbook docs/runbooks/email-imap.md describes the run; integration marker at brain/packages/email/tests/test_email_live.py:13

- **✅ verified**. Two refinements landed during validation (readable-string tool output and HTML-body fallback), recorded in the ADR-0009 addendum
  - Evidence: Code: brain/packages/email/src/cortex_email/server.py:25-58 (every tool returns one formatted string) and reader.py:44-50 (get_body preferencelist ('plain','html')); recorded at docs/adr/ADR-0009-tools-mcp.md:157-166; commit 6935404

- **✅ verified**. Module docs and runbooks exist for the slice (brain-tools.md, brain-email.md, tools-mcp.md, email-imap.md)
  - Evidence: docs/modules/brain-tools.md:1-51, docs/modules/brain-email.md:1-43, docs/runbooks/tools-mcp.md:1-53, docs/runbooks/email-imap.md:1-61 all match the shipped code

- **✅ verified.** Consciously deferred refinements are recorded in the ROADMAP ledger (multi-server aggregation, advertised-tool filtering, HTML-to-text extraction, salience/rate policy) and at the origin ADR
  - Evidence: docs/ROADMAP.md:471-482 (Tools, Slice 6 ledger block); docs/adr/ADR-0009-tools-mcp.md:137-144 (filtering), :165-166 (HTML extraction), :181-191 (aggregation addendum), :121-122 (salience/rate)

- **✅ verified**. The three ADR-0009 forks are resolved as claimed: native function-calling, sidecar-over-http tool servers, thin read-only IMAP server (imap-tools over aioimaplib for STARTTLS)
  - Evidence: docs/adr/ADR-0009-tools-mcp.md decisions 2 (:33-41), 5 (:62-68), 6 (:70-82); code matches (backend.py tools payload; compose sidecars; imap.py MailBoxStartTls)

- **◐ partial.** The filesystem server is pinned to a patched version (EscapeRoute CVE-2025-53109/53110) as stated in ADR-0009 decision 5 and Risks
  - Evidence: The committed compose runs an unversioned `npx -y @modelcontextprotocol/server-filesystem /projects` on a mutable node:22-bookworm-slim image (docker/docker-compose.tools.yml:29-39); pinning is delegated to the operator via a comment (:26-28) and docs/runbooks/tools-mcp.md:24-26, while ADR-0009:65 and :109-110 state it as done
  - Adversarial re-check: confirmed. The auditor is correct and cannot be refuted. The committed compose service starts the filesystem MCP server via `npx -y @modelcontextprotocol/server-filesystem /projects` with no version specifier (docker/docker-compose.tools.yml:39), on a mutable `node:22-bookworm-slim` tag (:29); the bridging `supergateway` npx invocation (:31-33) is likewise unpinned. Both the compose comment (:26-28) and the 

## Gaps (3)

### G1 · severity low · **not documented as a deferral**

The filesystem MCP server version is not actually pinned in the repo: ADR-0009 decision 5 and its Risks section say the server 'is pinned to a patched version' (EscapeRoute CVE-2025-53109/53110), but docker/docker-compose.tools.yml:29-39 runs unversioned `npx -y @modelcontextprotocol/server-filesystem` on a mutable node:22 tag. The punt to the operator is written in a compose comment and the runbook (docs/runbooks/tools-mcp.md:24-26), but it is not recorded in the ROADMAP 'Deferred refinements & later work' ledger and the origin ADR asserts pinning as done rather than deferred. Low severity: the read-only single-directory mount is the proven security boundary (EROFS validated, ADR-0009 addendum) and auditing covers every call, so this is an ADR-text/compose discrepancy, not an open hole.

**Adversarial re-check: confirmed.** The auditor is correct on every element. (1) The filesystem MCP server version is not pinned anywhere in the repo: the compose service runs unversioned `npx -y @modelcontextprotocol/server-filesystem` on a mutable node:22 tag, and a repo-wide search for server-filesystem/EscapeRoute/CVE-2025-53109/53110 finds no lockfile, Dockerfile, or version knob. (2) The origin ADR-0009 asserts pinning in done-language at decision 5 (line 65) and the Risks section (line 109), and none of its four addenda record the pin as deferred. The origin ADR does not document a deferral, it misstates the state. (3) The ROADMAP "Deferred refinements & later work" ledger's Slice 6 Tools block lists exactly four deferrals (multi-server aggregation, advertised-tool filtering, HTML extraction, salience/rate policy) and no pin entry; the only pin it mentions is the unrelated Python mcp SDK pin. The only written records of the punt are the operator-facing compose comment and runbook step the auditor already acknowledged, which fall outside the ledger/origin-ADR criterion. The compose file even contradicts itself (header says "is pinned", command is unversioned), reinforcing the ADR-text/compose discrepancy. The auditor's low-severity framing is also fair: the EROFS-validated read-only single-directory mount is documented as the real boundary (ADR-0009 increment-3 addendum, lines 134-142).

### G2 · severity low · documented (docs/adr/ADR-0009-tools-mcp.md:104-105 (explicit 'added when the real tool path is validated' condition); docs/runbooks/tools-mcp.md:46 and email-imap.md:54 (flag requirement); docs/runbooks/llamacpp-gpu.md:102-108 (the ad-hoc override used for the ADR-0013 probe))

The `--jinja` flag has not been added to the committed cortex GPU compose: ADR-0009 Consequences (:104-105) say it 'is added to the GPU Compose command when the real tool path is validated on the host', both tool runbooks say the end-to-end model-emits-tool-calls path needs it (tools-mcp.md:46, email-imap.md:54), yet docker/docker-compose.gpu.yml:30-46 has no --jinja (only the Slice 7 subagents compose does, docker-compose.subagents.yml:48). Correspondingly there is no recorded validation of the cortex model natively emitting a tool call through the full live loop. The live inference test asserts text streaming only (test_backend_live.py:25) and the ADR-0013 GPU probe hand-built the tool-call message; increments 3/4 dogfooded McpToolRegistry directly, bypassing the model. The conditional plan is written at the origin ADR and the runbooks describe a scratch --jinja override (llamacpp-gpu.md:102-108), so the state is documented, but the ROADMAP marks Slice 6 complete without the condition ever being marked met.

### G3 · severity low · documented (brain/packages/core/src/cortex_core/tool_loop.py:6 ('inlined in handle_turn before Slice 7'); docs/ROADMAP.md:162 and :484-485 (Slice 6.5 text references stream_tool_loop as an existing seam))

Stale text (minor): the Slice 6 ROADMAP paragraph says 'TurnEngine runs the bounded (MAX_TOOL_STEPS) inference↔tool loop'; since Slice 7 the loop body lives in the shared cortex_core/tool_loop.py (stream_tool_loop), which TurnEngine drives (engine.py:111). Not misleading (the behavior is unchanged and the extraction is recorded), but the Slice 6 text was not updated to name the new home.
