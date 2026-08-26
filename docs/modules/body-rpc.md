# body/crates/rpc (`body_rpc`)

**Purpose.** The body's gRPC adapter for the seam ([proto/body.proto](../../proto/body.proto),
the single source of truth): the committed tonic/prost stubs for `cortex.seam.v1` plus the
two directions of the seam, namely `BrainSeamClient`, the tonic implementation of the
`body_core::BrainTransport` port (body→brain), and `body_service`, the `BodyService` server
over the `body_core::AudioControl` port (brain→body, Slice 9, ADR-0023) and the
`body_core::Notify` port (the reminder toast, Slice 9.5, ADR-0025). Thin translation
only, with no business logic, and no retries *here*: bounded retry is composed over this adapter
by `body_core`'s `RetryingTransport` decorator (ADR-0024), for which `connect_lazy_with_token`
supplies a reconnecting channel. **The deadline is announced here and enforced there**, for a
sharper reason than symmetry: tonic attaches its `transport::Error` to the `Status::cancelled` it
raises when its own request timeout expires, so `status_to_error` classifies that expiry
`TransportError::Connection`, which is honest (the connection indicator draws `Down`, and nothing
answered) but is also in the *retryable* set, so a deadline configured on the endpoint would be
retried against a peer that has just proved too slow to answer. The per-attempt deadline is
therefore enforced in the core over the `Sleeper` port and arrives typed as
`TransportError::Timeout`, outside the transient set
(ADR-0024 deadline addendum, as corrected the same day: the first reading of tonic here claimed a
*sourceless* status classified `Rpc`, and running it says otherwise). What this adapter does put
on the wire is the **courtesy** `grpc-timeout` header (ADR-0024 courtesy-header addendum), which a
client sends once `announcing(plan)` tells it which plan the decorator above it enforces. Sending
it necessarily arms tonic's clock too (the channel's own `GrpcTimeout` layer parses the header back
off the outgoing request), so the announced value is the plan's `announced_deadline_for`, strictly
longer than what the core enforces: the two clocks are ordered by construction and the retryable
one never fires first. `tests/client.rs` proves all of it against a fake brain that accepts the
call and never answers: the core's bound ending it, what tonic's own expiry classifies as, and the
bound still winning with the announcement armed. The status→error mapping is split into
`status.rs`
(`status_to_error` / `error_chain`, shared by every direction) to keep both files under the
line cap, and what one call carries on the wire into `call.rs` (`SeamCall`, the per-call
interceptor, and the `SEAM_TOKEN_HEADER` declaration it attaches).

**Public contract.**

