# ADR-0022: Email send as the first outbound tool needing confirmation, and the confirmer

**Status:** Accepted (2026-09-17)

## Context

Sending an email is the first outbound, irreversible action the assistant has, and it brings the
machinery every later such action reuses. [ADR-0013](ADR-0013-untrusted-content.md) built the
confirmation rule (`ToolSpec.gated`, the dispatcher's block, the `Confirmer` port), but the port
was unused (`confirmer=None`, fail-closed) because no tool needed confirmation. The email sidecar
(`cortex_email`, [ADR-0009](ADR-0009-tools-mcp.md)) read IMAP only. The overlay talks to the brain
over the bidirectional `Converse` stream ([ADR-0011](ADR-0011-body-v1.md)), and a confirmation is
asked mid-turn, so that stream is the channel it has.

Three constraints shape the design. **The one hard rule:** no confirmation state may live in a
model process, so a pending confirmation is turn-local and dies, as a denial, with its turn.
**ADR-0013's position:** confirmation is the human's, out of band; a possibly jailbroken model must
not be able to forge, bypass or upgrade it, and an action demanded by injected content must never
be only a confirmation away. **The wire contract:** everything crossing body and brain is declared
in [proto/body.proto](../../proto/body.proto) and generated into both toolchains
([ADR-0003](ADR-0003-generated-stubs.md)).

How the email reader answers a search, a folder and a read is a separate decision,
[ADR-0056](ADR-0056-email-reader-answers.md), and the second IMAP server it is measured against is
[ADR-0057](ADR-0057-imap-probe-server.md).

## Decision

### 1. The confirm exchange travels on the `Converse` stream, not a new RPC

A turn lives inside one `Converse` call, so the exchange is oneof members on that stream:
`ServerEvent.confirm_request = 6` and `ClientEvent.confirm_response = 4`.

```proto
message ConfirmRequest {
  string confirm_id = 1;      // correlation id, minted per request by the brain
  string tool_name = 2;       // what would run, e.g. "send_email"
  string arguments_json = 3;  // the exact draft being approved, one JSON object
  string reason = 4;          // why confirmation is required, shown verbatim
}
message ConfirmResponse { string confirm_id = 1; bool approved = 2; }
```

If the stream drops, the turn dies and the pending confirmation dies as a denial, so the hard rule
holds with no persistence at all. `arguments_json` is the dispatcher's `call.arguments` serialized
as one object, so nested drafts survive. **What is approved is what runs:** the dispatcher
serializes the call it then invokes, and a future tool whose adapter rewrote arguments after the
confirm would break this rule. Version skew is harmless on the response side (an old brain ignores
an unknown client event) and fatal on the request side (prost decodes an unknown oneof member as an
empty event and the body fails the turn with `TransportError::Protocol`); both halves come from one
tree, and each commit keeps both green.

### 2. The rule: confirmation is for untainted turns, and tainted turns block

| call | outcome |
|---|---|
| no confirmation required | run |
| confirmation required, **untainted** turn | **confirm**: approved runs; denied, no confirmer or timeout blocks |
| confirmation required, **tainted** turn | **block unconditionally**; the confirmer is never consulted |

This supersedes ADR-0013 decision 4's table. An outbound action is always the user's explicit
decision, so such a tool means the human approves each use. On a tainted turn the model's arguments
may themselves be injection-authored, and a card showing attacker-drafted content to a user used to
clicking approve is not a boundary: after reading hostile bytes, the outbound path is closed for
the rest of the turn. "Read that email, then reply" still works in the next turn, because taint is
turn-local. A caller's own refusal (a spent dispatch budget, a recognized repeat) is checked ahead
of this rule, so it returns before the confirmer is asked.

A block returns one of two `is_error` results, audited, the tool never invoked: `DENIED_MSG` for
the tainted block, and `USER_DECLINED_MSG` for an explicit or defaulted denial, so the model can
tell "the user said no" (pass it on, do not retry) from "this turn is tainted" (explain the block).
The card's reason is `_GATE_REASON` ("this action is outbound or irreversible and runs only with
your approval") unless the policy names a per-tool reason
([ADR-0030](ADR-0030-brain-handoff.md) decision 1).

### 3. A per-stream `SeamConfirmer`, built by an engine factory

The composition root hands the servicer an `EngineFactory` (`engines.py`) rather than one engine.
Each `ConverseStream` builds one `SeamConfirmer` (`confirm.py`) bound to its own output queue, and
the factory builds that stream's dispatcher and engine around it. An engine is a stateless function
over the store, so one per stream costs nothing. The subagent path keeps `confirmer=None`.

`SeamConfirmer.confirm(request)` mints `confirm_id` (`uuid4().hex`), registers a future, and emits
the request on the stream's **control path** (`put_nowait`, no data credit, like the terminal
`SeamError`): the turn task is suspended inside `dispatch`, so waiting for a credit could deadlock
against a stalled consumer, and at most one confirmation is outstanding per stream. It then awaits
the future under `CORTEX_SEAM_CONFIRM_TIMEOUT_S` (default 120 s, limited so an unattended overlay
cannot hang a turn). A timeout denies; a cancellation propagates; a stale or unknown `confirm_id`
is logged and ignored, so a late approval approves nothing; and a client half-close denies a
pending confirm at once. No confirmation state exists outside the awaiting coroutine.

