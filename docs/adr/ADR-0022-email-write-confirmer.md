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
- Richer send shapes (cc/bcc/HTML/attachments) behind the same tool name.
- A structured confirm-resolution event so the overlay can close a stale card exactly.
- Trust (as opposed to gating) overlays for remote tools. Still nothing needs one.
- Batching / per-tool session allowlists against confirmation fatigue.
- Salience of `ToolActivity`: still emitted by nothing; the confirm card is the first
  mid-turn tool surface, and a general tool-activity chip remains an overlay-gap item.
