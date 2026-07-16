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
  below); **attachments remain** (they need a bytes-transport decision, recorded there).
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
[email-confirmer.md](../refinements/email-confirmer.md).

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

**Declined**, docs-only. The entry stays in [email-confirmer.md](../refinements/email-confirmer.md)
verbatim as the historical record, annotated with this outcome, and moves to the backlog's
dead-until-a-consumer list. It reopens only if the outbound-on-tainted decision is itself revisited
with new evidence that a confirmation card converts reflexive approval into scrutiny, **and** a real
`SENDER`/`URI` producer exists to name the source, not on provenance plumbing alone. Nothing in the
seam, the proto, the confirmer, or the gate changed.
