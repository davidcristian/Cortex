# ADR-0022: Email-write as the first gated outbound tool + the real Confirmer

- **Status:** Accepted (Slice 8.8)
- **Date:** 2026-07-08

## Context

Every capability shipped so far is read-only or reversible. Slice 8.8 lands the first
**outbound, irreversible** action (sending an email) and with it the machinery every later
gated action (Slice 9 OS actions, Slice 9.5 side-effectful reminders) reuses:

- The capability gate exists and is proven (ADR-0013): `ToolSpec.gated`, the dispatcher's
  block, the `Confirmer` port. But the port has shipped **inert** since Slice 6.5
  (`confirmer=None`, fail-closed), because no gated tool existed to need it.
- The email sidecar (`cortex_email`, ADR-0009) is read-only IMAP by construction; the SMTP
  write path is its planned twin (ROADMAP cross-cutting item, Phase-0 assumption 6).
- The overlay talks to the brain over the bidi `Converse` stream (ADR-0011), and the brain
  cannot yet dial the body (`BodyService` is served from Slice 9), so a confirmation
  round-trip has exactly one live channel available: the `Converse` stream itself.

Three constraints shape the design. **(1) The one hard rule:** no confirmation state may
live in a model process; a pending confirmation must be turn-local, dying (denied) with its
turn. **(2) ADR-0013's posture:** confirmation is the human's, out of band. A possibly
jailbroken model must not be able to forge, bypass, or upgrade it; and an action demanded
by injected content must never be *merely a confirmation away*. **(3) The seam contract:**
`proto/body.proto` is the single source of truth; anything crossing body↔brain is declared
there and regenerated into both toolchains (ADR-0003).

## Decision

### 1. The Confirm exchange rides the `Converse` stream, not a new RPC

A gated call is confirmed **mid-turn**, and a turn lives inside one `Converse` call. So the
confirmation exchange is two new oneof members on the existing stream (field numbers
appended, never renumbered):

```proto
message ServerEvent { oneof event { … ConfirmRequest confirm_request = 6; } }
message ClientEvent { oneof event { … ConfirmResponse confirm_response = 4; } }

message ConfirmRequest {
  string confirm_id = 1;      // correlation id, minted per request by the brain
  string tool_name = 2;       // what would run, e.g. "send_email"
  string arguments_json = 3;  // the exact draft being approved, one JSON object
  string reason = 4;          // why confirmation is required, shown verbatim
}
message ConfirmResponse {
  string confirm_id = 1;      // echoes the request
  bool approved = 2;
}
```