### 4. The send tool: an SMTP twin in `cortex_email`, off by default, declared at the root

`send_email` is `SmtpSender` (`smtp.py`) over smtplib with STARTTLS against the ProtonMail Bridge's
SMTP port (`CORTEX_EMAIL_SMTP_*`, default `127.0.0.1:1025`), one connection per call, run in
`asyncio.to_thread`. `From` is the authenticated Bridge user and never a parameter, so the tool
cannot spoof a sender; the Bridge refusing an alias arrives as the tool's error string. The tool is
registered only when `CORTEX_EMAIL_SEND_ENABLED=true`, which fails at startup without credentials;
otherwise the sidecar is the read-only server. MCP `ToolAnnotations` (`destructiveHint=True` and
the rest) are advisory and never authority.

Which tools need confirmation is declared brain-side, in code under review, so a compromised or
misconfigured sidecar cannot exempt itself. `GatedToolRegistry(inner, gated=...)` in
`cortex_core/aggregate.py` sets `gated=True` on the names in `CORTEX_TOOLS_GATED` and passes
`invoke` through; the dispatcher enforces. It wraps the shared MCP root in `build_tool_registry`,
so the cortex's dispatcher confirms `send_email` and the subagent wiring's `UngatedToolRegistry`
removes it: **subagents never see the send tool.** The default set is `send_email` and
`escalate_to_brain`, so enabling the write path without touching that set still requires
confirmation; a named tool that never appears is harmless. The trust counterpart, the
composition-root overlay that marks a remote tool's result trusted, is ADR-0013's
`OwnTextToolRegistry`, keyed by bytes the brain holds and never by a tool's name.

### 5. The body keeps the client stream open, and the overlay shows a card

`BrainSeamClient::converse(session_id, text, decisions: impl Stream<Item = ConfirmDecision>)` takes
the answers as an input stream, which keeps `body_core` runtime-agnostic, and `TurnEvent` gains a
non-terminal `ConfirmRequest`. The adapter sends
`once(user_turn).chain(decisions.map(confirm_response))` and half-closes when the caller drops its
sender; dropping the event stream still aborts the RPC, which denies any pending confirm.

The overlay holds at most one `pendingConfirm`, set by the event and cleared by the user's answer
and by every turn-ending action. Because dropping the event stream does not half-close the Tauri
request stream, each turn-ending action (`stop`, `dismiss`, `newChat`, `openSession`) first sends
an explicit deny for a still-pending confirm, so the brain resolves it at once rather than at the
timeout. The card renders in the history area with the tool name, the draft as key and value lines,
the reason, and Approve and Deny; a confirm arriving while the panel is hidden shows like a
finished turn and does not fade, since a question waits to be seen. `BrainBridge.respondConfirm`
forwards to the shell's `confirm_response` command, which pushes into the open turn's sender. The
demo bridge scripts a confirm round, so the card can be driven without a brain.