- `BrainSeamClient` (`Clone` lets clones share the channel; `Debug` never carries the seam
  token: it is hand-written and prints the token's *presence* as `<redacted>`, the derive having
  been given up when the client started holding the `MetadataValue` itself rather than a
  `Debug`-less interceptor. `tests/client.rs` asserts a configured token cannot reach a `{:?}`).
  What it holds is the channel, the token, and optionally the `RetryPlan` it announces from; the
  generated client is built **per call** (`SeamCall`, `src/call.rs`), which is the only way a
  per-call value reaches an interceptor that is otherwise built once per connection.
  - `BrainSeamClient::connect(addr: &str) -> Result<Self, TransportError>` (async)
    dials e.g. `http://127.0.0.1:50051` sending no seam token; an invalid URI or
    unreachable endpoint maps to `TransportError::Connection`.
  - `BrainSeamClient::connect_with_token(addr: &str, token: Option<&str>) -> Result<Self, TransportError>`
    (async, ADR-0016) is like `connect`, additionally attaching `token` as
    `x-cortex-seam-token` metadata on **every** call (a tonic client interceptor) when
    `Some`, which is what a `CORTEX_SEAM_TOKEN`-protected brain requires; the Tauri shell reads
    that env var and passes it here. A token that is not valid ASCII metadata maps to
    `TransportError::Connection` before any dial; a wrong/missing token surfaces per the
    normal status mapping as `TransportError::Rpc { code: "Unauthenticated", .. }`.
  - `BrainSeamClient::connect_lazy_with_token(addr, token) -> Result<Self, TransportError>`
    (**sync**, ADR-0024) is like `connect_with_token` but over a *lazy* channel
    (`Channel::connect_lazy`): construction never dials, so it fails only on a bad URI or a
    non-ASCII token, never on reachability, and each RPC (re)establishes the connection on
    demand. This is the channel `body_core`'s `RetryingTransport` retries over. A call
    against a briefly-down brain fails `Connection`, the decorator backs off, and tonic
    reconnects transparently. The ungated shell's `seam::connect()` composes the two.
  - `BrainSeamClient::announcing(plan: RetryPlan) -> Self` (ADR-0024 courtesy-header addendum)
    turns on the courtesy `grpc-timeout` header: every unary call then announces
    `plan.announced_deadline_for(method)`, which is that method's enforced deadline plus
    `ANNOUNCED_DEADLINE_GRACE_MS` (250 ms). `Converse` announces nothing (the plan gives a turn no
    deadline, and a header would hand tonic a clock to end one with), and a client nobody called
    this on announces nothing at all, which is what every constructor returns. `plan` must be the
    **same plan the decorator above the client enforces**: `seam::connect()` reads
    `plan_from_env()` once and hands the one value to both, which is what makes the ordering
    between the two clocks structural rather than a convention. An announcement past
    `MAX_ANNOUNCED_DEADLINE_MS` (99999999 ms, about 27.8 hours) is dropped rather than clamped or
    rounded, a shorter announcement being the one thing that would lose the race on purpose. That
    bound is the top of `grpc-timeout`'s millisecond rung and not the 8-digit ceiling tonic's
    encoder panics on, which is four rungs higher: one step above it the unit is a whole second,
    the truncation onto it is four times the grace, and the clock tonic arms from the decoded
    header would then run **under** the bound the core enforces (ADR-0024 unit-ladder addendum).
  - `impl BrainTransport`: `health()` calls `BrainService.Health`; an Ok reply maps to
    `SeamHealth { ready, detail }`. A non-OK gRPC status splits by origin: a status
    tonic *synthesized* from a client-local transport failure (detected by a
    `tonic::transport::Error` in the status's `source()` chain, e.g. the brain died
    after the channel connected) maps to `TransportError::Connection`; a status
    genuinely reported by the brain maps to `TransportError::Rpc { code, message }`
    where `code` is the status-code name (`Internal`, `Unimplemented`, …).
  - `converse(session_id, text, decisions)` opens `BrainService.Converse` (`src/converse.rs`,
    one turn per call, ADR-0011): the request stream is `once(ClientEvent{session_id,
    user_turn})` chained with one `confirm_response` per `ConfirmDecision` from the caller's
    `decisions` stream (ADR-0022). The client half-closes when `decisions` ends, so an
    empty stream keeps the pre-8.8 one-shot shape. Each streamed `ServerEvent` maps to a
    `TurnEvent`: `TextDelta`→`Delta`, `ToolActivity`→`ToolActivity`,
    `ToolOutcome`→`ToolOutcome` (non-terminal), `StatusUpdate`→`Status`,
    `ConfirmRequest`→`ConfirmRequest` (non-terminal, since the brain suspends the gated call and
    denies it fail-closed if no matching decision ever arrives),
    `ConfirmResolved`→`ConfirmResolved` (non-terminal: the brain ended that wait itself, so the
    caller closes the question and the turn streams on), `TurnComplete`→`Complete`
    (terminal), `SeamError`→`Failed` (terminal). A status raised at the call or mid-stream
    reuses the same origin split (`status_to_error`, shared with `health`) → `Rpc`/`Connection`;
    an empty `ServerEvent` or a stream that ends before `TurnComplete` → `Protocol`. The
    reply mapping is built with `async-stream`, the request chain with `tokio-stream`.
  - `list_sessions(limit)` / `session_messages(session_id)` (the read-only session views,
    ADR-0021; `src/sessions.rs`) are unary calls to `BrainService.ListSessions` /
    `GetSessionMessages` mapping each reply row to a core `SessionSummary` (including its `pinned`
    flag, ADR-0021 pinning addendum) / `SessionMessage`; a non-OK status maps through the
    `SeamCall` the client hands in (`status_to_error` plus that call's announcement) →
    `Rpc`/`Connection`/`Timeout` (a store failure is `Rpc{code:"Unavailable"}`). Kept in their own
    module so `client.rs` stays under the line cap.
  - `rename_session(session_id, title)` (the user-driven catalog write, ADR-0021 management
    addendum; same `src/sessions.rs`) is a unary call to `BrainService.RenameSession`; the reply
    is a bare ack, so success maps to `()` and a non-OK status maps the same way as the reads.
  - `delete_session(session_id)` (the user-driven DESTRUCTIVE catalog write, ADR-0021 delete
    addendum; same `src/sessions.rs`) is a unary call to `BrainService.DeleteSession`; the reply
    is a bare ack, so success maps to `()` and a non-OK status maps the same way (a store or
    memory failure is `Rpc{code:"Unavailable"}`).
  - `set_session_pinned(session_id, pinned)` (the user-driven pin toggle, ADR-0021 pinning
    addendum; same `src/sessions.rs`) is a unary call to `BrainService.SetSessionPinned`; the reply
    is a bare ack, so success maps to `()` and a non-OK status maps the same way (a store failure is
    `Rpc{code:"Unavailable"}`).
  - `get_preferences()` / `set_preference(key, value)` (the user's settings record, ADR-0032;
    `src/preferences.rs`) are unary calls to `BrainService.GetPreferences` / `SetPreference`,
    mapping the reply rows to plain `(key, value)` tuples and the write's bare ack to `()`. Same
    status mapping; nothing special-cases a brain with no preference store, which answers an empty
    record and accepts a write silently rather than a status.
  - `list_due_reminders()` / `ack_reminder(reminder_id)` (the reminder pull path, ADR-0025;
    `src/reminders.rs`, split for the same reason) are unary calls to
    `BrainService.ListDueReminders` / `AckReminder`, mapping each reply row to a core
    `DueReminder` and the ack reply to its `acked` bool. Same status mapping; nothing here
    special-cases the schedule-free brain, which answers an empty list and `acked=false`
    rather than a status.
  - Every `TransportError::Connection` message folds the error's full `source()` chain
    (e.g. `transport error: tcp connect error: Connection refused (os error 111)`), so
    tonic's opaque `"transport error"` `Display` still names the root cause.
- `status_to_error(status: &Status) -> TransportError` (`src/status.rs`) is that mapping as a
  function: a status carrying a `tonic::transport::Error` anywhere on its `source()` chain is
  `Connection`, anything else is `Rpc`. Public only so the contract suite can assert it against
  statuses tonic really produces, the expired request timeout above being the one whose answer
  a source reading got wrong. Its crate-internal twin `announced_status_to_error(status,
  announced)` is what a call that announced a deadline maps through, and it adds exactly one
  answer: a **brain-sent** `DEADLINE_EXCEEDED` becomes `TransportError::Timeout { after }`
  carrying the announcement, since the body's own expired clock and the brain's report of the
  same deadline mean one thing to everything above the adapter. tonic's local expiry is caught by
  the transport-source arm before that one and is unmoved; a `DEADLINE_EXCEEDED` on a call that
  announced nothing stays `Rpc`, there being no deadline of ours to name. All three are terminal,
  so no retry decision turns on the difference.
- `body_service(audio: A, notifier: N, token: &str)` (Slice 9, ADR-0023; the notifier joined
  in Slice 9.5, ADR-0025; `src/server.rs`) is the brain→body direction: builds the
  `BodyService` server over an `AudioControl` backend, a `Notify` backend, and a
  `ScreenCapture` backend, fronted by the seam-token validator. Its pieces:
  - `OsService<A: AudioControl, N: Notify, S: ScreenCapture>` is the generated `BodyService`
    trait over the injected backends (named `VolumeService` while volume was the only OS
    action).
    `get_volume`/`set_volume` map the wire messages onto the volume port (the level
    clamp lives in `body_core::VolumeChange`, not here); `notify` builds a
    `body_core::Notification` from the wire values, which is where the inert-text rule is
    applied, and answers `NotifyReply { shown }`; `capture_screen` delegates to `src/screen.rs`;
    `inject_input` answers `Status::unimplemented` until its slice. No state is held. Volume is
    read from the OS on demand, a notification is fire and forget, and a capture's pixels live
    only for the call that returns them (the one hard rule).
  - `screen::capture(...)` (Slice 10, ADR-0029) owns the capture translation: it resolves the
    wire's `max_edge`/`max_bytes`/`target` fields into a `body_core::CaptureRequest`, runs the
    blit, the
    pure-core `Capture::from_bgra` policy, the clock read, and the receipt inside **one**
    `off_worker` hop, then maps the `Capture` onto `ImageBlob` (including `source_width`/
    `source_height`, which stay the **display's** even when the picture is one window, and
    `captured_at_unix_ms`). `resolve_target` is where proto3's unknown-enum rule is spent: a
    value this body does not name reads as `CaptureTarget::Display`, which is the only honest
    answer and is the picture this seam has always sent. `encoded_target` fills the reply's
    `resolved_target` from `Capture::covers_display()`, the same predicate the receipt is picked
    by, so the sentence the user is shown and the sentence the brain shows the model cannot
    disagree about one picture. Error mapping, one code per variant so
    the brain
    can tell them apart: `NoDisplay -> FailedPrecondition`, `NoTarget -> FailedPrecondition`
    (host state again: it works the moment a window is on screen), `Disabled ->
    PermissionDenied`,
    `Backend -> Internal`, `TooLarge -> ResourceExhausted`. **Nothing this server answers is
    `Unavailable`**, which is the rule the brain's classifier rests on: tonic synthesizes that
    code client-side for a channel that cannot connect and grpc-python cannot tell a synthesized
    status from a sent one, so leaving it unspent makes it mean exactly "the call never arrived"
    (ADR-0023's 2026-08-08 addendum). The receipt is a
    `body_core::Notification` built from the fixed body-owned `CAPTURE_RECEIPT_*` strings,
    picking the screen sentence or the window one by `Capture::covers_display()`, which is what
    was **sent** rather than what was asked for, and
    is **best effort**: by the time it runs the pixels have been read, so a dead notification
    service must not also cost the capability. `receipts` (the host's
    `CORTEX_HOST_CAPTURE_NOTIFY` switch, resolved by the shell) turns it off.
  - `off_worker(call, to_status)` is where every handler's **one synchronous OS call**
    actually runs: `tokio::task::spawn_blocking`, not inline (the ADR-0023 deferral, closed
    2026-07-16). Both OS ports are sync because the OS is (Core Audio and the toast manager
    are COM, which has no async form), and a COM call parks its thread for as long as the
    audio stack or the notification service takes; inline that would park an **async worker**
    of the runtime the overlay's own seam calls share. The backends therefore sit behind an
    `Arc` inside `OsService`, purely so a handler can lend one to the blocking thread; the
    service still holds no state. Nothing COM-shaped crosses a thread, which is what makes
    this safe rather than a bug: `WindowsAudioControl` is a unit struct and `WindowsNotify` an
    app-id string, and each resolves its own interface *inside* the closure, so every COM
    pointer is created and dropped on the one thread that uses it. A backend that panics
    mid-call arrives as a join failure and answers `Internal`, because letting the panic
    escape the handler would cost the brain the whole connection instead of one call.
  - `audio_error_to_status(&AudioError) -> Status` is the inverse of
    `client::status_to_error`: `NoEndpoint`→`FailedPrecondition` (host state, and it works again
    once a device is there), `Backend`→`Internal`. `notify_error_to_status(&NotifyError) -> Status`
    splits the same way (`Unavailable`→`FailedPrecondition`, `Backend`→`Internal`); the variant
    keeps its `body_core` name because that name is about the host, not about gRPC. A declined
    notification is **not** an error: `shown=false` rides the reply, because the brain reads
    it as "push did not happen" exactly like a status and the reminder stays deliverable
    either way, so turning a user preference into a gRPC failure would only lie to the logs.
  - `SeamTokenValidator` (`src/auth.rs`) is a tonic server `Interceptor`, the mirror of the
    client `SeamTokenInterceptor` (ADR-0016, reversed for this direction). Rejects any
    call lacking a matching `x-cortex-seam-token` with `UNAUTHENTICATED` before any handler
    runs; the compare is constant-time (the Rust twin of `secrets.compare_digest`).
    **Always attached** but a **pass-through when the configured token is empty** (a
    tokenless deployment is byte-for-byte the tokenless server, which is the single-type
    equivalent of the brain's register-only-when-set). Deliberately not `Debug`: it holds
    the shared secret.
  - The bind/serve lifecycle (address, runtime) lives in the ungated Tauri shell; this
    crate holds only the coverable translation.
- `generated` is the codegen for the whole proto package: message types plus
  `brain_service_client::BrainServiceClient`,
  `brain_service_server::{BrainService, BrainServiceServer}` and the `BodyService`
  counterparts (`body_service_client`/`body_service_server`, now driven by the Slice 9
  server above and its contract tests). Generated code: exempt from lint, coverage, and
  the line cap (ADR-0002 decision 4). Public so contract tests and server wiring can drive
  it directly.

**Stub regeneration** (the `just proto` loop). Stubs are committed under
`src/_generated/`; normal builds and CI run **no** codegen and never need `protoc`.
After editing the proto (extend, never renumber, since v0 field numbers are frozen):

```sh
cd body && CORTEX_REGEN_PROTO=1 cargo build -p body-rpc
```

`build.rs` then runs `tonic-prost-build` (`protoc` 35.x on PATH) and rewrites
`src/_generated/cortex.seam.v1.rs`. Output is deterministic for a pinned toolchain:
regenerating with an unchanged proto must leave `git diff` empty.

**Live checks** (AGENTS.md gate 3, the Rust `integration` suite, ADR-0003 decision 3).
The `#[ignore]`d tests in `tests/live.rs`, run by `just seam-health`. The roster below is every
one of them and nothing else, held that way by `scripts/rostercheck.py`, so a check the suite
gains and this list does not, or a name here whose check is gone, is a red rather than a reader
misled (ADR-0003 live-roster addendum). It opens with no tally, a count restated beside a list
being the half that drifts first here; each bullet says what its check needs, and not all of them
need a brain:

```sh
cargo test -p body-rpc --test live -- --ignored
```

They read `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`, which matches the brain
server's `CORTEX_SEAM_HOST`/`CORTEX_SEAM_PORT` defaults `127.0.0.1`/`50051`) and
`CORTEX_SEAM_TOKEN`, which is **a precondition of the suite rather than an option**: one check
proves a wrong token is refused, and a brain serving without one accepts every token there is,
so it fails naming what it needs. `just seam-health` refuses to start without the variable for
that reason (ADR-0016 addendum on the checked precondition).

- `brain_reports_ready_over_the_live_seam` calls `Health` via `BrainSeamClient` and
  asserts `ready`.
- `converse_round_trips_one_turn_over_the_live_seam` (Slice 3) drives the raw generated
  `BrainServiceClient`, deliberately not `BrainTransport`, which grows a typed converse
  method only with the body slices. It opens the bidirectional `Converse` stream, sends
  one `ClientEvent{session_id, user_turn}` with a session id unique per run (so reruns
  never share session state), collects `TextDelta`s until `TurnComplete` (tolerating
  interleaved `ToolActivity`/`StatusUpdate`, failing on `SeamError`), and asserts at
  least one delta arrived, the concatenated text is non-empty, and `TurnComplete`
  carries a non-empty `turn_id`.
- `the_link_probe_classifies_the_live_brain_and_a_peer_that_cannot_serve` (ADR-0011 addendum)
  runs what the overlay's connection indicator runs, `body_core::probe_link`, over a **lazy**
  client: the live brain must classify `Ready` with a non-empty detail, and a peer that accepts
  the dial and drops it must classify `Down` with the dial failure rather than raising. Lazy on
  both, since an eager connect would fail before the probe could classify anything. The peer is
  the suite's own listener rather than a closed port, because this client carries no deadline
  and a closed port is not refused everywhere (ADR-0024 host-shape addendum).
- `session_reads_round_trip_over_the_live_seam` (Slice 8.7, ADR-0021) seeds one turn over
  the raw `Converse` to persist a session, then reads it back over the typed
  `BrainTransport`: `list_sessions(50)` must return the chat with its derived title (the
  first user message) and a real last-activity timestamp, and `session_messages` the user
  turn + assistant reply in order. Needs only brain + Redis (no GPU).
- `the_ack_write_is_answered_once_against_the_live_brain` (ADR-0025) pins the retry gate's
  refusal on the wire: `ack_reminder` of an unknown id answers `false` and costs one round
  trip rather than a backoff.
- `a_rejected_seam_token_is_answered_at_once_and_never_retried` (ADR-0016) dials the live brain
  with a deliberately wrong token: the answer must be `Degraded` (the brain answered), the
  detail must open `Unauthenticated`, and it must arrive with no wait spent, since a terminal
  status is not retried. This is the check that needs the brain to be serving with a token.
- `the_probe_budget_bounds_a_down_verdict_against_a_dead_address` (ADR-0024) probes
  `http://127.0.0.1:1` through `RetryingTransport` on a real `Sleeper` and asserts the verdict
  is `Down` inside the budget. The bound is all it asserts: what a dial to a closed port costs
  is the host's fact, not the seam's (refused in microseconds on a Linux stack, dropped where
  loopback belongs to a Windows host, which spends the attempt's whole deadline instead).
- `the_probe_trims_its_attempts_where_a_read_spends_them_all` (ADR-0024 host-shape addendum) is
  the patience proof, and the one check here that needs no brain: against a loopback peer of its
  own that accepts each dial and drops it, **counting dials on the wire**, the probe must spend
  exactly 2 attempts with one real 400 ms wait between them while the same schedule leaves the
  read all 5. A clock cannot count attempts, which is why this one does not try to.

Being ignored, they never run in CI and never count toward coverage.

**Invariants.**
- Thin adapter: translate types and errors, nothing else; everything crossing the seam
  is declared in `proto/body.proto` first.
- Generated code lives only in `src/_generated/` (never hand-edited), pulled in via the
  `generated` wrapper module whose inner allows scope the clippy exemption; the
  `check-body` coverage run excludes it via `--ignore-filename-regex '/_generated/'`.
  Hand-written code is fully gated: 100% line+region+branch.
- The courtesy deadline is contract-tested off the **request the fake brain received**, since no
  reply echoes a header: the fake records every call's `grpc-timeout`, and the checks assert the
  per-method value (a probe and a read announce differently), silence from a client with no plan
  and from every turn, silence rather than a panic for a deadline the header cannot spell, silence
  for one it spells only in whole seconds and a header still sent for the last bound below that
  rung, that a
  hanging brain still ends as `Timeout` with the announcement armed (the ordering, measured rather
  than asserted), and that a brain-sent `DEADLINE_EXCEEDED` arrives as the same `Timeout`. The
  rung case reads the truncation off `tonic::Request::set_timeout` itself rather than off tonic's
  source, so a ladder that moves under a version bump reddens the case that rests on it.
- Contract tests exercise a scripted in-process fake `BrainService` over loopback
  (`127.0.0.1:0`) only, which is CI-safe, with no real network. They cover both sides of the
  status-origin split, including brain death after a successful connect (graceful
  fake shutdown → next `health()` must be `Connection`, not `Rpc`); the lazy
  constructor (ADR-0024, covering a healthy round-trip over a lazy channel, construct-then-fail
  against a dead endpoint, bad URI, non-ASCII token); and the confirm
  round-trip (ADR-0022): the fake emits `ConfirmRequest` mid-turn and asserts the
  echoed `ConfirmResponse` arrives on the still-open request stream (approve and
  deny, answered reactively over a channel), a `ConfirmResolved` for a confirm the caller
  never answers (the brain's timeout, proven non-terminal because the reply and
  `TurnComplete` still follow it), plus the half-close of an empty decisions stream. The reminder pull (ADR-0025) is covered the same way: two scripted
  rows differing in every flag prove the row mapping (taint included), an ack of the
  deliverable id answers `true` while an unknown id answers `false` (proving the id
  crossed the wire and that "nothing to clear" is an answer, not an error), and a
  scripted store failure maps both calls to `Rpc{code:"Unavailable"}`.
- The `body_service` server (Slice 9) is contract-tested the same way, via a real loopback
  server over a fake `AudioControl` and a fake `Notify`, to 100% line+region+branch:
  `get_volume`/`set_volume`
  happy paths, both `audio_error_to_status` arms, the `Unimplemented` handlers, and the
  `SeamTokenValidator` pass-through (empty token) plus its accept/reject arms (matching,
  wrong, and missing token). The push notification (ADR-0025) adds four: a shown toast whose
  recorded `Notification` proves the wire text reached the backend already inert and badged
  (the fake holds its record behind an `Arc`, so the test reads what actually crossed after
  the fake moved into the server), a declined one answering `shown=false` rather than a
  status, and both `notify_error_to_status` arms. `off_worker` adds three more: both fakes
  record **which thread** each call ran on, and since `#[tokio::test]` is a current-thread
  runtime (the whole server runs on the test's own thread), a backend reporting a different
  thread is the proof the call left the async worker; a panicking audio backend answers
  `Internal` twice over the *same* channel, proving the connection survives it; a panicking
  notification backend answers the same way.
- Every one of those runs twice per gate, alphabetically under the stable `cargo test` and
  permuted under the nightly coverage step's fixed `--shuffle-seed`; the rule for adding a test to
  the biggest binaries in this workspace is in `docs/modules/body-core.md`, since the shuffle is
  `check-body`'s and not any one crate's.

**Dependencies.** `body-core` (the port), `tonic` + `tonic-prost` + `prost`, plus
`async-stream` (builds the `converse` reply mapping), `tokio-stream` (chains the confirm
decisions onto the request stream, promoted from dev-only in Slice 8.8, ADR-0022),
`futures-core` (the `Stream` trait) and `tokio` with `rt` only (`spawn_blocking` for the
synchronous OS calls); build-dependency `tonic-prost-build` (idle unless
`CORTEX_REGEN_PROTO=1`); dev-only `tokio` features (`macros`, `net`, `rt-multi-thread`,
`sync`).