Riding `Converse` keeps the pending confirmation **turn-local by construction**: if the
stream drops, the turn dies and the pending confirmation dies as a denial, so the hard rule
holds with no persistence design at all. It is also the trigger ADR-0011 deferred ("picked
up when client events start to interleave"): the body's client stream stays open past the
first `UserTurn` (decision 5). The brain-side pump (`converse.py`) already reads client
events continuously mid-turn (queued turns, `Cancel`), so routing a `confirm_response` is
one more pump case, not a new architecture. `arguments_json` is one JSON object (the
dispatcher's `call.arguments` serialized) rather than repeated key/value pairs so nested
drafts survive; the overlay renders it as key→value lines and falls back to raw JSON.

**Version skew** is fail-quiet by construction on the response side (an old brain
debug-logs and ignores an unknown client event) but *terminal* on the request side: prost
drops an unknown oneof member, so an old body decodes a `confirm_request` as an empty
event and fails the turn with `TransportError::Protocol`. That only bites a mixed-version
deployment mid-confirm, impossible on this single-machine repo where both halves ship
from one tree, and the slice's commits keep each tree green independently (the ADR-0021
staging pattern).

### 2. The gate table is revised: confirmation moves to the *untainted* branch

ADR-0013 decision 4 shipped: not gated → run; gated ∧ ¬tainted → run; gated ∧ tainted →
confirm-or-block. That table was written when no tool was gated and nothing could prompt.
With a real outbound tool the ROADMAP's stricter composition applies, and this ADR
supersedes that table (ADR-0013 carries a pointer addendum):

| call | outcome |
|---|---|
| not gated | run (unchanged) |
| gated, **untainted** turn | **confirm**: approved → run; denied / no confirmer / timeout → block |
| gated, **tainted** turn | **block unconditionally**. The Confirmer is never consulted |

Two reasons. First, an outbound/irreversible action should *always* be the user's explicit
decision, so "gated" now means "the human approves each use", not "the human approves it only
when the turn is suspicious". Second and load-bearing: on a tainted turn the model's
arguments may themselves be injection-authored (the exfil-via-`send_email` corpus case,
ADR-0013 harness), and a confirmation dialog showing attacker-drafted content to a user
conditioned to click "approve" is not a boundary, since **a send demanded by injected content
must never be merely a confirm-away**. The tainted block keeps the deterministic guarantee
the whole untrusted-content posture rests on: after reading hostile bytes, the outbound
surface is closed for the rest of the turn, full stop. The legitimate "read that email,
then send a reply" flow still works: send in the next turn, because taint is turn-local, tool
context does not persist (ADR-0013 decision 3), and the fresh turn confirms normally. The
cost (one extra user prompt-turn) is accepted; a confirm-with-provenance-display
alternative for tainted turns is deferred, needing structured provenance first
(ADR-0013/0019 deferral).

Denial messages become two, both `is_error` results, audited, tool never invoked: the
existing `DENIED_MSG` stays the tainted-block text (it already explains untrusted
content), and a new `USER_DECLINED_MSG` is returned on an explicit or defaulted denial of
an untainted confirm. The model must be able to tell "the user said no / was unreachable"
(relay, don't retry) from "this turn is tainted" (explain the block). The dispatcher's
`_GATE_REASON` becomes the untainted-confirm request text ("this action is outbound or
irreversible and runs only with your approval"), carried verbatim as the wire `reason`.

### 3. The brain-side adapter: a per-stream `SeamConfirmer` behind an engine factory

`TurnEngine` and its `ToolDispatcher` are built once in `wiring.py` and shared by every
stream today. But a confirmation must reach *the stream running the turn*. The
composition root therefore hands the servicer an **engine factory**,
`make_engine(confirmer: Confirmer | None) -> TurnEngine`: a closure over the shared
adapters (store, backend, memory, registry, spawn tool, window, guardrail) that builds the
cheap pure objects (dispatcher, capabilities, engine) per stream. Engines are stateless
functions over the store (the one hard rule), so per-stream construction costs nothing and
keeps the routing explicit. `BrainService` and `converse()` take the factory; each
`_ConverseStream` builds one `SeamConfirmer` (new orchestrator module `confirm.py`) bound
to its own output queue and pending-response registry, and runs `make_engine(confirmer)`.
The core is untouched (`TurnEngine`'s constructor, `TurnCapabilities`, and the subagent
path (which keeps `confirmer=None`, ADR-0013 defense-in-depth) are all unchanged).

`SeamConfirmer.confirm(request)`:

1. mint `confirm_id` (`uuid4().hex`), register an `asyncio.Future` in the stream's router;
2. emit `ServerEvent.confirm_request` onto the output queue via the **control path**
   (`put_nowait`, bypassing the credit semaphore exactly like the terminal `SeamError`):
   at most one confirmation is outstanding per stream (turns are sequential, the tool loop
   is sequential, subagents cannot confirm), so the unbounded queue grows by at most one,
   and a stalled consumer can never deadlock the request behind exhausted data credits
   while the turn task sits suspended inside `dispatch()`;
3. await the future under `asyncio.timeout(confirm_timeout_s)`, where timeout → deregister →
   **False** (fail-closed); cancellation (turn cancelled, stream torn down) → deregister →
   propagate (the turn is dying; nothing runs);
4. the pump routes a `confirm_response` to the registry and resolves the future; an
   unknown or stale `confirm_id` is logged and ignored (a late approval after timeout must
   not approve anything, because the denial already happened and was audited); when client input
   ends (half-close), any pending future resolves False immediately, since no answer can ever
   arrive.

The timeout is `CORTEX_SEAM_CONFIRM_TIMEOUT_S` on `SeamServerConfig` (default **120**, which is
generous for a human decision, bounded so an unattended overlay cannot hang a turn
forever). No confirmation state exists outside the awaiting coroutine: nothing is
persisted, nothing survives the turn, re-asking is the recovery from any interruption. This is
the hard rule by construction. (`config.py` sits at 299/300 lines; the setting lands with
the module split that has precedent in `subagent_builders.py`.)

### 4. The send tool: an SMTP twin in `cortex_email`, off by default, gated at the root

**The tool.** `send_email(to, subject, body) -> str` joins the email sidecar as the write
twin of the Slice 6 reader: an `SmtpSender` (new `smtp.py`, the `ImapMailbox` pattern of
per-call connection, same ssl-context/`tls_insecure`/`ca_cert` semantics) over
**smtplib + STARTTLS** against ProtonMail Bridge SMTP, config under `CORTEX_EMAIL_SMTP_`
(default port **1025** is the Bridge's SMTP loopback; *an assumption from Bridge defaults,
verified in the live run and documented in the runbook*). `smtplib` is sync, so the tool
body runs in `asyncio.to_thread` like the reader; the message is a stdlib `EmailMessage`
via `send_message`. The sender authenticates as the Bridge user and sends **as that user**
(`From` is the authenticated address, never a parameter, so the tool cannot spoof a sender).
One recipient string, subject, plain-text body: exactly the draft the user approves;
richer shapes (cc/bcc/HTML/attachments) are deferred until something needs them.

**Off by default.** `build_server(reader, sender=None)` registers `send_email` only when a
sender is passed, and `main()` builds one only when `CORTEX_EMAIL_SEND_ENABLED=true`
(explicit, default false; enabled without credentials fails fast at startup). Absent the
flag the sidecar is byte-for-byte the Slice 6 read-only server, so its
read-only-by-construction property holds for every existing deployment, and enabling the
write path is a deliberate, documented act. The tool also carries MCP `ToolAnnotations`
(`readOnlyHint=False, destructiveHint=True, openWorldHint=True`) as *advisory* metadata
for any MCP client and never authority (below).

**Gated at the composition root.** The brain sees `send_email` through `McpToolRegistry`,
which builds specs generically and never sets `gated` (it also drops annotations and
must keep dropping them as authority: gating is declared *in code under review on the
brain side*, per ADR-0013 decision 4, so a compromised or misconfigured sidecar cannot
un-gate itself by editing its own metadata). This slice adds the deferred composition-root
overlay (ADR-0013 "per-remote-tool trust / gating overrides"): a port-preserving core
combinator next to its siblings in `aggregate.py`

```python
GatedToolRegistry(inner, gated=frozenset_of_names)
```

whose `describe_tools` stamps `gated=True` onto matching specs and whose `invoke` passes
through (the *dispatcher* enforces; the overlay only declares). It wraps the shared MCP
registry root in `build_tool_registry`, so both consumers inherit it: the cortex's
dispatcher sees `send_email` as gated (confirm path), and the subagent wiring's
`UngatedToolRegistry` (ADR-0013 structural exclusion) strips it. **Subagents never see
the send tool at all**, not merely a denial. Config: `CORTEX_TOOLS_GATED`, a name set
**defaulting to `{"send_email"}`**. Enabling the sidecar's write path without touching
gating config still gates it (fail-closed pairing); a gated name that never appears is
harmless. Trust overlays (the other half of that deferral) stay deferred: nothing needs a
trusted remote tool yet.

### 5. The body keeps the client stream open; `converse` takes a decision stream

`BrainSeamClient::converse` today sends one `UserTurn` and half-closes; the reply stream's
drop cancels the turn (ADR-0011). To carry responses, the port gains an *input*:

```rust
// body_core
pub struct ConfirmDecision { pub confirm_id: String, pub approved: bool }
// TurnEvent gains (non-terminal):
ConfirmRequest { confirm_id: String, tool_name: String, arguments_json: String, reason: String }

fn converse(
    &self,
    session_id: &str,
    text: &str,
    decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send;
```

An input `Stream` (not a returned handle) keeps `body_core` runtime-agnostic. The caller
owns whatever channel feeds it (the Tauri glue uses a tokio mpsc; tests use scripted
streams; a caller with no confirm surface passes `futures::stream::empty()` **only if** it
wants an immediate half-close, or a held-open channel otherwise). The adapter builds the
request stream as `once(user_turn).chain(decisions.map(confirm_response))`, and the client
half-closes when the caller drops its sender. Drop-to-cancel is unchanged: dropping the
*event* stream still aborts the RPC whatever the sender does, the brain-side teardown path
(already exercised by disconnect tests) denies any pending confirm, and a decision sent
after teardown is a no-op (the stale-id case the brain ignores). Terminal bookkeeping is
unchanged: the client stops at `TurnComplete`/`SeamError` and drops everything.
(`tokio`/`tokio-stream` promote from dev-dependencies in `body-rpc`; the confirm mapping
gets its own module if `converse.rs` nears the line cap, following the `sessions.rs` precedent.)

The overlay (all CI-gated but the Tauri glue): TS `TurnEvent` gains `confirmRequest`
(field names fixed by the serde camelCase mirror); `OverlayState` holds at most one
`pendingConfirm`. It is set by the event, cleared by the user's answer and by every
turn-ending action. Because dropping the event stream mutes the JS sink but does *not*
half-close the Tauri request stream, each turn-ending action (`stop`/`dismiss`/`newChat`/
`openSession`) also sends an **explicit deny** for a still-pending confirm before it drops
the turn, so the brain resolves the confirm immediately (fail-closed, because the user did not
approve) instead of leaving a zombie turn suspended until the timeout; the
approval card renders in the history area (the design doc's inline-chip layer, its first
real occupant) with tool name, the parsed draft as key→value lines, the reason, and
Approve/Deny per the overlay design language; a confirm arriving while the panel is
hidden surfaces like a completed turn (orb → preview) but **does not auto-fade**, because the
"errors wait to be seen" rule extends to a question. `BrainBridge.respondConfirm(confirmId,
approved)` forwards to a new `confirm_response` Tauri command that pushes into the open
turn's held sender (per-turn state in the shell, which is UI glue, the same ungated class as
`converse`/`sessions`). The demo bridge scripts a confirm round so the UI is drivable
without a brain; `overlay-ux.md` gains the card's spec.

### 6. Validation splits three ways (the established rhythm)

- **CI (100%, no GPU/SMTP/GUI):** the revised gate table (every branch, both denial
  messages), `GatedToolRegistry` + composition (subagent strip proven and proven to
  *fail* without the overlay: a test asserts `send_email` arrives brain-side gated),
  `SeamConfirmer` (approve/deny/timeout/stale-id/input-end/teardown over fakes), the
  engine-factory wiring, `SmtpSender`+`send_email` over patched smtplib fakes (the
  `ImapMailbox` test pattern, both registered and absent branches), regenerated stubs +
  facade exports on both sides, Rust contract tests scripting the fake brain through a
  confirm round-trip (approve and deny), overlay reducer/card/bridge tests.
- **Agent, via Docker (mine):** the live SMTP round-trip between the two `example.com`
  addresses over the user's ProtonMail Bridge, `integration`-marked, arrival verified
  through the existing IMAP reader; plus the brain-side confirm flow against the real
  stack where reachable.
- **User, Windows host:** the overlay approval prompt driven end to end (hotkey → turn →
  gated send → card → approve/deny), the one genuinely OS-host-only piece, as ADR-0013
  predicted.

## Alternatives rejected

- **A separate unary `RespondConfirm` RPC.** Smallest body-side diff (the `sessions.rs`
  pattern, rides the ADR-0016 token interceptor unchanged). But the response's lifetime
  no longer matches the turn's: the brain needs a *cross-stream* pending-confirmation
  registry keyed by id, answers can arrive for dead turns as a matter of course rather
  than as a race, and stream-death-means-deny stops being structural. The in-stream shape
  keeps every guarantee local to `_ConverseStream`.
- **`ToolAnnotations` as gating authority.** MCP 1.28 carries `readOnlyHint` et al., and
  mapping `gated = not readOnlyHint` looks free. But it fails open (a sidecar that omits
  the annotation ships an ungated outbound tool) and hands policy to the sidecar (a
  compromised server un-gates itself). Annotations stay advisory; the brain-side overlay
  with a fail-closed default set is the authority.
- **A ContextVar-routed process-wide Confirmer.** Avoids the factory, but hides the
  stream→turn routing in ambient state, which is harder to test, invisible in signatures, and
  contrary to "DI at the edge". The factory is one closure in the composition root.
- **A per-turn confirmer through `TurnCapabilities`.** The confirmer is per-*stream*, not
  per-turn, and threading it through the core's capability bundle changes core signatures
  for what is purely seam wiring. The factory keeps the core byte-for-byte untouched.
- **An is-error-only denial (no distinct user-declined text)** was rejected already in
  ADR-0013; the two-message split exists so the model can respond honestly to "no".

## Consequences

- The first user-approval loop exists end to end; Slices 9/9.5/10 gated actions inherit it
  by setting `gated=True` (built-ins) or a `CORTEX_TOOLS_GATED` entry (remote tools), with no
  seam change.
- `proto/body.proto` grows two messages + two oneof members; both stub trees regenerate
  (`just proto`), the facade re-exports the new messages, and the grpcio/protobuf floors
  are re-checked on regen (ADR-0003).
- ADR-0013's decision-4 table is superseded by decision 2 (pointer addendum there); its
  `confirmer=None` fail-closed default now also denies every untainted gated call, and the
  gate tests are rewritten to the new table, not appeased.
- The Slice 6 email sidecar is no longer read-only *by identity*. It is read-only **by
  default**, write-enabled by explicit opt-in, with the write path gated brain-side; the
  compose file's "read-only by construction" comment and `brain-email.md` are updated.
- `wiring.py` hands the servicer a factory, not an engine. The last per-process singleton
  between a turn and its capabilities is gone, which Slice 11's swap orchestration will
  want anyway.
- The orchestrator's `config.py` splits (at 299/300 lines) before gaining
  `CORTEX_SEAM_CONFIRM_TIMEOUT_S` and `CORTEX_TOOLS_GATED`.

## Risks

- **Confirmation fatigue** (carried from ADR-0013): every send prompts. Accepted for a
  personal assistant sending occasional email; batching/allowlists are deferred policy.
- **Approve-after-timeout race:** the user clicks approve at second 121; the turn already
  denied and the model already said so. The stale id is ignored, the audited denial
  stands, which is correct but potentially confusing. Mitigated by the generous default and the
  reply text; a structured confirm-resolution event for the overlay is deferred.
- **What-you-approve-is-what-runs** holds because the dispatcher serializes `call.arguments`
  for the request and invokes with the same `call`. A future gated tool whose adapter
  rewrites arguments post-confirm would break it. Recorded as a rule: `arguments_json` is
  the executed contract.
- **`From` spoofing** is closed by construction (authenticated sender only), but the
  Bridge rejects an alias mismatch late (SMTP error), surfaced as the tool's error string.
- **Bridge SMTP specifics** (port 1025, STARTTLS) are believed-not-verified until the live
  run; wrong defaults cost only config, not design.

## Deferred (recorded in the ROADMAP)

- Confirm-with-provenance for tainted turns (needs structured provenance, ADR-0013/0019).
  **Declined 2026-07-16** once the provenance landed (addendum below): reversing the fail-closed
  block is rejected on the merits, and the useful `SENDER`/`URI` provenance has no producer anyway.
- Richer send shapes behind the same tool name: **cc/bcc/HTML landed 2026-07-13** (addendum
  below); **authored-text attachments landed 2026-07-15** and **real-file attachments (bytes the
  assistant did not author) were declined 2026-07-16** (addenda below), the capability kept
  ungranted on the outbound sidecar.
- A structured confirm-resolution event so the overlay can close a stale card exactly.
  **Landed 2026-07-14** (addendum below).
- Trust (as opposed to gating) overlays for remote tools. Still nothing needs one.
- Batching / per-tool session allowlists against confirmation fatigue.
- Salience of `ToolActivity`: **landed 2026-07-12** end to end (the shared tool loop emits a
  registry-authored `ToolActivity` per audited dispatch, the overlay renders it as an inline
  chip; ADR-0009 chip addendum). The confirm card was the first mid-turn tool surface; the
  general activity chip is now the second. The *dispatch* rate/salience policy this line
  originally gestured at stays a separate deferral (ADR-0009 risks).
- **The subagent-side authoritative gated-name backstop is available but not wired.**
  `ToolDispatcher` and `build_subagent_tools` both accept `gated_names` (the post-review
  hardening that makes the *cortex's* gate independent of advertisement), but
  `build_subagents` does not pass it (a 7th arg trips the PLR0913 cap), so a subagent's
  dispatcher runs with an empty set. Subagents stay protected by the two structural layers
  they already have, namely `UngatedToolRegistry` (strips gated specs and refuses a gated name by a
  live walk at invoke) plus `confirmer=None` (fail-closed). These cover every case except the
  astronomically narrow skip-mode double-walk window (a sidecar down for the strip's walk yet
  up for the inner invoke walk, with the subagent independently emitting the exact gated name).
  Wiring the backstop through is a small change behind the unchanged `build_subagent_tools`
  seam if that residual ever matters. *Closed by the 2026-07-12 addendum below.*

## Addendum (2026-07-08): agent validation of overlay UI (Chrome) + gating over real MCP (Docker)

Two of the three validation arms were run by the agent this session; only the pieces that need
the ProtonMail Bridge or the Windows Tauri shell remain.

**Overlay confirm card (Chrome, demo bridge).** Ran the overlay under `vite dev` and drove the
gated-send flow in a real browser: a "send an email" prompt surfaces the `ConfirmCard` exactly to
spec. The shield + `send_email`, the draft as verbatim `to`/`subject`/`body` key→value lines, the
reason line, and Deny (neutral) vs Approve (accent gradient). **Approve** clears the card and the
reply resumes ("Sent …"); **Deny** clears it and the reply resumes ("Okay, not sent. The draft
is discarded."); multi-turn history is preserved across rounds. This exercises the real React
component, the reducer wiring, and the `BrainBridge` interface. That is everything but the Tauri IPC
transport (the `WireEvent` serde ↔ TS mapping, the `confirm_response` command, `ConfirmRoute`),
which stays host/Windows-only.

**Gating overlay + send tool over real MCP (Docker).** Brought up the `cortex_email` sidecar with
`CORTEX_EMAIL_SEND_ENABLED=true` and dogfooded it through the real `McpToolRegistry`:
- `send_email` **registers** (all four tools present) and arrives `gated=False` over MCP. The
  sidecar never self-declares gating, while the composition-root `GatedToolRegistry` stamps it
  `gated=True` and leaves the three read tools ungated. The ADR-0022 overlay, proven end to end.
- A `send_email` call that cannot reach the Bridge returns a **clean `is_error`** result
  (`Connection refused`), not a crash or a hang (the FastMCP exception path).
- With `CORTEX_EMAIL_SEND_ENABLED=false` the sidecar is **read-only by default**. `send_email` is
  absent, only the three read tools register.

**Live SMTP + IMAP round-trip (real ProtonMail Bridge).** Once the user added a Windows
`netsh` portproxy (the vEthernet-(WSL) adapter → the Bridge's `127.0.0.1:1143/1025`, since this
distro is `nat`-mode with `interop=false` and can't reach Windows loopback directly), the
`integration`-marked live tests passed against the real Bridge: the read-only IMAP reader
(`test_reader_lists_and_reads_from_a_live_bridge`), and (the headline) **`send_email` really
sent one message over SMTP and the test found it back over IMAP by its unique subject within the
60 s window** (`test_send_round_trips_between_the_two_test_addresses`, ~13 s end to end). The
whole write path (`SmtpSender` → Bridge SMTP (STARTTLS) → delivery → IMAP search) is proven end
to end; `From` was the authenticated account (never a parameter), the CR/LF guard and the
opt-in/gating all in the loop.

**Still pending (genuinely OS-native, host-only):** the **Windows Tauri confirm-card**
validation (hotkey → gated send → card → approve/deny through the real IPC transport). It is the one
piece Chrome/Docker can't reach, exactly as ADR-0013 predicted.

## Addendum (2026-07-12): the subagent gated-name backstop is wired

The deferred wiring above is done, through the unchanged `build_subagent_tools` seam and
without a seventh argument: `build_subagents` no longer assembles the subagent dispatcher
itself. It now receives it pre-assembled (`tools: ToolDispatcher | None` replaces the
`tool_registry` parameter), and the composition root builds it with
`build_subagent_tools(tool_registry, clock, gated_names=tools_config.gated)`, the same
bundling move that kept `build_cortex_tools` under the argument ceiling (one pre-assembled
collaborator instead of one parameter per concern). `CORTEX_TOOLS_GATED` therefore now
covers subagents exactly as it covers the cortex and the schedule ticker: the user's set
is authoritative at the dispatcher regardless of advertisement, and `confirmer=None` turns
a gated name into a hard deny, closing the skip-mode double-walk window. The dispatcher's
behavior under `gated_names` was already pinned by the existing backstop test; the builder
tests now assemble the dispatcher exactly as the composition root does.

## Addendum (2026-07-13): richer send shapes (cc/bcc/HTML) behind an `EmailDraft` seam

The deferred richer-send-shapes refinement lands for **cc, bcc, and an HTML alternative**,
entirely inside the `cortex_email` sidecar and behind the **unchanged brain-side gate**: the
brain still sees the tool by the name `send_email` in `CORTEX_TOOLS_GATED`, still stamps it
`gated`, and the confirm card still renders the draft as generic `key→value` argument lines
(now including any `cc`/`bcc`/`html` the model authored), so the gate, the taint table, and the
`SeamConfirmer` are all untouched. No proto, port, or orchestrator change.

**The seam is a value object, not a wider signature.** `EmailSender.send` changed from
`send(to, subject, body)` to `send(draft: EmailDraft)`, where `EmailDraft` is a frozen value
(`to`/`subject`/`body` + optional `cc`/`bcc`/`html`, each defaulting to `""` = omitted). This is
the deliberate extension point: the still-deferred **attachments** shape becomes one more field
on `EmailDraft`, never another change to the `send` contract or to every fake that implements it.
The MCP `send_email` handler gained matching optional parameters, so the richer shapes flow to the
cortex as ordinary advertised tool arguments with no brain-side plumbing.

**Safety carried forward.** `cc` and `bcc` get the same in-code CR/LF header-injection refusal as
the recipient and subject (a laundered `\r\nBcc:` in any address field is rejected before the
wire, not left to the interpreter's patch level). `From` is still the authenticated identity,
never a parameter. A `bcc` is composed as a header but `smtplib.send_message` deletes it from the
transmitted copy while still delivering to it, so a blind recipient stays hidden from the To/Cc
readers (stdlib behavior, exercised by the live round-trip). An `html` draft composes a
`multipart/alternative` (plain `body` fallback first, then the HTML part); a plain draft is
byte-for-byte the previous single `text/plain` message.

**Validation.** CI-gated at 100% over the fake smtplib (cc/bcc/html composition, the two new
header-injection refusals, the plain-draft-stays-text/plain regression) and the in-process MCP
server (the tool forwards the new arguments onto the draft). The `integration`-marked live
round-trip now sends with a `cc` back to the sending account and an HTML alternative, so a real
Bridge run validates cc/HTML composition end to end, not just the plain path.

**Attachments remain deferred**, recorded here as the open sub-item: they need a bytes-transport
decision the other shapes did not (a path into the sidecar's mounted filesystem, which adds a
file-read capability to the email sidecar, versus a base64 blob in the JSON tool argument, which
bloats the call and the audit line). Chosen deliberately as a separate increment so this slice
stays a pure header/body composition change with no new capability surface. It lands as a new
`EmailDraft` field behind this same seam.

## Addendum (2026-07-14): the structured confirm-resolution event

The deferred "structured confirm-resolution event so the overlay can close a stale card
exactly" lands. Until now a `ConfirmRequest` had exactly one ending the overlay could see:
the user answering it. The brain's *own* endings were invisible on the wire, so the card
stayed interactive until the turn's terminal event cleared it. That is this ADR's
approve-after-timeout risk seen from the overlay: at second 121 the user clicks Approve on a
question the brain answered for them at second 120, the stale id is ignored, and the card
leaves looking exactly as though the click did something.

### 1. The event, and the two endings it reports

```proto
message ServerEvent { oneof event { … ConfirmResolved confirm_resolved = 7; } }

message ConfirmResolved {
  string confirm_id = 1;  // which ConfirmRequest ended
  string outcome = 2;     // "timeout" | "unavailable"
}
```

**It is emitted only for endings the client cannot already know**, which is what makes it a
closing signal rather than a chatty echo:

| how the confirm ended | emitted? | why |
|---|---|---|
| the user answered (approve or deny) | no | the client authored that fact and cleared its own card when it sent the answer |
| `CORTEX_SEAM_CONFIRM_TIMEOUT_S` elapsed | **yes**, `"timeout"` | the whole gap: the brain denied and the card is now a lie |
| client input half-closed (`close`) | **yes**, `"unavailable"` | no answer can ever arrive, so the question is void |
| the turn was cancelled or the stream died | no | the turn is dying and its terminal event (or the stream's death) already closes the card; `endTurn` in the reducer has always done this |
| `confirm` called after `close` | no | it emitted no request either, so there is no card to close |

That table is the whole contract. The overlay needs no rule beyond "a resolution for the
card I am showing closes it", and every path that does *not* emit is one the overlay already
handles, so nothing regresses to a timeout-shaped hole.

**`outcome` is a string, not a proto enum.** An enum would buy a typed value at the price of
an unknown-value branch on both sides of any version skew, for a field whose only job is to
explain. This seam already settled that trade the other way for `SeamError.code` and
`StatusUpdate.state`, and the Rust mirror keeps `TurnEvent::Status{state}`'s shape: the
vocabulary is documented at the message and passed through as text.

**The overlay closes the card and renders nothing else.** The explanation surface already
exists and is the model's own reply: `USER_DECLINED_MSG` tells the model to relay the
declined action to the user, so a resolved card pinned beside that sentence would be a second
account of one fact, which the overlay design language spends nothing on. `outcome`
nonetheless rides the wire documented, so a later surface (a badge on the reply, an audit
view) needs no seam change. That is the `DueReminder.session_id` precedent from ADR-0025,
where the field shipped one slice before the control that used it.

### 2. It rides the control path, for the request's reason

The resolution is emitted from inside `SeamConfirmer`, while the turn task is still suspended
inside `dispatch`, which is exactly where the request is emitted. So it takes the same control
path (`put_nowait`, no data credit): acquiring a credit there could deadlock against a stalled
consumer. The over-credit accounting in `_ConverseStream.events` therefore widens from one to
at most two per confirmation, still bounded by "at most one confirmation is outstanding per
stream" and still single digits of drift over a session, never unbounded.

**Version skew is the `confirm_request` case unchanged** (decision 1): an old body drops the
unknown oneof member, decodes an empty `ServerEvent`, and fails the turn with
`TransportError::Protocol`. Both halves ship from one tree, and each commit keeps both green.

### 3. The overlay: one reducer case, and a rename that pays for itself

`{kind: "confirmResolved"}` was the reducer action for *the user answering*. It is now
`confirmAnswered`, freeing `confirmResolved` for the brain's event and making both names say
which side acted. The new case closes the card only when the id matches the one on screen; a
resolution for anything else is a no-op, the same stale-id property every other confirm path
has. Two behaviours then fall out of the card being gone rather than needing their own code:
the ghost click cannot reach the bridge at all (`respondConfirm` already refuses an answer
that is not the live question), and the explicit deny each turn-ending action sends
(`stop` / `dismiss` / `newChat` / `openSession`) is skipped for a resolved confirm, keeping
the answer the user never gave off the wire.

### 4. Validation

- **CI (100%):** the confirmer emits on timeout and on close, and stays silent for an
  answered confirm, a never-asked one (post-`close`), and a cancelled one; `converse` carries
  the resolution to the wire ahead of the turn's remaining deltas; the adapter maps
  `ConfirmResolved` to a non-terminal `TurnEvent::ConfirmResolved` against the scripted fake
  brain; the reducer closes on a matching id and no-ops otherwise.
- **Agent, in a browser:** the demo bridge scripts a confirm that times out, so the card
  closing on its own is drivable without a brain. Its draft also carries an attachment
  (attachments addendum), which is how the card's two long-draft defects were found.
- **User, Windows host:** unchanged. The Tauri IPC transport carries one more `WireEvent`
  variant through the same serde mirror.

## Addendum (2026-07-15): attachments are authored text, inline in the approved draft

The last deferred send shape lands. The open question was never the field (the richer-shapes
addendum built `EmailDraft` to take it) but **where the bytes come from**, and what settles it
is not a transport comparison. It is this ADR's own rule, from the Risks above:
**`arguments_json` is the executed contract.** The confirm card renders the draft the
dispatcher is holding, and approving it runs exactly that. Apply the rule to each candidate
and the decision falls out.

### 1. What an attachment is

`EmailAttachment(filename, content, subtype="plain")`, a frozen value beside `EmailDraft`,
carried as `EmailDraft.attachments: tuple[EmailAttachment, ...] = ()`. Each one composes a
single `text/<subtype>` part through `EmailMessage.add_attachment`, so a draft with
attachments is `multipart/mixed` (holding the existing single part or `multipart/alternative`
unchanged, plus one part per attachment).

**The maintype is not a parameter, exactly as `From` is not.** `text/*` is the entire
vocabulary, which makes the capability statable in one sentence: the assistant can attach
**what it wrote**, as a file (a report as `markdown`, a table as `csv`, an invite as
`calendar`, a log as `plain`). It cannot attach a file it read, because it has none to read.

### 2. Why the two candidates this deferral recorded were both wrong

| candidate | what the card shows | what actually leaves |
|---|---|---|
| a filesystem path | the path | whatever that file holds **after** approval |
| a base64 blob | roughly 1.4 KB of base64 per KB of payload | bytes no human can read off a card |
| authored text (chosen) | the content, verbatim | the same content |

Both rejected candidates fail the executed-contract rule, and that is the disqualifier, not
their cost. A path is the worse of the two: the bytes are read after the click, from a
filesystem that can change in between, so the approval is for a name rather than a payload.
Their costs are real too and were the ROADMAP's warning: a path needs a `volumes:` mount
**and** a file-read capability on a sidecar deliberately built with neither, re-opening the
path-escape surface the filesystem sidecar is version-pinned against
(CVE-2025-53109/53110); base64 spends the model's context, the audit line, and the card on a
payload nobody reads.

Inline authored text adds **no transport at all**: tool arguments already arrive at the
sidecar as JSON over MCP, so the attachment rides the channel the subject and body already
ride, with no new capability anywhere. No proto, port, orchestrator, gate, or taint change;
`send_email` is still the one gated name, and the card still renders generic key/value rows.

### 3. Refusals, and where they live

`SmtpSender._compose` is where a send is refused, so the new rules join the CR/LF ones rather
than starting a second refusal site. The split the existing comment draws is the one that
decides each rule: **`filename` is a header value, `content` is a payload.**

- **The filename gets header treatment:** non-empty (a nameless part cannot be saved),
  CR/LF refused in code like every other header value (a laundered `\r\nBcc:` in a
  `Content-Disposition` is the same attack), and bounded to `MAX_FILENAME_CHARS` (128), since
  a header line is not a place to put a kilobyte.
- **The subtype must be a MIME token** (`^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,62}$`, no `/`), which is
  what keeps `text/` a prefix the caller cannot escape: `subtype="plain\r\nX: y"` or
  `subtype="html; boundary=..."` would otherwise be a header-injection channel of its own.
- **`MAX_ATTACHMENTS` (8) refuses rather than truncates**, the spawn batch cap's argument
  (ADR-0010): a silently dropped attachment is a send the user approved and did not get.
- **`MAX_ATTACHMENT_CHARS` (32768, summed over all attachments)** bounds what one call can
  put on the card, in the audit line, and on the wire. The number comes from the *authoring*
  side rather than from SMTP (Proton's limit is three orders of magnitude higher): 32K of
  text is already half the 16K-token context and two thirds of the default
  `CORTEX_HISTORY_CHAR_BUDGET`, so past it an attachment is competing with the conversation
  that produced it. It is counted in **characters**, matching the history budget and the
  `content` the card shows, rather than in encoded bytes, which would make the same visible
  draft fit or not fit depending on its accents.

A refusal is a `ValueError`, which the sidecar returns as the tool's error string, so the
model sees why and the message never reaches the wire.

### 4. Two things the card got wrong, both found by driving it

The feature is brain-side, but "the card shows the content, verbatim" is half the argument
above, so the card was driven in a browser with an attachment on it. Both defects it exposed
are pre-existing gaps that only an attachment makes reachable, and neither is chrome:

- **The draft had no height bound.** An attachment is the first argument value *meant* to be
  long, and a long draft grew the card until Approve and Deny were pushed out of the history's
  view. `.confirm-draft` now caps at `42vh` and scrolls. Every byte stays on the card, which
  is the point: a summary such as `notes.md (1.2 KB)` would break the rule this addendum
  turns on.
- **A non-string value was rendered with `JSON.stringify`,** which was invisible while every
  argument was a string and is exactly wrong for the first one that is not: the payload
  arrived as `{"content":"# Week 30\n- one"}`, so the user consents to a file through its
  escapes. `formatDraftValue` (pure, beside the card) now renders structure as indented
  `key: value` lines and leaves every string untouched, giving a multi-line value its own
  line. It knows about JSON shapes and nothing about `send_email`: the card stays generic
  over whatever gated tool the brain asks about.

The demo bridge's scripted draft carries an attachment for the same reason, so the long-draft
case stays drivable by hand on the host Windows shell too.

### 5. Binary attachments stay deferred, with a named blocker

Not "attachments" any more, but specifically **bytes the assistant did not author**. What
would have to be true first: a way for the card to be honest about a payload the user cannot
read (a digest plus size, with the sidecar re-reading at send and refusing on mismatch, so
approval binds to bytes rather than to a path), on top of the capability grant the path form
needs. Recorded in the ROADMAP.

### 6. Validation

- **CI (100%):** composition (a plain draft plus one attachment nests as `multipart/mixed`;
  a `body`+`html`+attachment draft keeps the `multipart/alternative` intact inside it; the
  subtype and filename reach the part), the five refusals each proven to keep the message off
  the wire, and the MCP handler forwarding a nested `attachments` argument onto the draft.
  Plus the regression that matters: a draft with no attachments is byte-for-byte the message
  the richer-shapes addendum shipped.
- **Agent, over Docker:** the nested array-of-objects schema is the first of its shape in the
  repo, so it is validated where a fake cannot: the containerized sidecar advertises it through
  the real `McpToolRegistry` (pydantic lifts `EmailAttachment`'s **docstring** into the `$defs`
  description, so "what it wrote, not a file on disk" reaches the model without a `Field`), a
  refusal comes back as a clean `is_error` carrying its reason, and a real model emits the
  nested argument against the advertised schema.
- **Agent, live Bridge:** the `integration`-marked round-trip sends a real attachment and
  parses it back off IMAP by filename and content, so the whole path is proven, not just the
  composition.
- **User, Windows host:** unchanged. No seam, no IPC, no new event.

## Addendum (2026-07-16): subagent tool-step surfacing landed via the ADR-0010 progress sink

The `ToolActivity` addendum above listed "subagent tool-step surfacing (the ADR-0010 progress
deferral)" as remaining behind the same seams. It lands, in [ADR-0010](ADR-0010-subagents.md), as
one side channel shared with that ADR's own progress-reporting deferral, and it reuses this chip
wholesale rather than growing anything here.

The `ToolStep`-to-`ToolActivity` mapping this addendum built for the cortex is exactly what a
subagent needs; the only gap was that the subagent's `stream_tool_loop` runs inside
`SubagentRunner`, whose steps this ADR's engine mapping never saw (the runner dropped them). The
progress addendum adds a pure-core `ProgressSink` on the dispatch `TurnStamp`, so `SubagentRunner`
now maps each `ToolStep` onto the spawning stream's sink as the same registry-authored
`ToolActivity`. The chip's fields stay registry-authored (never the model's call or arguments, the
laundering-surface guarantee this addendum turns on), so the overlay renders a subagent's step with
**no wire or reducer change** and no new guardrail obligation. The `phase` field stays deferred (the
chip still needs no completion states). Full record and validation live at the
[ADR-0010 progress addendum](ADR-0010-subagents.md); the backlog closes in
[email-confirmer](../refinements/index.md#email-confirmer).

## Addendum (2026-07-16): confirm-with-provenance for tainted turns is declined

The structured provenance this deferral waited on landed (`TurnStamp.sources`, ADR-0027
addendum), so the blocker the entry named is gone and the decision it always was can be made.
The decision is to **keep the fail-closed tainted block**. Reversing it is rejected on the
merits, and separately the provenance that would make a card useful does not exist yet. Both
findings were read against the code, and the block was observed to fail closed.

### 1. What a tainted turn reaching a gated call does today, in code

`ToolDispatcher.dispatch` gates on the dispatcher's own `stamp.tainted`
(`cortex_core/dispatch.py`): a gated call on a tainted turn returns `DENIED_MSG` and the
confirmer is **never consulted** (the `if stamp.tainted:` branch returns before `_confirmed`
runs). Two tests pin it, and both were run green this session:
`test_gated_tool_on_a_tainted_turn_is_blocked_without_a_confirmer` and
`test_gated_tool_on_a_tainted_turn_is_blocked_even_when_a_confirmer_would_approve`, the second
asserting `confirmer.requests == ()` with an approving confirmer wired. So the posture is a
hard block, not a confirm-without-provenance, and the entry's "reverses a fail-closed posture"
framing is exactly right. There is no card on this path to add a source line to; building the
entry means letting a tainted gated call reach the confirm card at all.

### 2. Why reversing it is rejected, independent of provenance

The tainted block is a **deterministic guarantee**, not a gap left by a missing source string:
after a turn reads hostile bytes, the outbound surface is closed for the rest of the turn, full
stop (decision 2, `DENIED_MSG` at `cortex_core/untrusted.py`). On a tainted turn the model's
arguments may themselves be injection-authored, so a card showing that draft to a user
conditioned to approve is not a boundary. A send demanded by injected content must never be
merely a confirm-away, and a source line on the card does not change what the card asks the user
to do. The posture is also **not over-broad**: the legitimate "read this email, then reply" flow
still completes, in a fresh turn, because taint is turn-local and `DENIED_MSG` tells the model to
have the user re-ask. Keeping the block costs one extra user turn, the cost decision 2 already
weighed and accepted; reversing it reopens the exact path an injection attack aims for, to save
that one turn. That trade is refused, consistent with the same-day decline of summarizing a
tainted exchange (feeding attacker text through a model makes the model the target; a provenance
card makes the **user** the target, worse, since the user is the authority the gate exists to
protect).

### 3. And the useful provenance is not captured anyway

Even had the decision gone the other way, the change could not be built honestly. The only two
`Provenance` producers in the brain are both **attested** (brain-authored): the tool loop notes
the advertised tool name (`SourceKind.TOOL`, `cortex_core/tool_loop.py`) and recall notes a
fenced memory's id (`SourceKind.MEMORY`, `cortex_core/engine.py`). A card built from those would
say "this turn used the read tool" or "recalled memory abc123", which names the user's own action,
not the attacker. The kinds that would identify the attacker, `SENDER` and `URI` (the content's
own claim), ship shaped and tested with **no producer**, because `ToolResult` carries no source
field (the sidecar-declared-sender deferral, ADR-0027 addendum). So the provenance actually
present at the confirm point is precisely the unhelpful kind, and the helpful kind is a second,
independent blocker.

### 4. Outcome

**Declined**, docs-only. The entry stays in [email-confirmer](../refinements/index.md#email-confirmer)
verbatim as the historical record, annotated with this outcome, and moves to the backlog's
dead-until-a-consumer list. It reopens only if the outbound-on-tainted decision is itself revisited
with new evidence that a confirmation card converts reflexive approval into scrutiny, **and** a real
`SENDER`/`URI` producer exists to name the source, not on provenance plumbing alone. Nothing in the
seam, the proto, the confirmer, or the gate changed.

## Addendum (2026-07-16): real-file attachments (bytes the assistant did not author) are declined

The attachments addendum above landed authored text and named the one remaining shape as "bytes
the assistant did not author (a real file)", blocked on two things at once: a file-read capability
on a sidecar built with none, and a card that could bind approval to a payload the user cannot
read. Both were read against the code before deciding. The decision is to **keep the capability
ungranted**: the email sidecar stays with no filesystem access, and `send_email` keeps attaching
only what the assistant wrote. This is a security decision, not deferred plumbing, and the
reasoning is recorded so a future consumer reopens it with the constraints already known.

### 1. What exists today, in code

Send exists, and it attaches authored text only. `send_email` takes an `attachments` array of
`EmailAttachment(filename, content, subtype)` (`cortex_email/server.py`, `cortex_email/values.py`),
where `content` is a `str` the model wrote; `SmtpSender._compose` adds each as one `text/<subtype>`
part via `message.add_attachment(attachment.content, ...)` (`cortex_email/smtp.py`). The tool's own
docstring states the boundary to the model: "Attachments carry text only, so a file on disk cannot
be attached." The bytes ride the JSON tool argument over MCP, the same channel the subject and body
ride, so the current shape has no transport and no capability behind it.

The sidecar has no filesystem access to grant from. The `mcp-email` service declares no `volumes:`
at all in `docker/docker-compose.email.yml`, unlike `docker/docker-compose.tools.yml`'s
`mcp-filesystem`, which is a separate container holding a single read-only bind mount scoped to
`/projects` and version-pinned against the EscapeRoute path-escape CVEs. So "a real file" means
granting the network-egress sidecar a brand new power: reading local disk.

### 2. The exfiltration threat that grant creates

The email sidecar is the outbound path: it authenticates to the Bridge and sends mail off the
machine over SMTP. Giving that one process the power to read local files fuses read-local and
write-remote in the single component whose whole reason to exist is to leave the machine. A send
driven by injected content could then attach and exfiltrate an arbitrary local file. This is the
exfil-via-`send_email` case the untrusted-content posture is built against (ADR-0013 harness,
decision 2's tainted block), and it is why the architecture invariant keeps email read-only and
lets "only tools reach external services". A personal, local-first assistant has no present need
that pays for opening this surface.

### 3. The taint boundary already closes the useful path, which is the deep finding

Reading a file's bytes into the turn cannot coexist with sending in that turn, by construction. A
tool result defaults to `Trust.UNTRUSTED` (`cortex_core/tools.py`), the MCP registry builds read
results with that default (`cortex_tools/registry.py`), the tool loop's `TaintLedger.mark` flips
the turn `tainted` on any untrusted result (`cortex_core/untrusted.py`), and a gated call on a
tainted turn is blocked outright with `DENIED_MSG`, the confirmer never consulted
(`cortex_core/dispatch.py`). So "read this file, then attach and send it" is already denied: the
read taints the turn and the send is closed for the rest of it.

That is what makes a real-file attachment genuinely hard rather than merely capability-gated. To be
*useful* it must get the bytes to the sidecar **without** them passing through the model's context,
so the turn stays untainted and the send is allowed. But a channel that moves bytes the model never
reads is exactly the arbitrary-file exfiltration channel: the file is chosen by a path or handle
the model emits, and on a turn poisoned earlier the model's arguments may be injection-authored.
The digest-bound card the entry proposed binds approval to the *bytes* (it catches a swap between
approval and send, a TOCTOU on content), but it never binds the file *choice*, and the choice is
the thing an injection controls. A card reading "attach id_rsa (sha256 abc..., 3.2 KB)" is honest
about the bytes and still asks a user conditioned to approve to approve an exfiltration. That is the
same failure that declined confirm-with-provenance for tainted turns the same day: a card can make
the **user** the injection target, which is worse than the model, because the user is the authority
the gate exists to protect.

### 4. The safe design, if a real consumer ever appears

Recorded so the work is not lost and reopens with its constraints known. A defensible build is
**not** "grant the email sidecar a path and let it read arbitrary disk". It is all of:

- **A narrowly-scoped source, never an arbitrary path.** Either a dedicated outbox directory the
  sidecar may read (a single read-only mount, the filesystem sidecar's containment pattern, never
  the home directory), or a caller-provided opaque handle to bytes already admitted by a trusted
  path, so the string the model emits can name only things inside an allowlist and can never select
  `~/.ssh/id_rsa`.
- **The file choice gated by taint, not by the model alone.** Because a path is chosen text, the
  same tainted-turn block that guards the send must guard the *selection*: an attachment whose
  source was named on a turn that read untrusted content is refused, so injected content cannot pick
  the file even when the bytes bypass the model's context.
- **A digest-bound card.** The card shows the filename, size, and a content digest; the sidecar
  re-reads at send and refuses on a digest mismatch, so approval binds to bytes and a swap between
  the click and the send fails closed. This closes TOCTOU but, per finding 3, is not sufficient on
  its own: it must sit on top of the scoped source and the taint gate, which together bound the
  *choice*.

Its cost is a new capability surface (a mount plus file-read on the egress sidecar, or a brain-side
bytes-admission port and handle plumbing), a proto and card change to carry the digest and size,
taint rules extended to the attachment source, and tests proving both a digest mismatch and an
injection-chosen source fail closed. That is a slice, not a follow-on, and it is the right shape
only when something needs it.

### 5. Trigger and outcome

**Declined**, docs-only, the capability ungranted. It reopens on a real consumer that must attach
bytes the assistant did not author (a saved PDF, an image, a downloaded report), and even then it
is built to the finding 4 shape, not by handing the egress sidecar a path. The entry stays verbatim
in [email-confirmer](../refinements/index.md#email-confirmer) as the historical record, annotated with
this outcome, and moves to the backlog's dead-until-a-consumer list. Nothing in the seam, the proto,
the sidecar, or the gate changed.

## Addendum (2026-07-19): where the Windows-native card check is tracked

The "Still pending (genuinely OS-native, host-only)" paragraph above names the confirm card
through the real Tauri IPC hop. That check now has a written home: item 3 of
[docs/host/index.md#windows-desktop](../host/index.md#windows-desktop), indexed at
[docs/host/](../host/index.md), with the gated-tool prerequisite spelled out (either
`CORTEX_EMAIL_SEND_ENABLED=true` with the Bridge reachable, or any name in `CORTEX_TOOLS_GATED`)
and with the approve, deny, and ignore paths as three separate expectations. Worth knowing when
searching for the trail: its backlog line lived under
[refinements/index.md#untrusted-content](../refinements/index.md#untrusted-content) rather than
`email-confirmer.md`. The result comes back here as a dated addendum.

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-08-11): the attachment schema describes its fields, not just the object

The attachments addendum's validation section above closed on a happy observation: pydantic
lifts `EmailAttachment`'s **docstring** into the `$defs` description, "so 'what it wrote, not a
file on disk' reaches the model without a `Field`". That sentence was true and it is why this
deferral was left open, and reading the generated schema again shows what it bought and what it
did not. It bought the object. Every one of the three fields arrived carrying `title` and
`type` and nothing else, so a model filling the shape was told there is a string called
`content` and left to guess what belongs in it.

### 1. The guesses, and what each one costs

The bounds this ADR chose are enforced in `SmtpSender._compose`, which runs in the sidecar,
which is **after** the brain gated the call and after the user approved the card. So a wrong
guess is not a validation error the model retries cheaply: it is a send the user consented to
and did not get, and the user is asked again for something they already said yes to. That
raises the field descriptions from documentation to part of the refusal design.

- **`content`** is the guess that matters most, because getting it wrong still succeeds. A
  model reading `filename: str, content: str` has every reason to read the pair as a name and
  a location, and `{"filename": "notes.md", "content": "/home/user/notes.md"}` composes,
  sends, and arrives: the recipient gets a file whose whole text is a path. Nothing refuses it,
  because a path is a perfectly good string. The description now says the field is the file
  itself, never a path and never a URL, and that nothing is read from disk, which also carries
  this ADR's real-file decline to the one place a model is deciding.
- **`subtype`** is the guess a whole MIME type invites: `text/markdown` is what the type is
  called everywhere else, and it is exactly what `_SUBTYPE_TOKEN` refuses, since the regex bans
  the solidus precisely so `text/` stays a prefix the caller cannot escape. The description
  locates the token as the part after `text/` and names the wrong form outright.
- **`filename`** is the guess with a number in it. It rides a `Content-Disposition` header, it
  is refused rather than trimmed, and 128 characters is not a limit anyone would assume from
  `str`. The description also asks for an extension matching the subtype, which no check
  enforces and which is what makes the file open correctly for the human at the other end.
- **The array** had no description at all, and its two bounds (at most `MAX_ATTACHMENTS`, and
  `MAX_ATTACHMENT_CHARS` summed over their content) belong to neither the object nor any field
  of it. They ride `attachments` itself through the tool signature, the `capture_screen` target
  precedent of a help constant spent where the schema is declared.

### 2. Where the prose lives, which is what the deferral was really about

The entry's own objection was that per-field text "would put pydantic in the pure values
module". It would, and it does, and the objection turns out to point the wrong way. That module
was already a prompt surface: pydantic has been lifting `EmailAttachment`'s docstring into the
advertised schema since attachments landed, so the only question was whether the model-facing
prose would be complete or half of it. The alternative, a schema-facing mirror of the three
fields declared in `server.py`, would spell the tool contract in two places to keep one import
out of one file, which is a worse trade than the one it avoids.

So `values.py` gains the import and, with it, the three bounds themselves, moved off
`smtp.py`. That move is the point rather than tidying: the description a model reads and the
check that refuses the send are now the same integer read twice, so the prose cannot drift from
the rule. `_SUBTYPE_TOKEN` stays in `smtp.py`, being a rule rather than a number.

### 3. Validation

- **CI (100%):** the generated schema is asserted rather than the source, since the schema is
  the artifact and it is generated: every attachment field carries a description holding the
  fact that settles its guess, and the array names both bounds from the constants themselves,
  so a description that restated a bound as a literal fails even while reading correctly.
- **Five mutations, each measured.** Dropping any one field description reddens; restating the
  filename bound as its own number reddens; hollowing `content` down to what its type already
  says reddens; deleting the array description reddens. The sixth attempt is the finding worth
  recording: the subtype check first matched the bare string `text/`, which the description
  contains twice, once in the instruction and once in the counter-example warning against
  `text/markdown`. Deleting the instruction left the check green. It now matches the phrase
  that locates the token, and reddens.
- **Not measured:** whether a model composes a correct call more often with the descriptions
  than without. That is this entry's actual claim and it stays an argument, resting on the
  four guesses above being real rather than on a rate. The A/B belongs on the CPU tier and is
  the sort of thing the turn-cost harness does; it is not a blocker for text that can only
  add facts the schema was missing.

### 4. What the sibling sweep found

Every other tool in this sidecar was read for the same defect. The write path is clear: the
`send_email` docstring already describes `to`, `cc`, `bcc`, `body` and `html`, and it keeps
that job, the tool description saying what the capability is while the fields say what a value
must be. `list_folders` takes nothing and `read_email`'s `folder`/`uid` are named by the tool
that produces them.

`search_emails` is the exception and it is **deferred rather than closed**, recorded in
[refinements/index.md#email-confirmer](../refinements/index.md#email-confirmer). Its `query` is passed
through to imap-tools unaltered, so the dialect is raw IMAP `SEARCH` criteria, and "an IMAP
query" is all the tool says. A model that writes `from:someone@example.com` is writing the
search syntax of every mail client a person has used, and it is not this one. The reason it is
not closed here is that the honest description is a list of criteria that work, and this repo
knows exactly two of them work against a real ProtonMail Bridge, `ALL` and `SUBJECT "..."`,
because the live round-trip uses those two and nothing else. Writing a longer list from the RFC
would be advertising a capability nobody has run, on a server whose `SEARCH` support is
partial by reputation. It wants a live pass over the criteria first, which is a different
sitting from this one.

## Addendum (2026-08-18): the search dialect, named from a live pass

The addendum above deferred one field rather than closing it: `search_emails`'s `query`, whose
honest description is a list of criteria that **work**, against a server whose `SEARCH` support is
partial by reputation. That pass has now run, so the field is described from measurement.

**What was run.** Every criterion below went through this repo's own `ImapMailbox`, so the proven
form is the one imap-tools actually sends (`UID SEARCH CHARSET US-ASCII ...`), against Proton Mail
Bridge 03.25.00 over a folder of 1205 messages, read-only throughout (`EXAMINE`, and hit counts
rather than content). Accepted, each with a discriminating count: `ALL` (1205); the quoted-argument
criteria `SUBJECT`, `FROM`, `TO`, `CC`, `BCC`, `BODY`, `TEXT` and `HEADER "Name" "value"`; the date
criteria `SINCE` (417), `BEFORE` (788, a clean partition of the 1205 against `SINCE`), `ON`, and the
`SENTSINCE`/`SENTBEFORE`/`SENTON` trio; the standalone flags `SEEN`/`UNSEEN`,
`ANSWERED`/`UNANSWERED`, `FLAGGED`/`UNFLAGGED`, `DRAFT`/`UNDRAFT`, `DELETED`/`UNDELETED`; `LARGER`
and `SMALLER` in bytes. Composition holds: juxtaposition ANDs (`FROM "..." SINCE 01-Jan-2026` at 8,
below either alone), `OR` takes exactly the two criteria after it, `NOT` negates the one after it,
and parentheses group.

**What was refused**, which is the half that makes the description worth the tokens. The client
syntax a model reaches for comes back as a `BAD` it cannot repair: `from:someone@example.com` and
`subject:cortex` both fail with `expected space`. An ISO date fails with `expected - after year`,
so `dd-Mon-yyyy` is a requirement rather than a convention. An unquoted multi-word argument fails
with `unknown search key`. And `KEYWORD` was refused for the flag it was probed with, which is why
it is not named: a criterion nobody can demonstrate stays out, exactly as the deferral asked.

Two sibling guesses in the same tools are described in the same edit, since each cost one constant.
`folder` says the name comes verbatim from `list_folders` and that an invented one is an error
rather than an empty result (measured: `no such mailbox`), and it is spent by `read_email` too, so
the two cannot drift. `limit` says the matches it keeps are the first in the folder's own uid
order, which is not the newest: measured against a virtual All Mail folder whose uid 1 to 4 are
August 2026 messages, a `SINCE` search truncated to those same four, so a model raising the limit
to look for recent mail is doing the one thing that cannot work.

**The description is guarded rather than trusted.** An integration-marked test runs one query per
criterion family the description names, and refuses to pass if the description names a criterion
the queries never ran, so adding a word to the prose without proving it fails the live pass.
It also asserts the client syntax still raises, which is the premise the whole description exists
to remove. It is excluded from the coverage gate and never runs in CI, per the live-adapter rule.
Proved able to fail by adding `KEYWORD` to the list: the run went red on the Bridge's refusal.

One thing the pass surfaced and did not fix: what escapes on a query the server still refuses is a
raw `imaplib.IMAP4.error`, so the model reads `UID command error: BAD [Error offset=38]` rather
than anything naming the dialect it got wrong. That is filed as
[a refinement](../refinements/tasks/312-search-refusal-is-untyped.md).

## Addendum (2026-08-19): the refused search is the port's own error, not imaplib's

The addendum above closed with the one thing its live pass surfaced and did not fix: a query the
Bridge refuses escaped `ImapMailbox` as a raw `imaplib.IMAP4.error`, so the model read
`UID command error: BAD [b'[Error offset=38]: expected space']`, an offset into a wire command it
never composed, from a library nothing had told it about. This closes it, and the shape it lands
in is the one every other refusal in this sidecar already has.

**The port gained a failure channel, so the adapter's library no longer has one.** `cortex_email`
now declares its own two typed errors (`errors.py`), in the two-member shape `cortex_core.errors`
established for `MemoryStoreError`/`MemoryDataError` and `ModelHostError`/`ModelNotHostedError`,
and declared here rather than there because the sidecar deliberately cannot import the core.
`MailboxError` says the mailbox could not answer: the Bridge was unreachable, TLS or the login was
refused, the folder could not be examined, the connection went away. `SearchRefusedError` is the
one narrower fact, and the line between them is whether rewriting the query would change anything.
Every other failure heals when the machine is fixed and nothing about the query touches it; this
one heals only when the query is rewritten, which is something the model reading the result can
do. So it carries the `query` it refused, and its message names where the dialect is written down
rather than restating it, since the field description is already in the model's context on the
turn it reads the refusal.

**The classification looks rather than assumes.** imaplib raises a plain `IMAP4.error` for a `BAD`
tagged response and its `IMAP4.abort` subclass when the connection goes away mid-command, and
those are opposite facts about the same query: one says the text was wrong, the other says the
text may have been perfect and the server stopped listening. Reporting an abort as a refusal would
send a model round a rewrite loop that cannot end, so `_search_failure` tests for the subclass
first and only the remaining `IMAP4.error` becomes a refusal. Everything else the IMAP stack
raises, imap-tools' own `NO` exceptions included, crosses as `MailboxError` with the cause
chained, so no exception of the library reaches a caller through any of the three methods.

**What the model reads, checked end to end.** A tool that lets an exception out is restated by
FastMCP as `Error executing tool search_emails: <the exception>`, which is the truth for a mailbox
that could not answer and a falsehood for a search the server read and declined: the tool ran, and
what it has to say is a correction. So `search_emails` catches the refusal and answers with a
`CallToolResult` of its own, the shape `read_email` already used for its source declaration, with
`isError` set and the text untouched. Driven through the low-level server's real request handler
and then through the brain's `McpToolRegistry`, the refusal arrives in `ToolResult.content`
verbatim and `is_error` True: the registry restates nothing, which answers the question the
refinement entry raised about it. The contrast case was driven the same way and still reads
`Error executing tool search_emails: the mailbox could not run that search: connection refused`,
which is what a failed tool should say.

**Ports before adapters, so the fake refuses too.** The `Mailbox` port had no shared contract, only
a fake in the reader tests and a stand-in imap-tools box in the adapter tests. It has one now
(`mailbox_contract.py`), four checks driven over both implementations, with the one condition no
method can create supplied as a knob exactly as the `Embedder` contract supplies a broken backend:
the server refuses the next search. Two of the checks are about the refusal, and one of those is
that the message carries no fragment of the wire answer, which is the promise a future adapter
could quietly break. The stand-in box and the fake mailbox moved into shared test modules so the
adapter is driven over one stand-in rather than two that could drift.

**Validation.** `just check` green. Both new gates were proved able to fail: deleting the abort
branch reds the connection-lost test, and removing the wrap entirely reds two contract checks on
the `imap` arm with the wire text visible in the failure. Live against a real Bridge on this
machine, `from:someone@example.com` came back as `SearchRefusedError` carrying that query, with
`UID command error: BAD [b'[Error offset=38]: expected space']` on the chained cause where an
operator finds it and the model does not. The live criterion guard now asserts that type rather
than imaplib's, which is the only place the branch is taken on an answer a real server sent.

One sibling this opened rather than closed: `folder` is described just as carefully as `query` and
a name no mailbox has still comes back as imap-tools' own sentence inside a `MailboxError`, filed
as [a refinement](../refinements/tasks/318-a-folder-refusal-is-untyped.md). And the observation
this slice made in passing, that a search which read nothing still taints the turn and so closes
the outbound surface behind it, is
[filed too](../refinements/tasks/319-a-refusal-taints-the-turn.md).

## Addendum (2026-08-19): a folder no mailbox has is the port's own error too, classified live

The addendum above closed by naming its own sibling: `folder` is the other guess the two read
tools invite, described just as carefully, and a name no mailbox has still came back as imap-tools'
sentence inside a base `MailboxError`. The model read `the mailbox could not run that search:
Response status "OK" expected, but "NO" received. Data: [b'no such mailbox']`, a command status
reported to a caller that sent no command, and the folder it refused was not in the message at
all. This closes it in the shape the query already has.

**`FolderUnknownError`, the port's second correction.** It sits beside `SearchRefusedError` under
`MailboxError`, and the two are drawn on one line: the mailbox answered, and what it said is
something the caller can fix rather than something the machine has to. It carries the `folder` it
was given, and where the query's message points at a field description because a rewrite is what
fixes a query, this one names `list_folders`, because the correction here is a single call. That
asymmetry is the whole reason the folder was worth typing separately: it is the cheaper guess to
get wrong and the cheaper one to fix. `FOLDER_UNKNOWN` sits in `values.py` beside `FOLDER_HELP`,
which is the description both tools already spend, and it names neither searching nor reading,
because both tools take a folder and both now answer it in the same words.

**What a real Bridge says, measured.** A `NO` to `SELECT` is not by itself a missing folder, so the
question was what distinguishes one from a folder that exists and could not be opened, read off
the response rather than inferred from the fact that a select failed. Against the live Bridge on
this machine, every name no mailbox has is refused identically, whatever shape the wrong name
takes (a bare name, a child of a real folder, a child of a `\Noselect` parent, a child of a
`\Noinferiors` folder, an empty name, a quoted name, a non-ASCII name): the answer is `('NO', [b'no such mailbox'])` every time, with no RFC 5530
response code beside it. So the words are what is read. `_FOLDER_MISSING_ANSWERS` holds that
measured phrase plus `[NONEXISTENT]`, the standard's own machine-readable spelling of the same
fact, which a server that sends it means exactly; anything else a `NO` carries is not proof.

**The second situation could not be constructed, so the classification fails safe.** The obvious
candidate was a `\Noselect` folder, and this Bridge lists two of them (`Folders`, `Labels`) as the
parents of its hierarchy. Both select cleanly, which is itself worth recording: on this server a
listed name always opens, and the live test now asserts that over the whole list, so nothing
`list_folders` returns can come back as the refusal `FOLDER_HELP` warns about. With no way to
produce the contrast case, the rule is presence rather than absence: a select failure is reported
as a missing folder only when the answer says the mailbox does not exist, and every other refusal
stays a plain `MailboxError` carrying the library's account of why. That is the safe direction.
Telling a model to consult `list_folders` about a folder it read off `list_folders` is a loop,
whereas "the mailbox could not answer" is true whichever of the two it was. The branch is reachable
only from a scripted stub (RFC 5530's `[INUSE]`), which the contract and the adapter tests both
drive, and it is the one line here a live pass cannot reach.

**Both tools, checked end to end.** `read_email` takes a folder too and fails on it before it has
looked at a uid, so answering a guessed folder with `message <uid> not found in <folder>` would
send a model hunting through a folder that does not exist for a message that may well be there.
Both tools now catch the correction and answer with a `CallToolResult` carrying the port's wording
and `isError`, driven through `FastMCP.call_tool` and asserted verbatim and identically for the
two. Onward from there nothing restates it: `McpToolRegistry` sets `is_error` from `result.isError`
and renders the content as it stands, which its own contract already holds.

**Ports before adapters, so the fake refuses too.** The `Mailbox` contract gained three checks and
the fake gained a folder list it honours, which is the more faithful fake: a folder no mailbox has
needs no knob, only a name `list_folders` did not return, which is exactly the mistake the tool
descriptions warn about. The one genuinely unreachable condition, a folder that could not be
opened for another reason, is a knob on both fixtures, the established honest widening. The
checks are that both folder-taking calls raise the port's own type carrying the name, that the
message names the folder and `list_folders` and carries no fragment of the library's answer, and
that a folder which failed to open for any other reason is not reported missing.

**Validation.** `just check` green. The new gates were proved able to fail, both mutations run in
the session that landed this: dropping the measured phrase from `_FOLDER_MISSING_ANSWERS` reds the
two unknown-folder contract checks on the `imap` arm, with the library's sentence visible in the
failure, and classifying every select failure as missing reds the fail-safe contract check on that
same arm plus the adapter test beside it. The fake arm cannot red on either, which is what the
knob's honest widening means. Live against the real Bridge, the four wrong-name shapes and both
folder-taking calls were driven for real, and every one of the nineteen folders the account lists
opened.

One narrower thing this opens rather than closes: the contrast case has never been seen on any
server this repo can reach, so the phrase-matching rule rests on one server's wording, filed as
[a refinement](../refinements/tasks/327-the-other-no-to-select-is-unseen.md).

## Addendum (2026-08-21): both refusals, measured against a second server

The addendum above closed by naming what it could not do: a `NO` to `SELECT` covers two facts and
only one of them had ever been produced, so the rule that types a missing folder was built on one
server's English and the assumption behind it, that a real "there but shut" refusal says none of
the things a missing one says, had never been tested against a server saying it. This settles both
halves by running a second IMAP server, which is what the refinement asked for.

**The second server.** `docker/docker-compose.imap-probe.yml` starts `dovecot/dovecot:2.3.21`
(build `47349e2482`) with its ACL plugin on, no mail, no password checked and a loopback publish.
`docker/dovecot/probe-mailboxes.sh` builds the tree and says what each part of it is for: the LIST
returns **four names**, three of them mailboxes (`INBOX` and `Parent/Child` open, `Guarded` does
not) and one of them a `\Noselect` node that is no mailbox at all (`Parent`). `Guarded` is listed
and its ACL leaves the account lookup rights only, so it exists, is advertised, and will not open:
the case that could not be constructed. It is a fixture rather than a service, taken up and down
around a measurement (`just up-imap-probe`, `just email-folder-probe`, `just down-imap-probe`), and
nothing in the brain stack knows it exists. The measuring recipe asks the published port first and
falls back to the container's own address, because a Docker Desktop engine publishes onto the
Windows host and the WSL distro this repo is developed in reaches the bridge instead; on the first
run here the publish did not answer, and a recipe that knew only the publish waited rather than
saying so.

**What it said, measured through `ImapMailbox`, verbatim.**

| SELECT of | the answer |
| --- | --- |
| `Nonexistent`, and every other shape of wrong name | `NO Mailbox doesn't exist: Nonexistent (0.001 + 0.000 secs).` |
| `Guarded`, listed and ACL-shut | `NO [NOPERM] Permission denied (0.001 + 0.000 secs).` |
| `Parent`, a `\Noselect` node with a child | `NO Mailbox doesn't exist: Parent (0.001 + 0.000 secs).` |
| `""`, the empty name | `NO [CANNOT] Invalid mailbox name: Name is empty (0.001 + 0.000 secs).` |

**The assumption holds, and is now a measurement.** The refusal for a mailbox that is there and
shut carries neither measured phrase nor `[NONEXISTENT]`, so the fail-safe branch is taken on a
sentence a real server really sent rather than on one this repo wrote about a server it had never
met. The scripted answer the unit and contract suites drive that branch with is now that sentence
(`UNOPENABLE_FOLDER_ANSWER`), replacing an invented `[INUSE]`.

**The classification stands, and gains a phrase.** The two servers agree on the fact and share no
word of how they say it: where the Bridge says `no such mailbox`, this one names the folder and
says it doesn't exist. Neither sends a response code with it, so the alternative the refinement
offered, moving to a machine-readable signal both servers share, is not available: there is no such
signal, and the words really are all there is. `_FOLDER_MISSING_ANSWERS` therefore holds both
measured phrases beside `[NONEXISTENT]`, and a model that invents a folder name is corrected on
either server instead of only on the one the rule was first written from.

**Two things this measured that nobody had asked about.** A `\Noselect` node is refused here
exactly as a name no mailbox has is, and this server lists it, so a model told to spell folders as
`list_folders` returned them can be sent back to a list the refused name is on. That loop is the
one the fail-safe direction exists to avoid, and it arrives from the other side: not a misread
refusal but a `list_folders` that offers a name which is not a mailbox. The Bridge's own
`\Noselect` parents open, which is why it never showed up before. And an empty name is refused as
neither missing nor shut but as no name at all, `[CANNOT]`, a third fact the same `NO` carries.
Both are recorded in the live probe suite and filed as refinements rather than fixed here, since
each is a change to a different call than the one this addendum is about: the listed node that is
not a mailbox is
[one](../refinements/tasks/364-list-folders-offers-a-name-no-mailbox-has.md) and the name the
server will not read is [the other](../refinements/tasks/365-a-refused-name-is-neither-missing-nor-shut.md).
The probe's own mailbox names are spelled in its script and in its test with nothing tying them,
which is [a third](../refinements/tasks/366-the-probe-fixture-and-its-test-are-untied.md).

**Validation.** `just check` green. The live probe suite is five integration-marked tests
against the running Dovecot, driven through the whole `just` path, and the fail-safe half of it
runs the port contract's own check over the real refusal rather than restating it. Three mutations
were run in the session that landed this and each was reverted and re-read off disk: dropping the
new measured phrase reds one test of the email package's unit suite and two of the probe's live
suite; classifying every select failure as missing reds two of that unit suite (one of them the
contract check on the `imap` arm) and one live test, at the contract's own assertion; and granting
the guarded mailbox full rights in the fixture, which is the measurement's own premise rather than
the code's, reds exactly the live test that says a listed mailbox refused to open.

## Addendum (2026-08-21): `list_folders` offers mailboxes, not every name a server lists

The addendum above measured a thing it did not fix: this server's LIST answers with `Parent`, a
node that exists only because `Parent/Child` does, and then refuses a SELECT of it with `Mailbox
doesn't exist: Parent`, word for word what it answers for a name no mailbox ever had. The refusal
carries nothing that tells the two apart, so the classification cannot be the place this is fixed;
a model handed the name is told the folder does not exist and told to read `list_folders`, which
is exactly where it got the name. That is the loop the fail-safe direction exists to prevent,
arriving from the list rather than from the refusal.

**The flags survive.** imap-tools does not throw the LIST attributes away: `folder.list()` returns
a `FolderInfo` per name with `name`, `delim` and `flags`, and the adapter was reading `.name`
alone. Measured against the running probe, verbatim:

    FolderInfo(name='Guarded', delim='/', flags=('\\HasNoChildren',))
    FolderInfo(name='Parent', delim='/', flags=('\\Noselect', '\\HasChildren'))
    FolderInfo(name='Parent/Child', delim='/', flags=('\\HasNoChildren',))
    FolderInfo(name='INBOX', delim='/', flags=('\\HasNoChildren',))

So the fact is available at the one place it is needed, and the decision is only what to do with
it.

**Decision: omit, rather than mark.** Two shapes were weighed. Carrying selectability across the
port would let a caller see the tree as the server sees it, and it is the wider change: the port
returns `Sequence[str]` today, so marking means a folder value crossing it, a new field for every
implementation to fill, and a rendering decision in the MCP tool. Omitting keeps the port's shape
and makes it say something stronger, which is what its only consumer actually needs. That consumer
is a model choosing a folder to read, `FOLDER_HELP` already promises it "one folder name spelled
exactly as `list_folders` returned it", and a name that cannot be opened is not one of those. The
usual argument for keeping the node, that its name is a useful prefix, does not survive contact
with the measurement: `Parent/Child` is listed in its own right and carries the prefix inside a
name that works, so nothing about the tree becomes unreachable. `ImapMailbox.list_folders` drops
any name whose flags include `\Noselect` or `\NonExistent`, read case-folded, the second being RFC
5258's spelling of the same fact for a server that speaks LIST-EXTENDED.

**What omitting costs, said plainly.** The Bridge lists two `\Noselect` parents, `Folders` and
`Labels`, and both of them open there, so this filter withholds from a model two names that would
have worked on that one server. Their children are listed under them exactly as `Parent/Child` is,
so nothing is unreachable; what is lost is the ability to search a container whose only content is
its children. That is worth less than the loop, and the alternative, selecting each listed name to
find out, is a round trip per folder on every listing. It is measured nowhere yet, so it is filed
as its own task rather than asserted to be harmless.

**This paragraph was overtaken the same day it was written.** The measurement it asked for was
taken against the live Bridge, it found exactly the two names named here, and the filter was
narrowed to drop a name only when the server refuses it as well as flags it. The two sentences
above about what `list_folders` drops are the shipped behaviour no longer; read the
flagged-and-refused addendum at the end of this document instead.

**It is a port change even so, and the contract carries it.** What changed is the port's promise
rather than its signature: every name `list_folders` answers with is a name the other two calls
may be given. `mailbox_contract.py` states it in two checks the fake, the adapter over its
stand-in, and the live probe all run. The first walks the offered list and fails if any name comes
back `FolderUnknownError`. The second says the honest other half: naming the node anyway is still
refused, because it still is not a mailbox, which is what keeps this a correction to the list
rather than to the classification. A hierarchy node is the third condition of a real server that
no method can arrange, so it joins the two refusal knobs as a field of `MailboxUnderTest` that
each fixture is built over rather than as something a check switches on.

**The fail-safe classification does not move.** A refusal that cannot be proved to name a missing
folder is still the base `MailboxError`; the guarded mailbox is still listed and still refused
without being called missing. Nothing in `_select` changed.

**Validation.** `just check` green, its output captured to a file. The live probe suite is five
integration-marked tests against the running Dovecot 2.3.21, run through `just up-imap-probe`,
`just email-folder-probe` and `just down-imap-probe`; the node test now asserts the fix, running
both new contract checks over the live server and then asserting the child is still offered. Two
mutations were run over the email package's unit suite (103 tests) and the probe's live suite (5),
each reverted and re-read off disk: making `list_folders` keep every listed name reds two of the
unit suite (the newer-spelling test and the contract check on the `imap` arm) and one live test,
and making the fake stop filtering reds one, the same contract check on the `fake` arm, which is
what proves the check is a statement about each implementation rather than about the adapter
alone.

## Addendum (2026-08-21): the flag is asked, not believed, because the two servers disagree

The addendum above landed a filter measured against one of the two servers this repo talks to, and
said so: the Bridge lists two `\Noselect` parents that open, and dropping them was recorded as a
cost worth paying and filed as its own task because it had been reasoned about rather than seen.
It has now been seen. Every name the account lists, with its LIST attributes verbatim and the
result of an EXAMINE of each, measured through `ImapMailbox` against a live ProtonMail Bridge:

| listed name | flags the server sent | SELECT |
| --- | --- | --- |
| `INBOX` | `\Noinferiors`, `\Unmarked` | opened |
| `Folders` | `\Noselect`, `\Unmarked` | opened |
| `Labels` | `\Noselect`, `\Unmarked` | opened |
| `All Mail` | `\All`, `\Marked`, `\Noinferiors` | opened |
| `Archive` | `\Archive`, `\Noinferiors`, `\Unmarked` | opened |
| `Drafts` | `\Drafts`, `\Noinferiors`, `\Unmarked` | opened |
| `Sent` | `\Noinferiors`, `\Sent`, `\Unmarked` | opened |
| `Spam` | `\Junk`, `\Marked`, `\Noinferiors` | opened |
| `Starred` | `\Flagged`, `\Noinferiors`, `\Unmarked` | opened |
| `Trash` | `\Marked`, `\Noinferiors`, `\Trash` | opened |
| the nine `Folders/...` children | `\Marked` or `\Unmarked` | opened |

Nineteen names, two of them flagged, and all nineteen open. So the filter as it shipped withheld
`Folders` and `Labels` from a model on the server the assistant actually talks to, and the earlier
claim that it did was right.

**Decision: keep the flag as the question and let the server answer it.** `list_folders` now drops
a name only when it is both flagged and refused: a name carrying `\Noselect` or `\NonExistent` is
opened once with EXAMINE on the connection the listing already holds, kept if it opens and dropped
if it does not. That is correct on both servers at once, which no reading of the flag alone can be:
the probe's Dovecot means "not a mailbox" by it and this Bridge means "a parent, and also a
mailbox", and no third signal tells the two apart. The promise the port makes is unchanged and now
holds in both directions: every name offered opens, and every name that opens is offered.

**Cost, which is the reason the last addendum did not do this.** The option weighed and rejected
there was a SELECT per listed name, nineteen extra round trips on this account for a listing that
otherwise costs one. Asking only the flagged names is a different profile entirely: two round trips
here, one on the probe, none at all on a server that flags nothing, and none ever on an ordinary
mailbox. The connection is already open and EXAMINE is read-only, so nothing is marked and no state
is left behind. That is small enough that the loop stays closed without paying for it in the common
case.

**What still gets dropped, and one edge worth naming.** A flagged name that is refused is dropped
whatever the refusal said, because the promise is about names that work rather than names that
exist. So a flagged mailbox that is real and merely shut right now, which no server this repo can
reach has ever produced, would be dropped where an unflagged shut mailbox (the probe's `Guarded`)
is still offered. The asymmetry is deliberate and untested against any server, so it is filed
rather than asserted:
[a flagged name that is refused for a reason that is not its name](../refinements/tasks/375-a-flagged-name-shut-is-dropped-as-if-missing.md).
The other thing this leaves open is that the kept half is proved only against the Bridge, on one
account, because the probe has no flagged name that opens and was not asked to grow one:
[the kept half has no fixture](../refinements/tasks/376-the-bridge-flag-reading-is-one-account.md).

**Where the check lives.** Not in `mailbox_contract.py`. The port cannot see this: the contract is
written over what `list_folders` returns, and the failure here is a name it did not return, which
is only visible beside the server's own LIST. The probe's Dovecot has no flagged name that opens
and cannot grow one, so a contract check would have to be optional at exactly the fixture that
matters. So the adapter's own tests carry the two halves over the stand-in, with the Bridge's
measured flags as a named constant, and `test_email_live.py` carries the live half: it walks the
server's LIST, selects every name itself, and asserts that the offered list is exactly the set that
opened. That assertion is the one that would have caught this the day the filter landed.

**Validation.** `just check` green, its output captured to a file. The live folder test was run
against the real Bridge before and after, green after and red on the mutation below. Three
mutations over the email package's unit suite (105 tests, integration deselected) and the live
folder test (1 of the 4 in `test_email_live.py`), each reverted from a saved copy and the file
re-read off disk: believing the flag again reds two of the unit suite and the live test; keeping a
flagged name that the server refused reds three of the unit suite, one of them the port contract's
own check on the `imap` arm; and asking every listed name rather than the flagged ones reds two,
at the assertion that says which names were opened.

## Addendum (2026-08-22): a refused name is the folder correction, read off a code

The two-server addendum measured a third thing the same `NO` carries and left it untyped: Dovecot
2.3.21 answers a `SELECT` of the empty name `[CANNOT] Invalid mailbox name: Name is empty`, which
is neither of the two facts the classification is drawn between. Nothing in it says the folder is
missing and nothing says a folder is there and shut, so it fell through to the base `MailboxError`
and a model that guessed a name which is not a name read back something indistinguishable from the
Bridge being down. This settles it.

**What the two servers say, measured through `ImapMailbox` and through a raw imaplib dialogue
against the running probe, verbatim.** The `[CANNOT]` reasons are one refusal with six wordings,
and the point of listing them is that every one of them is about the **name**:

| SELECT of | dovecot/dovecot:2.3.21 answered |
| --- | --- |
| `""` | `NO [CANNOT] Invalid mailbox name: Name is empty (0.001 + 0.000 secs).` |
| `Parent/` | `NO [CANNOT] Invalid mailbox name: Ends with hierarchy separator (0.001 + 0.000 secs).` |
| `/Parent` | `NO [CANNOT] Invalid mailbox name: Begins with hierarchy separator (0.001 + 0.000 secs).` |
| `Parent//Child` | `NO [CANNOT] Invalid mailbox name: Has adjacent hierarchy separators (0.001 + 0.000 secs).` |
| `INBOX/../etc` | `NO [CANNOT] Invalid mailbox name: Contains '..' part (0.001 + 0.000 secs).` |
| `~root` | `NO [CANNOT] Invalid mailbox name: Begins with '~' (0.001 + 0.000 secs).` |
| `Bad\Name` | `NO Mailbox doesn't exist: Bad\Name (0.001 + 0.000 secs).` |
| `"  "`, two spaces | `NO Mailbox doesn't exist:    (0.001 + 0.000 secs).` |

And the same account of the same question on a live ProtonMail Bridge, which has no code for any
of it:

| SELECT of | the Bridge answered |
| --- | --- |
| `""` | `NO no such mailbox` |
| `Nonexistent` | `NO no such mailbox` |

So the empty name was already the folder correction on one server and the base error on the other,
which is the drift the two-server addendum spent a fixture closing for the missing case.

**Decision: `FolderUnknownError`, and a response-code test rather than a seventh phrase.** A name
no mailbox could have is a name no mailbox has. `list_folders` never offered it and never will, so
the correction a caller is owed is the one that names the list, and it is the same one call on
either server. The classification now reads two RFC 5530 codes, `[NONEXISTENT]` and `[CANNOT]`,
beside the two measured phrases, and `_FOLDER_MISSING_PHRASES` and `_FOLDER_MISSING_CODES` are
separate constants because they are different kinds of evidence reaching one conclusion.

**The alternative, and why it lost.** `[CANNOT]` is the server refusing the request rather than
reporting the mailbox, which is closer to what `SearchRefusedError` says about a query, and typing
it as missing has the port assert something this server declined to assert. Three things decide
against it. The port's error is the correction a caller can act on rather than a restatement of
the server's claim, and here the correction is identical whichever fact it was. A third type would
also be a difference the port invented out of a difference in server wording, which is exactly what
the second measured phrase was added to erase: the Bridge would answer `search_emails(folder="")`
with one type and the probe with another, for one mistake. And `SearchRefusedError` is the wrong
sibling anyway, since it carries the query and points at the query dialect, while this fails in
`_select` before any query is read, on `fetch` as much as on `search`.

**Why the fail-safe direction does not object.** The rule that a folder which cannot be proved
missing is not reported missing exists to protect one case, a mailbox that is really there and
temporarily shut, because sending a model to `list_folders` over it starts a loop. `[CANNOT]` is
RFC 5530 for an operation that can never succeed, so it cannot be that case; the probe's own
"there but shut" mailbox answers `[NOPERM] Permission denied` and is untouched here. The other
thing `[CANNOT]` could plausibly mark, a name that exists and can never be opened, is the
hierarchy node, and the port already answers that with `FolderUnknownError`.

**It is a port decision, so the contract carries it.** `mailbox_contract.py` gains a check
saying that a name no mailbox could have is one no mailbox has: `search` and `fetch` of the empty
name both raise `FolderUnknownError` carrying it. The fake, the adapter over its stand-in, the live probe and
the live Bridge all pass it, and on the probe it passes only because of this change, which is where
the check has force. No new error type was added, so nothing else about the port's vocabulary moved.

**A mutation found the hole in the first version of this.** Reading the bare word `cannot` instead
of the bracketed `[CANNOT]` left every test green, and a server saying a real mailbox "cannot be
opened right now" would then have been reported missing. The test that closes it drives the
measured sentence with its brackets removed, which is a constructed near miss and is labelled as
one where it sits: what it pins is that the rule turns on a
response code, a form ordinary prose cannot imitate.

**Validation.** `just check` green, run to completion in the session that landed this. The probe
was taken up with `just up-imap-probe`, measured with `just email-folder-probe`, and taken down
with `just down-imap-probe`; the live Bridge half ran as `pytest -m integration -k folder` over
`test_email_live.py` with `CORTEX_EMAIL_IMAP_TLS_INSECURE=true`, green. The mutation table covers
this change and the next one together and sits at the end of the addendum below, both having
landed in one pass against one bring-up of the probe.

## Addendum (2026-08-22): the newer unselectable word, measured where it really lives

The hierarchy-node addendum put two spellings in `_NOT_A_MAILBOX` and measured one. `\Noselect` is
what the probe's Dovecot sends with its `Parent` node; `\NonExistent` was RFC 5258's spelling of
the same fact, read off the standard, sent by no server this repo had connected to, and pinned by a
unit test driving a stand-in that had been told to say it. The refinement that closed asked for the
cheap version of the missing evidence: a direct imaplib dialogue issuing an extended LIST and
recording what `Parent` comes back flagged as.

**That dialogue was run, and it refutes the premise it was built on.** `Parent` is `\Noselect`
under every extended LIST this server accepts, so there was never a `\NonExistent` waiting behind
a return option. Verbatim, against dovecot/dovecot:2.3.21:

    LIST "" "*"                        (\Noselect \HasChildren) "/" Parent
    LIST "" "*" RETURN (CHILDREN)       (\Noselect \HasChildren) "/" Parent
    LIST "" ("*") RETURN (SPECIAL-USE)  (\Noselect) "/" Parent
    LIST (SUBSCRIBED) "" "*"            (\Subscribed \Noselect) "/" Parent

The last two prove the client really did reach the extended syntax, since both drop the children
flags a plain LIST carries. The fourth line needed the node subscribed for the length of that
dialogue, which is why the fixture does not carry it and this is the one row here a rerun has to
arrange for itself. Dovecot converts its own `NONEXISTENT` to `\Noselect` for a client that
did not ask for LIST-EXTENDED and never the other way, and a node with a child on disk is
`\Noselect` in its model rather than nonexistent.

**Where the word does live, measured.** `\NonExistent` is this server's answer about a **subscribed
name no mailbox has**, and it takes a listing that asks for subscriptions to see one:

    LIST (SUBSCRIBED) "" "*"            (\Subscribed \NonExistent) "/" Ghost
    LIST (SUBSCRIBED RECURSIVEMATCH)    (\Subscribed \NonExistent) "/" Ghost
    LIST "" "*"                         Ghost is not returned at all
    LSUB "" "*"                         () "/" Ghost
    EXAMINE Ghost                       NO Mailbox doesn't exist: Ghost (0.001 + 0.000 secs).

So both halves of what the refinement asked are answered. It arrives **instead of** `\Noselect`
rather than beside it, on a different name and for a different reason. And the name behaves exactly
as the measured one does: it is refused in the very words that prove a folder missing, which is what
would send a model back to the list it read the name off.

**The fixture grew a fifth name to produce it.** `SUBSCRIBE Ghost` is itself refused here (`NO
Mailbox doesn't exist: Ghost`), so the subscription cannot be arranged over the wire and
`docker/dovecot/probe-mailboxes.sh` writes the subscription file directly, in the format read back
off one dovecot wrote itself: a `V<TAB>2` version line, an empty namespace prefix line, then one
name per line. The name is registered in `scripts/fixturecouplings.py` beside the other four, so a
rename in the script alone is caught by a gate rather than by the next measurement.

**Decision: keep the spelling, and say in the comment what kind of evidence it now is.** The
honest downgrade the refinement offered is not needed, because the word is measured; but the shape
around it is more interesting than the word. The call `ImapMailbox` makes is imap-tools'
`folder.list()`, which sends the plain `LIST "" "*"` and nothing else, and RFC 5258 lets a server
return `\NonExistent` only where a selection option was given. The Bridge cannot send it under any
phrasing: it advertises `AUTH=PLAIN ID IDLE IMAP4REV1 STARTTLS` and answers an extended LIST with
`BAD [Error offset=17]: expected CR`. So on both servers this repo talks to, reading the newer word
is a defence rather than a live path. It stays because reading a word neither server sends costs
one comparison of a tuple that is already being walked, while not reading it costs a name offered
to a model that cannot open it, on the first server met that lists one.

**Validation.** `just check` green, run to completion in the session that landed this, and both
suites run against the probe brought up and taken down around the pass. Mutations, each reverted
from a saved copy and the file re-read off disk, over the email package's unit suite (110 tests, integration deselected), the probe's live
suite (6 integration tests, `just email-folder-probe`) and `just check-crosscheck`:

| mutation | expected | observed |
| --- | --- | --- |
| drop `[cannot]` from the codes | the empty name falls back to the base error | 1 unit test red (the code-not-prose one) and 1 live probe test red, at the port contract's own check |
| read `cannot` instead of `[cannot]` | prose imitating a code is classified | 1 unit test red (the bracketed-code one); this mutation was green before that test existed, which is why it exists |
| drop `\nonexistent` from `_NOT_A_MAILBOX` | the newer spelling stops being read | 1 unit test red; no live test, since neither server sends the word to the listing the adapter makes |
| the fixture stops writing the subscription | the word has no source | 1 live probe test red and `crosscheck` red |
| rename the subscribed name in the script alone | the two spellings drift | `crosscheck` red on the new coupling, and the same live test red |

## Addendum (2026-08-23): the flag that lies, on a server this repo builds

The flagged-and-refused addendum shipped a rule with two halves and evidence for one of them. A
name a server flags `\Noselect` or `\NonExistent` is opened once before being judged: dropped if
the server refuses it, kept if it opens. The **drop** is pinned on a fixture, the probe's `Parent`
node, which this repo builds and can rebuild. The **keep** was pinned on nothing but a live
ProtonMail Bridge, on one account, whose `Folders` and `Labels` happen to be flagged and open.
That was filed as
[the kept half has no fixture](../refinements/tasks/376-the-bridge-flag-reading-is-one-account.md),
and the question it asked is whether Dovecot can be made to produce an openable flagged name at
all. It can, and it cannot, and which of the two depends on the listing.

**It cannot, in the plain `LIST "" "*"` the adapter itself makes.** There, on dovecot 2.3.21, the
flag and the refusal are computed from one fact, so a name flagged there is a name SELECT will
refuse. Two configurations were built and measured against that claim, and both confirmed it:

| what was tried | what the plain LIST answered | what a SELECT of it answered |
| --- | --- | --- |
| a second namespace `prefix = Shared/` beside a real mailbox `Shared` | `(\HasNoChildren) "/" Shared` **and** `(\Noselect \HasChildren) "/" Shared`, the name listed twice | `NO Mailbox doesn't exist: Shared`, the prefix node being what the name resolves to |
| a second namespace `prefix = INBOX/`, whose prefix node is INBOX itself | `(\HasChildren) "/" INBOX`, merged with the real one and not flagged at all | `OK`, but there was no flag to survive |

The first is the closer miss and the more instructive: the flagged line really is there in a plain
LIST, and the name really is a mailbox in another namespace, and the server still refuses it,
because a bare prefix resolves to the prefix node rather than to the mailbox it collides with. The
second shows the rule from the other side: Dovecot knows INBOX is selectable, so it declines to
flag the prefix node at all. Both are one behaviour seen twice.

**It can, in an `LSUB` of `%`, and there it is a requirement rather than a quirk.** RFC 3501
section 6.3.9 says a name that is unsubscribed and has subscribed children MUST come back from
LSUB flagged `\Noselect`, whatever that name really is. So the standard obliges a compliant server
to flag a mailbox it will happily open, which is the shape the Bridge shows in its ordinary LIST.
The fixture grew a pair to produce it, `Feigned` and its child `Feigned/Followed`, and both are
ordinary mailboxes. Verbatim, against dovecot/dovecot:2.3.21 (build `47349e2482`):

    LSUB "" "%"          () "/" Ghost
                         (\Noselect) "/" Feigned
    LIST "" "*"          (\HasChildren) "/" Feigned
                         (\HasNoChildren) "/" Feigned/Followed
    EXAMINE Feigned      OK

**Decision: land the pair and assert both halves, and leave the Bridge test as the only proof of
the third thing.** The live suite now reads the flag out of the subscribed listing, reads its
absence out of the plain one, and opens the name through the port. What that establishes is the
premise the keep rests on: a real server, one this repo builds and can rebuild after any bump,
flags a name unselectable and opens it, so believing a flag is wrong against a standard and not
only against somebody's mailbox. What it does not establish is that `list_folders` keeps such a
name, because the flag never reaches the listing `list_folders` makes on this server. That stays
proved only by `test_email_live.py` against the Bridge, and it is now filed as its own narrower
thing rather than as half of this one:
[the keep in the adapter's own listing is still one account](../refinements/tasks/400-the-keep-in-the-adapters-listing-is-one-account.md).
The two rejected configurations are prose here and nothing runs them, which is the other residue:
[the rejected probe configurations are prose only](../refinements/tasks/401-the-rejected-probe-configurations-are-prose.md).

**Naming.** `Feigned` says what is true of it: the unselectability is a pretence, and the name is
a mailbox. It sits with `Guarded` as a participle describing what the server does to the name, next
to the nouns `Parent`, `Child` and `Ghost` that describe what the name is. `Followed` is the child,
named for the subscription that is the entire cause of the parent's flag. Alternates weighed and
not taken: `Masked` and `Belied` for the parent, both true and neither as plain; `Watched` and
`Kept` for the child, the second colliding with the word this decision record already spends on the
half of the rule that keeps a name.

**One measured thing that is not about IMAP at all.** The plain-LIST reading was first written as
an exact tuple, `(\HasChildren)`, and it passed. It then reddened on the next run against the same
container, which is how the transience was found: this server starts sending `\UnMarked` with a
mailbox once something has searched it, and the port contract's own check searches every name
`list_folders` offers, so the first run against a fresh container and every run after it see
different tuples. The assertion now reads the words it is about, that no attribute in that listing
calls the name unselectable, and ignores the rest. An exact reading of a live server's flags is a
reading of that server's history as much as of its configuration.

**Validation.** `just check` green, run to completion in the session that landed this, output
captured to a file. The probe stack was brought up through `docker compose` and taken down around
every arm, the mail store being a tmpfs so each arm builds its tree from the edited script. This
host cannot let compose create a network (`all predefined address pools have been fully subnetted`,
a split default route rather than anything in this repo), so the network was pre-created with an
explicit subnet and compose adopted it; everything else in the compose file ran as written.
Mutations, each planted in the fixture, measured after a container recreate, and reverted from a
saved copy, over the probe's live suite (7 integration tests, `just email-folder-probe` against
`127.0.0.1:11143`) and `just check-crosscheck`. The email package's unit suite (110 tests,
integration deselected) is unmoved by all three, which is the point of a fixture:

| mutation | expected | observed |
| --- | --- | --- |
| the fixture stops subscribing `Feigned/Followed` | the parent loses the flag, so the subscribed listing has nothing to read | 1 of 7 live red, at the LSUB reading, and `crosscheck` red on the subscription mention |
| the fixture stops building `Feigned` as a mailbox, leaving it a bare node | the plain listing starts calling it unselectable, which is what the second assertion denies | 1 of 7 live red, twice in a row, at the plain-LIST reading, and `crosscheck` red on the parent's mailbox mention |
| rename the pair in the script alone | the fixture builds a tree the suite is not measuring | 1 of 7 live red, and `crosscheck` red 3 times over 2 couplings |
| all three reverted | back to green | 7 of 7 live green three runs running, one against a fresh container and two against a warm one |

## Addendum (2026-08-24): one mail root, handed to the fixture out of the environment

The probe's mail store is one path that three files had to agree about: the tmpfs in
`docker/docker-compose.imap-probe.yml` that makes the store throwaway, the tree
`docker/dovecot/probe-mailboxes.sh` builds under it, and the home
`docker/dovecot/probe.conf` resolves for the account. Five spellings, no declaration anywhere,
and nothing able to hold them together: `crosscheck.py` compares a declaration against the places
restating it, and inventing one in a suite with no use for the value would be the gate editing the
contract it watches. That is why the fixture part of the registry could tie the account and not
the root above it. The two halves failed differently. Move the conf's alone and dovecot resolves a
home nothing built, every mailbox missing at once, which is loud. Move the tmpfs alone and the
fixture keeps working while the store stops being throwaway, which is silent, and silence is what
this closes.

The answer is smaller than a gate. The root is written once, in the compose file, and the other
two files read it out of the environment.

### Dovecot does take a path from the environment, and the first syntax for it does not work

Measured against `dovecot/dovecot:2.3.21` itself rather than reasoned about, three configurations
in a row, each a container started from the real conf with the account's home written a different
way and read back with `doveadm user probe`:

| the conf says | what the server did with it |
| --- | --- |
| `home=$ENV:PROBE_MAIL_ROOT/%Lu` | not expanded at all; the userdb lookup answered with no fields, so nothing resolved |
| `home=%{env:PROBE_MAIL_ROOT}/%Lu` | expanded, and expanded to nothing: `doveadm user probe` reported `home /probe` |
| the same, plus the name on `import_environment` | `doveadm user probe` reported `home /srv/mail/probe` |

The second row is the one worth keeping. `%{env:...}` is a variable this server knows, and the
variable is empty because the master process passes its children a named subset of its own
environment; `import_environment` is the list, and the name has to be on it before the auth and
mail processes that do the expanding can see anything. A configuration that reads the environment
without that line fails in exactly the shape a wrong path fails in, so the line is not a detail
and the conf says so beside it. `$ENV:` is not dovecot's spelling here at all: the parser does
expand `$name` references to settings, `mail_plugins = $mail_plugins acl` reaching `doveconf` as
` acl`, which is what makes the first row a measurement rather than a typo.

### The one spelling is an anchor, not a substitution

The compose file declares `x-mail-root: &mail-root "/srv/mail"` and aliases it twice, into the
tmpfs and into `CORTEX_IMAP_PROBE_MAIL_ROOT` in the service's environment. An anchor rather than
`${CORTEX_IMAP_PROBE_MAIL_ROOT:-/srv/mail}` for two reasons. A substitution would spell the
default once per use, which is two spellings in one file and the same drift one file smaller. And
a substitution reads the shell that ran `docker compose`, so a variable of that name left in an
operator's environment would move a fixture whose whole value is that it is the same fixture every
time. The anchor is YAML, resolved before compose interpolates anything, and nothing outside the
file can reach it.

### What the trade actually is

The path had five spellings across three files and one of the drifts was silent. It now has one,
and what is spelled in several places is the variable's NAME: once in the compose file, three
times in the script, twice in the conf. Every drift of a name is loud, and each fails in its own
way rather than in a way that has to be recognised. Misspell it in the script and `set -u` stops
the container before it builds anything, `parameter not set` naming the line. Drop it from
`import_environment` and the expansion is empty, so every home resolves under the filesystem root
and all seven live tests go red at once. Rename it in the compose file and both of those happen
together. None of them is a fixture that quietly measures something else.

### The count included a setting that did nothing

The conf spelled the root twice, as the static userdb's `home=` and again as `mail_home`. Only the
first was ever read: a userdb that answers with a home is what `~` in `mail_location` expands to,
and `mail_home` is the fallback for a userdb that does not. Measured by misspelling the variable in
`mail_home` alone, which changed nothing, `doveadm user probe` still reporting
`home /srv/mail/probe` and all seven live tests still green. So one of the five spellings this
entry counted was dead configuration, and it is gone rather than carried forward under a new
spelling.

### The store is now checked rather than claimed

The compose file's own comment says the store is a tmpfs so that every start is empty and `down`
leaves nothing behind. Nothing enforced that, which is what made the silent half silent. The
entrypoint now asks the kernel before it builds anything: if the mail root is not a tmpfs mount it
prints one line and exits, so a store that stopped being throwaway is a container that will not
start.

That check is worth more than it looks, because of what the image does with the path. This image
declares `VOLUME /srv/mail` (and `/etc/dovecot`), so a tmpfs that moves off the mail root does not
leave the store on the container's writable layer: docker fills the path with an anonymous volume.
Measured on the pre-change fixture with the tmpfs moved alone, the store was an anonymous volume
docker had named for itself, a file written into it survived a container restart, and the volume
outlived `docker rm -f`. The old silent failure was therefore not only a store that keeps mail; it
was one that keeps mail on the host, under a name nobody chose, after the fixture is gone.

The same declaration has a residue this did not fix: `/etc/dovecot` is a volume too, and the
compose file binds only the single file inside it, so every probe run leaves an anonymous volume
behind that `down` does not remove, against the same comment's promise. Filed as
[R-424](../refinements/tasks/424-every-probe-run-leaves-an-anonymous-volume.md).

### The registry gained no row, and its subject did not move

The other option the entry offered was to ask whether `crosscheck.py` could hold a coupling whose
places are all far sides, with no declaration anywhere. It is not needed and is not taken: a value
with one place is not a coupling. The fixture part of the registry keeps the account row it
already had, whose mention now renders the account under the variable rather than under the
literal path (`$CORTEX_IMAP_PROBE_MAIL_ROOT/{value}`, still pinned at two occurrences, the tree
and the `chown`), and the paragraph that explained why the root could not be a row now explains
why there is nothing left to tie. The origin line on the entry named the constant scan's decision
record, which is where the gap was written down; the fixture is this record's, and that is where
this went.

### Proved able to fail, six times, over the probe's live suite

The suite every count below is over is the probe's own: **seven `integration`-marked tests** in
`brain/packages/email/tests/test_imap_probe_live.py`, run with `just email-folder-probe` against
the running container, excluded from the coverage gate and never run in CI. Each mutation was
planted in one file, measured after a container recreate, and reverted from a copy taken before
the first. This host still cannot let compose pick a network (`all predefined address pools have
been fully subnetted`, the split default route recorded in the addendum above), so every run added
a scratch override pinning an explicit subnet and changed nothing else in the file.

| # | mutation | expected | observed |
| --- | --- | --- | --- |
| 0 | the pre-change files, tmpfs moved alone | the silent failure this closes | 7 passed; the store an anonymous volume that kept a written file across a restart and outlived the container |
| 1 | the one spelling moved, anchor and all | everything moves together | 7 passed, `home /srv/probe-mail/probe`, the tmpfs there too |
| 2 | the tmpfs re-spelled to another path, alias dropped | the entrypoint refuses | `up --wait` failed, container exit 1, `the mail root is not the tmpfs the compose file mounts` |
| 3 | the name dropped from `import_environment` | the expansion empties and the homes go | 7 failed, `home /probe` |
| 4 | the name misspelled in the script's `ROOT` alone | `set -u` stops it, and the account row reddens | container exit 2, `CORTEX_IMAP_PROBE_MAILROOT: parameter not set`; `check-crosscheck` red, found 1 pinned 2 |
| 5 | the tmpfs dropped entirely | the entrypoint refuses | `up --wait` failed, container exit 1, same line |
| 6 | the name misspelled in `mail_home` alone, before it was removed | unknown, and the reason it was measured | 7 passed, home unchanged: the setting was inert, which is why it is gone |

Row 6 is the one that changed the shape of the fix rather than confirming it. Row 0 is the only
row that cannot be re-run from the tree, the files it needs being the ones this replaced.

**Validation.** The live suite was run before anything changed (7 passed), after the change
(7 passed) and again after the last mutation was reverted (7 passed), each through
`just email-folder-probe` against the container the compose file describes. `just check` green.

### Records

The record is the task file
[R-390](../refinements/tasks/390-the-probes-mail-root-is-spelled-in-three-files.md), which closes,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it, the three
fixture files, `scripts/fixturecouplings.py`, the email module contract, the IMAP runbook, and
this addendum.

## Addendum (2026-08-24): the fixture's configuration directory is a tmpfs too

The addendum above closed one half of what `dovecot/dovecot:2.3.21` declares and filed the other.
This closes the other. The image declares `VOLUME /etc/dovecot` beside `VOLUME /srv/mail`, and the
compose file mounted a single file inside the first, `/etc/dovecot/dovecot.conf`, which leaves the
directory itself to docker. Docker fills a declared volume path that nothing is mounted at with an
anonymous volume, seeded from the image's own copy of the directory, and `docker compose down`
without `--volumes` removes the container and the network and leaves that volume on the host under
a name nobody chose. So every single run of a fixture whose compose file promises it leaves
nothing behind left something behind.

**Measured before the change**, on this host, with the recipes an operator runs. `docker volume
ls` held 37 volumes; `just up-imap-probe` (with the scratch subnet override this host needs)
brought the stack up, and `docker inspect` showed the container's third mount as
`volume 95893b6a... -> /etc/dovecot` beside the two binds; `just down-imap-probe` removed the
container and the network, and `docker volume ls` then held 38. One run, one volume, and the
volume outlived the fixture.

### Two remedies, and why the blunt one is not the one taken

`--volumes` on the `down` recipe is the obvious fix and it is a worse one. It does not stop the
volume being made, only sweeps it after a well formed shutdown, so a container killed any other
way still leaks; it removes whatever named volume this stack ever grows, which is a rule about the
future written as a flag; and it leaves the compose file's promise resting on a recipe rather than
on the stack it describes. Mounting a tmpfs at the path gives docker nothing to anonymise in the
first place, and it is what the mail root already does, so the fixture ends with one rule about
both of the paths its image declares rather than two rules that happen to agree.

### The cert and the key were never in that directory

The compose file's own comment said the single-file mount was there so that "the self-signed cert
and key beside it in the image stay where they are". They are not files beside it.
`ls -la /etc/dovecot` in the image shows `cert.pem` and `key.pem` as symlinks into
`/etc/ssl/certs/ssl-cert-snakeoil.pem` and `/etc/ssl/private/ssl-cert-snakeoil.key`, which is a
directory the image declares nothing at. So the argument against covering the directory was an
argument about two symlinks, and the conf now names the pair the symlinks name. It is the same
self-signed cert the image ships, verified over the wire rather than by reading the setting back:
`openssl s_client -starttls imap` inside the container reports `subject=CN = localhost`, valid to
2033, which is the certificate that was being served before.

### The configuration is copied onto the mount, not bound onto it

The conf is now bound in at `/probe.conf`, beside the entrypoint, and the entrypoint copies it to
`$CORTEX_IMAP_PROBE_CONFIG_ROOT/dovecot.conf` before becoming the server. Binding it straight onto
`/etc/dovecot/dovecot.conf` over the tmpfs also works, and was rejected for what it does to the
next reader who edits the anchor. Dovecot's configuration directory is compiled into the binary
and nothing in this repo can move it. With the copy, a configuration root written as any other
path is a tmpfs somewhere nobody reads and a server loading the image's own settings, which has no
ACL plugin, so the live suite goes red at all seven tests. With the bind, the file would land
inside whatever docker anonymised at `/etc/dovecot`, the suite would stay green, and the leak
would be back with nothing saying so. The one spelling is therefore an anchor the fixture cannot
quietly disagree with, and the tmpfs check in the entrypoint covers the remaining case, a mount
dropped rather than moved.

### Proved able to fail, four times, over the probe's live suite

The suite every count below is over is the probe's own: **seven `integration`-marked tests** in
`brain/packages/email/tests/test_imap_probe_live.py`, run with `just email-folder-probe` against
the running container, excluded from the coverage gate and never run in CI. Each mutation was
planted in one file, measured after a container recreate, and reverted from a copy taken before
the first. This host still cannot let compose pick a network (`all predefined address pools have
been fully subnetted`), so every run added a scratch override pinning an explicit subnet, kept
outside the repo and deleted afterwards, and changed nothing else.

| # | mutation | expected | observed |
| --- | --- | --- | --- |
| 0 | the pre-change files | the leak this closes | 7 passed, and `docker volume ls` went from 37 to 38 across one `up`/`down` cycle, the container holding `volume ... -> /etc/dovecot` |
| 1 | the configuration root dropped from the `tmpfs` list | the entrypoint refuses | `up --wait` failed, container exit 1, `/etc/dovecot is not the tmpfs the compose file mounts; every run would leave a volume behind`, and one anonymous volume made |
| 2 | the anchor moved to `/etc/dovecot-probe`, alias and all | the tmpfs lands where nothing reads it and the server loads the image's settings | container healthy, 7 of 7 live red, and the container holding `volume ... -> /etc/dovecot` again |
| 3 | the conf's `ssl_cert` and `ssl_key` pointed back through the shadowed symlinks | dovecot cannot open them | container exit 89, `Fatal: Error in configuration file /etc/dovecot/dovecot.conf line 58: ssl_cert: Can't open file /etc/dovecot/cert.pem` |
| 4 | `CORTEX_IMAP_PROBE_CONFIG_ROOT` dropped from the environment | `set -u` stops it | container exit 2, `/probe-mailboxes.sh: 71: CORTEX_IMAP_PROBE_CONFIG_ROOT: parameter not set` |
| 5 | all reverted | green, and nothing left behind | 7 of 7 live green, no volume made while up, `docker volume ls` identical at 37 before the `up` and after the `down` |

Row 2 is the row the design is for. It is the only mutation that leaves a fixture which still
starts and still looks like itself, and the copy is what makes it red instead of quiet.

### What this does not check

Nothing in the repo notices when an image the compose files name declares a volume no compose file
mounts. Both halves of this were found by reading `docker image inspect` by hand, a year of runs
after the fixture landed, and a bump of the pinned image could add a third. A repo scan cannot ask
that question, having no images; the live suite could, being the one thing here that already talks
to docker about this container. Filed as
[R-425](../refinements/tasks/425-nothing-notices-an-image-volume-nobody-mounts.md).

**Validation.** The live suite was run before anything changed (7 passed), after the change
(7 passed) and again after the last mutation was reverted (7 passed), each through
`just email-folder-probe` against the container the compose file describes, with the volume set
read before and after each cycle. `just check` green.

### Records

The record is the task file
[R-424](../refinements/tasks/424-every-probe-run-leaves-an-anonymous-volume.md), which closes,
[R-425](../refinements/tasks/425-nothing-notices-an-image-volume-nobody-mounts.md), which opens,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from both, the three
fixture files, the email module contract, the IMAP runbook, and this addendum.

## Addendum (2026-08-25): the question the last two addenda answered by hand is now a gate

Both of the paths `dovecot/dovecot:2.3.21` declares were found the same way, by reading
`docker image inspect` by hand, months of runs apart, each time after the leak had already been
happening on every start. The remaining deferral was to make something ask the question. It is
asked now, and the first thing it answered was that this fixture was never the only offender.

**A survey of every image any compose file here names, run before writing anything.** Inspected
with `docker image inspect --format '{{.Config.Volumes}}'` on this host today, and the three
images this repo builds were asked as built images rather than as Dockerfiles, since a built
image's answer already carries whatever its bases declared. Six declare nothing:
`ghcr.io/ggml-org/llama.cpp:server`, `node:22-bookworm-slim`, `redis:8-alpine`, and
`cortex-brain`, `cortex-model-host` and `cortex-mcp-email`, none of whose Dockerfiles here
carries a `VOLUME` line either. Two declare something.
`dovecot/dovecot:2.3.21` declares `/etc/dovecot` and `/srv/mail`, and both are covered by the
tmpfs mounts the two addenda above put there, so this fixture is clean as it stands.
`pgvector/pgvector:pg16` declares `/var/lib/postgresql/data`, and it is run by two services.

**The second one was leaking, and had been all along.** `pg-backup` in
[docker/docker-compose.memory.yml](../../docker/docker-compose.memory.yml) runs the same image as
the server so that `pg_dump` matches the major version, and mounts only its dump directory and
its script. It never opens a data directory of its own: `docker/postgres/backup.sh` dumps over the
network from the `postgres` service, and the compose file overrides the image's entrypoint, so
none of the upstream `PGDATA` bootstrap runs either. Docker does not care. The declaration is on
the image, the path had nothing mounted at it, and the sidecar therefore collected a fresh
anonymous volume on every start of the memory stack. Reproduced with exactly that mount set and
no others before the fix, and the third mount is the one nobody asked for:

```
$ docker inspect "$id" --format '{{range .Mounts}}TYPE={{.Type}} NAME={{.Name}} DST={{.Destination}}
{{end}}'
TYPE=bind NAME= DST=/backup.sh
TYPE=bind NAME= DST=/backup
TYPE=volume NAME=aa9c20129d789ac62a5484c4be308368b5c5630c5ebb30291dc7f9a51a376179 DST=/var/lib/postgresql/data
```

It takes the fix the fixture above already uses, a `tmpfs` at the declared path, which leaves
docker's declaration nothing to fill. Nothing else changes: the sidecar reads its source over the
network and writes its output to a bind. Confirmed by creating the same container again with
`--tmpfs /var/lib/postgresql/data` added and nothing else altered, where the same `docker inspect`
now reports two mounts rather than three:

```
TYPE=bind NAME= DST=/backup.sh
TYPE=bind NAME= DST=/backup
```

**The check itself is not in this suite, and that is the reasoned part.** The deferral proposed an
assertion in the probe's live suite asking docker for the running container's mounts, with a
`just` recipe as the alternative. Both were reconsidered and both were passed over, for the same
reason: they only ever ask about a container somebody is already running, and the leak found today
was in a stack the probe's suite never starts. The wide question, every image against what every
compose file mounts, is the one worth asking, and it is asked by `scripts/volumecheck.py` reading
a recorded answer rather than a docker daemon, with `just image-volumes` re-deriving that record
from docker by hand. Why a recorded answer rather than a live one, and why this does not become a
second recipe outside `just check`, is argued once in the ADR-0011 addendum on evidence that is
out of the gate's reach, which both of the deferrals that produced it point at.

### Proven able to fail

**Suite: the `scripts` pytest suite (`cd scripts && uv run pytest`), 1008 tests, 1 deselected**,
with `gate=` the exit code of `volumecheck.py --root ..` over the real tree beside it. Each
mutation applied alone and reverted. Nineteen rows, seventeen of them expected red and two
expected green.

| # | mutation | expected | result |
|---|---|---|---|
| T1 | the `pg-backup` tmpfs dropped, so a declared volume is uncovered | red | caught (gate=1 suite=1) |
| T2 | the pgvector pin bumped a major, so the image is unrecorded | red | caught (gate=1 suite=1) |
| T3 | a row added for an image no compose file names | red | caught (gate=1 suite=1) |
| T4 | the pgvector row emptied, so the record stops matching docker | red | caught (gate=0 suite=1) |
| T5 | the probe's anchored configuration tmpfs dropped | red | caught (gate=1 suite=1) |
| T6 | the mail-root anchor spent as its literal path (must stay green) | green | green (gate=0 suite=0) |
| T7 | a covering tmpfs written with a trailing slash (must stay green) | green | green (gate=0 suite=0) |
| C1 | the coverage rule never fires | red | caught (suite=1) |
| C2 | stale rows not reported | red | caught (suite=1) |
| C3 | an unrecorded image read as declaring nothing | red | caught (suite=1) |
| C4 | anchors no longer resolved | red | caught (gate=1 suite=1) |
| C5 | a tmpfs stops counting as cover | red | caught (gate=1 suite=1) |
| C6 | a fragment read as a definition | red | caught (suite=1) |
| C7 | the exact-path rule relaxed to accept a parent mount | red | caught (suite=1) |
| C8 | an empty compose walk becomes an empty pass | red | caught (suite=1) |
| C9 | a trailing slash becomes a second spelling | red | caught (suite=1) |
| C10 | an inspect failure skipped instead of reported | red | caught (suite=1) |
| C11 | an unreadable compose file becomes a silent skip | red | caught (suite=1) |
| C12 | the reader walks past a shape it was not taught | red | caught (suite=1) |

**The first pass was 18 of 19, and the miss is the useful row.** C6, a service fragment read as a
definition, produced no fault, because the fixture's fragment was named `brain` and `tree-brain`
happened to be a recorded row, so the mutant asked a question that had an answer. The fixture's
fragment is now named for nothing in the record and the definition count is pinned, and C6
reddens. The real tree cannot catch C6 either, both of its build-only services being recorded, so
that one test is the only thing holding the guard: worth saying plainly, since a row that reddens
only in a fixture is exactly the row a later reader is tempted to delete.

The rederive half was proved against a real daemon rather than a fake: with the pgvector row
emptied, `just image-volumes` exits 1 saying `pgvector/pgvector:pg16: recorded nothing, docker
says /var/lib/postgresql/data`, and with the row restored it reports the record agreeing with
docker on all eight images. One thing could not be shown at compose level: `docker compose ... up
--no-start` was refused by this host's daemon with `all predefined address pools have been fully
subnetted`, which is an environment condition unrelated to any of this, so the container-level
`docker create` above stands in for it and `docker compose config` was used to confirm the tmpfs
reaches the service.