### 6. Validation splits three ways

CI covers the rule, the overlay registry and the subagent removal, `SeamConfirmer`, the send path
over a scripted smtplib, and the confirm round trip in Rust and in the reducer. The agent runs the
live SMTP round trip against the Bridge (`integration`-marked, with a cc, an HTML part and an
attachment, read back over IMAP) and drives the card in a browser. The card through the real Tauri
IPC hop is host-only: [host task 004](../host/tasks/004-confirm-card-over-ipc.md).

### 7. `ConfirmResolved` closes a card the brain stopped waiting on

`ServerEvent.confirm_resolved = 7` has `confirm_id` and `outcome`, emitted only for endings the
client cannot know: `"timeout"` and `"unavailable"` (client input half-closed). None is emitted for
the user's own answer, a cancelled or torn-down turn (its terminal event closes the card), or a
confirm asked after close (no request went out). `outcome` is a documented string rather than an
enum, the same trade this contract made for `SeamError.code`. It travels on the control path for
the request's reason, so a confirmation spends at most two control events. The overlay closes the
card when the id matches and renders nothing else, since the model's reply already explains the
denial; a late click on a resolved card cannot reach the bridge, and no deny is sent for it. The
reducer's action for the user answering is `confirmAnswered`, leaving `confirmResolved` to the
brain's event.

### 8. The subagent dispatcher checks the declared names again

`build_subagents` receives a pre-assembled `ToolDispatcher`, built at the root with
`build_subagent_tools(..., gated_names=...)` from `CORTEX_TOOLS_GATED`. The user's set is
authoritative at every dispatcher whatever a registry advertises, and with `confirmer=None` such a
name there is a hard deny. That closes the one window the structural removal left: a sidecar down
during the removal's walk and up for the invoke.

### 9. A draft is a value object: cc, bcc and HTML

`EmailSender.send(draft: EmailDraft)` takes a frozen value (`to`, `subject`, `body`, and optional
`cc`, `bcc`, `html`, each `""` when omitted), so a new form is a field rather than a new contract.
The MCP tool's matching optional parameters reach the card as ordinary argument rows, with no
brain-side change. `bcc` is composed and `send_message` strips it from the transmitted copy while
still delivering to it. An `html` draft is `multipart/alternative` with the plain body first; a
plain draft stays one `text/plain` part.

### 10. An attachment is text the assistant wrote, inline in the approved draft

`EmailAttachment(filename, content, subtype="plain")` beside `EmailDraft`, passed as
`EmailDraft.attachments`, composes one `text/<subtype>` part each, making the message
`multipart/mixed`. The maintype is not a parameter, as `From` is not: the assistant attaches what
it wrote (a report as `markdown`, a table as `csv`), and never a file it read. This follows from
decision 1's rule: the card shows the content verbatim and approving it sends exactly that. The
limits are `MAX_ATTACHMENTS` (8, refused rather than truncated, since a dropped attachment is a
send the user approved and did not get), `MAX_FILENAME_CHARS` (128, a header value) and
`MAX_ATTACHMENT_CHARS` (32768 characters summed, about half of a 16K-token context, so the limit
comes from authoring rather than SMTP). The subtype must be a MIME token with no `/`, so `text/`
stays a prefix a caller cannot escape.

The card limits the draft to `42vh` and scrolls, keeping every byte on it, and `formatDraftValue`
renders a non-string value as indented `key: value` lines rather than escaped JSON; both are
written against JSON forms, so the card stays generic over any tool.

### 11. The draft rules are the port's, and a send that fails is typed

