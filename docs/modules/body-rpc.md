# body/crates/rpc (`body_rpc`)

**Purpose.** The body's gRPC adapter for the seam ([proto/body.proto](../../proto/body.proto),
the single source of truth): the committed tonic/prost stubs for `cortex.seam.v1` plus the
two directions of the seam, namely `BrainSeamClient`, the tonic implementation of the
`body_core::BrainTransport` port (body→brain), and `body_service`, the `BodyService` server
over the `body_core::AudioControl` port (brain→body, Slice 9, ADR-0023). Thin translation
only, with no business logic, and no retries *here*: bounded retry is composed over this adapter
by `body_core`'s `RetryingTransport` decorator (ADR-0024), for which `connect_lazy_with_token`
supplies a reconnecting channel. The status→error mapping is split into `status.rs`
(`status_to_error` / `error_chain`, shared by every direction) to keep both files under the
line cap.

**Public contract.**

- `BrainSeamClient` (`Clone` lets clones share the channel; `Debug` never carries the seam
  token: the interceptor holding it has no `Debug`, and tonic prints interceptors by type
  name only).
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
    `TurnEvent`: `TextDelta`→`Delta`, `ToolActivity`→`ToolActivity`, `StatusUpdate`→`Status`,
    `ConfirmRequest`→`ConfirmRequest` (non-terminal, since the brain suspends the gated call and
    denies it fail-closed if no matching decision ever arrives), `TurnComplete`→`Complete`
    (terminal), `SeamError`→`Failed` (terminal). A status raised at the call or mid-stream
    reuses the same origin split (`status_to_error`, shared with `health`) → `Rpc`/`Connection`;
    an empty `ServerEvent` or a stream that ends before `TurnComplete` → `Protocol`. The
    reply mapping is built with `async-stream`, the request chain with `tokio-stream`.
  - `list_sessions(limit)` / `session_messages(session_id)` (the read-only session views,
    ADR-0021; `src/sessions.rs`) are unary calls to `BrainService.ListSessions` /
    `GetSessionMessages` mapping each reply row to a core `SessionSummary` / `SessionMessage`;
    a non-OK status reuses `status_to_error` → `Rpc`/`Connection` (a store failure is
    `Rpc{code:"Unavailable"}`). Kept in their own module so `client.rs` stays under the line cap.
  - `list_due_reminders()` / `ack_reminder(reminder_id)` (the reminder pull path, ADR-0025;
    `src/reminders.rs`, split for the same reason) are unary calls to
    `BrainService.ListDueReminders` / `AckReminder`, mapping each reply row to a core
    `DueReminder` and the ack reply to its `acked` bool. Same status mapping; nothing here
    special-cases the schedule-free brain, which answers an empty list and `acked=false`
    rather than a status.
  - Every `TransportError::Connection` message folds the error's full `source()` chain
    (e.g. `transport error: tcp connect error: Connection refused (os error 111)`), so
    tonic's opaque `"transport error"` `Display` still names the root cause.
- `body_service(audio: A, token: &str)` (Slice 9, ADR-0023; `src/server.rs`) is the
  brain→body direction: builds the `BodyService` server over an `AudioControl` backend,
  fronted by the seam-token validator. Its pieces:
  - `VolumeService<A: AudioControl>` is the generated `BodyService` trait over an injected
    backend. `get_volume`/`set_volume` map the wire messages onto the port (the level
    clamp lives in `body_core::VolumeChange`, not here); `capture_screen`/`inject_input`
    answer `Status::unimplemented` until their slices (10 / later). No state is held. Volume is
    read from the OS on demand (the one hard rule).
  - `audio_error_to_status(&AudioError) -> Status` is the inverse of
    `client::status_to_error`: `NoEndpoint`→`Unavailable` (transient, like a dead
    backend), `Backend`→`Internal`.
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
Two `#[ignore]`d tests run against a real brain:

```sh
cargo test -p body-rpc --test live -- --ignored
```

Both read `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`, which matches the brain
server's `CORTEX_SEAM_HOST`/`CORTEX_SEAM_PORT` defaults `127.0.0.1`/`50051`) and, when the
live brain is token-protected (ADR-0016), `CORTEX_SEAM_TOKEN`:

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
- `session_reads_round_trip_over_the_live_seam` (Slice 8.7, ADR-0021) seeds one turn over
  the raw `Converse` to persist a session, then reads it back over the typed
  `BrainTransport`: `list_sessions(50)` must return the chat with its derived title (the
  first user message) and a real last-activity timestamp, and `session_messages` the user
  turn + assistant reply in order. Needs only brain + Redis (no GPU).

Being ignored, they never run in CI and never count toward coverage.

**Invariants.**
- Thin adapter: translate types and errors, nothing else; everything crossing the seam
  is declared in `proto/body.proto` first.
- Generated code lives only in `src/_generated/` (never hand-edited), pulled in via the
  `generated` wrapper module whose inner allows scope the clippy exemption; the
  `check-body` coverage run excludes it via `--ignore-filename-regex '/_generated/'`.
  Hand-written code is fully gated: 100% line+region+branch.
- Contract tests exercise a scripted in-process fake `BrainService` over loopback
  (`127.0.0.1:0`) only, which is CI-safe, with no real network. They cover both sides of the
  status-origin split, including brain death after a successful connect (graceful
  fake shutdown → next `health()` must be `Connection`, not `Rpc`); the lazy
  constructor (ADR-0024, covering a healthy round-trip over a lazy channel, construct-then-fail
  against a dead endpoint, bad URI, non-ASCII token); and the confirm
  round-trip (ADR-0022): the fake emits `ConfirmRequest` mid-turn and asserts the
  echoed `ConfirmResponse` arrives on the still-open request stream (approve and
  deny, answered reactively over a channel), plus the half-close of an empty
  decisions stream. The reminder pull (ADR-0025) is covered the same way: two scripted
  rows differing in every flag prove the row mapping (taint included), an ack of the
  deliverable id answers `true` while an unknown id answers `false` (proving the id
  crossed the wire and that "nothing to clear" is an answer, not an error), and a
  scripted store failure maps both calls to `Rpc{code:"Unavailable"}`.
- The `body_service` server (Slice 9) is contract-tested the same way, via a real loopback
  server over a fake `AudioControl`, to 100% line+region+branch: `get_volume`/`set_volume`
  happy paths, both `audio_error_to_status` arms, the `Unimplemented` handlers, and the
  `SeamTokenValidator` pass-through (empty token) plus its accept/reject arms (matching,
  wrong, and missing token).

**Dependencies.** `body-core` (the port), `tonic` + `tonic-prost` + `prost`, plus
`async-stream` (builds the `converse` reply mapping), `tokio-stream` (chains the confirm
decisions onto the request stream, promoted from dev-only in Slice 8.8, ADR-0022) and
`futures-core` (the `Stream` trait); build-dependency `tonic-prost-build` (idle unless
`CORTEX_REGEN_PROTO=1`); dev-only `tokio`.