`refuse_unsendable` in `cortex_email/drafts.py` is every rule a draft is checked against before it
is composed: CR or LF refused in every header value (recipients, subject, filenames), the
attachment limits and the subtype token. The adapter and the fake both call it; a refusal is a
`ValueError`, returned as the tool's error string, and nothing reaches the wire. A send that
reaches nobody (Bridge unreachable, login refused, every recipient refused) raises `SendError` with
the library's text kept. A send accepted for some recipients and refused for others answers
`drafts.confirmation` with the refused addresses appended, because the message has left and raising
would report a send that partly happened as failed.

### 12. The model reads what each attachment field must hold

`values.py` holds the three limits and the per-field descriptions pydantic lifts into the
advertised schema, so the prose a model reads and the check that refuses a send use one constant.
`content` is the file itself, never a path or a URL, and nothing is read from disk; `subtype` is
the token after `text/`, naming `text/markdown` as the wrong form; `filename` names its limit and
asks for a matching extension; the array names both of its limits. The limits are enforced after
the user approved the card, so a wrong guess costs a second approval.

## Consequences

- A later outbound action inherits the whole loop through `gated=True` (a built-in) or
  `CORTEX_TOOLS_GATED` (a remote tool), with no wire change. `escalate_to_brain` is the second.
- **Confirmation fatigue:** every such call prompts, and `ToolDispatcher._confirmed` remembers
  nothing between calls. Batching or a per-tool session allowlist waits in
  [R-214](../refinements/tasks/214-batching-session-allowlists.md) for prompts to become frequent.
- The email sidecar is read-only by default, write-enabled by explicit opt-in with the write path
  requiring confirmation brain-side, and has no filesystem access. A tainted turn that must send
  costs one more turn.

## Alternatives rejected

- **A unary `RespondConfirm` RPC.** The answer's lifetime would no longer match the turn's: the
  brain would need a cross-stream registry, and a dead stream would stop meaning a denial.
- **`ToolAnnotations` as the authority.** It fails open (an omitted annotation leaves an outbound
  tool unconfirmed) and hands policy to the sidecar.
- **A process-wide `ContextVar` confirmer** hides the stream-to-turn routing in ambient state; **a
  per-turn confirmer through `TurnCapabilities`** changes core signatures for wiring.
- **Confirm-with-provenance for tainted turns** (declined 2026-07-16). A source line does not
  change what the card asks and makes the user the injection target, and the provenance that would
  name an attacker (`SENDER`, `URI`) has no producer, `ToolResult` having no source field
  ([ADR-0027](ADR-0027-turn-provenance.md)).
- **Attachments as a filesystem path or a base64 blob.** A path is read after approval, so the user
  approves a name rather than a payload, and it needs a mount and a file-read capability on the
  outbound sidecar; base64 is bytes no person can read off a card.
- **Real-file attachments, bytes the assistant did not author** (declined 2026-07-16). Granting the
  sidecar that sends mail off the machine the power to read local disk fuses read-local and
  write-remote, and a card can bind the bytes (a digest) but never the file choice, which is what
  an injection controls. The taint rule already blocks "read this file, then send it" in one turn.
  If a consumer appears, the build is all of: a scoped source (an outbox mount or an opaque handle,
  never an arbitrary path), the file choice refused when named on a tainted turn, and a
  digest-bound card the sidecar checks again at send.

## Related

- [ADR-0013](ADR-0013-untrusted-content.md) (taint, confirmation, own texts),
  [ADR-0027](ADR-0027-turn-provenance.md), [ADR-0030](ADR-0030-brain-handoff.md) (per-tool reasons,
  `escalate_to_brain`), [ADR-0056](ADR-0056-email-reader-answers.md) (the reader's answers),
  [ADR-0057](ADR-0057-imap-probe-server.md) (the probe server).
- Modules: [brain-email](../modules/brain-email.md),
  [brain-orchestrator](../modules/brain-orchestrator.md),
  [`cortex_seam`](../modules/brain-seam.md); runbooks:
  [email-imap](../runbooks/email-imap.md), [body-overlay](../runbooks/body-overlay.md).
- [docs/refinements/index.md#email-confirmer](../refinements/index.md#email-confirmer).
