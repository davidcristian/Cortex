# body/crates/rpc (`body_rpc`)

**Purpose.** The body's gRPC adapter for both directions of the contract in
[proto/body.proto](../../proto/body.proto), the single source of truth: the committed tonic and
prost stubs for `cortex.seam.v1`, `BrainRpcClient` (the tonic implementation of the
`body_core::BrainTransport` port, body to brain), and `body_service` (the `BodyService` server over
the `AudioControl`, `Notify` and `ScreenCapture` ports, brain to body, ADR-0023 and ADR-0025). It
translates types and errors and holds no business logic, and it performs **no retries**: bounded
retry is composed over it by `body_core`'s `RetryingTransport` decorator (ADR-0024), for which
`connect_lazy_with_token` supplies a reconnecting channel.

**The deadline is announced here and enforced in `body_core`.** tonic attaches its
`transport::Error` to the `Status::cancelled` it raises when its own request timeout expires, so
`status_to_error` classifies that expiry `TransportError::Connection`, which is *retryable*: a
deadline configured on the endpoint would be retried against a peer that just proved too slow. The
per-attempt deadline is therefore enforced in the core over the `Sleeper` port and arrives as
`TransportError::Timeout`, outside that set (ADR-0024 decisions 13 and 14). What this adapter puts
on the wire is the `grpc-timeout` header (decision 15), sent once `announcing(plan)` names the plan
the decorator above it enforces. Sending it starts tonic's clock too, so the announced value is
strictly longer than what the core enforces and the retryable clock never fires first.

## The client

`BrainRpcClient` holds the channel, the token and optionally the `RetryPlan` it announces from.
`Clone` lets clones share the channel. `Debug` is hand-written and prints the token's *presence* as
`<redacted>`, and `tests/client.rs` asserts that a configured token cannot reach a `{:?}`. The
generated client is built **per call** (`RpcCall`, `src/call.rs`), which is the only way a per-call
value reaches an interceptor that is otherwise built once per connection.

- `BrainRpcClient::connect(addr: &str) -> Result<Self, TransportError>` (async) dials, for example,
  `http://127.0.0.1:50051` and sends no token; an invalid URI or unreachable endpoint maps to
  `TransportError::Connection`.
- `BrainRpcClient::connect_with_token(addr, token: Option<&str>)` (async, ADR-0016) is the same but
  attaches `token` as `x-cortex-seam-token` metadata on **every** call when `Some`, which is what a
  `CORTEX_SEAM_TOKEN`-protected brain requires. A token that is not valid ASCII metadata maps to
  `TransportError::Connection` before any dial; a wrong or missing one arrives as
  `TransportError::Rpc { code: "Unauthenticated", .. }`.
- `BrainRpcClient::connect_lazy_with_token(addr, token)` (**sync**, ADR-0024) is the same over a
  *lazy* channel (`Channel::connect_lazy`): construction never dials, so it fails only on a bad URI
  or a non-ASCII token, and each RPC establishes the connection on demand. This is the channel
  `RetryingTransport` retries over: a call against a briefly down brain fails `Connection`, the
  decorator backs off, and tonic reconnects.
- `BrainRpcClient::announcing(plan: RetryPlan) -> Self` turns on the `grpc-timeout` header: every
  unary call then announces `plan.announced_deadline_for(method)`, which is that method's enforced
  deadline plus `ANNOUNCED_DEADLINE_GRACE_MS` (250 ms). `Converse` announces nothing, the plan
  giving a turn no deadline, and a client nobody called this on announces nothing at all. `plan`
  must be the **same plan the decorator above the client enforces**: `seam::connect()` reads
  `plan_from_env()` once and hands the one value to both, which makes the ordering between the two
  clocks structural rather than a convention. An announcement past
  `MAX_ANNOUNCED_DEADLINE_MS` (99999999 ms, about 27.8 hours) is dropped rather than clamped or
  rounded, a shorter announcement being the one thing that would lose the race on purpose. That
  bound is the top of `grpc-timeout`'s millisecond step rather than the 8-digit ceiling tonic's
  encoder panics on, because one step above it the truncation is four times the grace and tonic's
  clock would then run **under** the core's bound (ADR-0024 decision 16).

`impl BrainTransport` maps each method onto its RPC:

- `health()` calls `BrainService.Health`; an Ok reply maps to `RpcHealth { ready, detail, notes }`,
  each `HealthNote` becoming its sentence. A
  non-OK status splits by origin: one tonic *synthesized* from a client-local transport failure,
  detected by a `tonic::transport::Error` on the status's `source()` chain, maps to
  `TransportError::Connection`, and one the brain really sent maps to
  `TransportError::Rpc { code, message }`.
- `converse(session_id, text, decisions)` opens `BrainService.Converse` (`src/converse.rs`, one turn
  per call, ADR-0011): the request stream is `once(ClientEvent{session_id, user_turn})` chained with
  one `confirm_response` per `ConfirmDecision` from the caller's stream (ADR-0022), half-closing
  when that stream ends. Each `ServerEvent` maps to its `TurnEvent` of the same name, with
  `TurnComplete` becoming `Complete` and `SeamError` becoming `Failed`, the two terminal ones. A
  status raised at the call or mid-stream reuses the origin split; an empty `ServerEvent` or a
  stream that ends before `TurnComplete` becomes `Protocol`. The reply mapping is built with
  `async-stream` and the request chain with `tokio-stream`.
- `list_sessions(limit)` and `session_messages(session_id)` (ADR-0021, `src/sessions.rs`) are unary
  calls mapping each reply row to a core `SessionSummary` (its `hoisted` flag included) or
  `SessionMessage`. A non-OK status maps through the `RpcCall` the client hands in, so it becomes
  `Rpc`, `Connection` or `Timeout`.
- `rename_session(session_id, title)`, `delete_session(session_id)` and
  `set_session_hoisted(session_id, hoisted)` (ADR-0021 decisions 10 to 12, same module) are unary
  calls whose replies are bare acknowledgements, so success maps to `()`.
- `get_preferences()` and `set_preference(key, value)` (ADR-0032, `src/preferences.rs`) map the
  reply rows to plain `(key, value)` tuples and the write's acknowledgement to `()`. Nothing
  special-cases a brain with no preference store, which answers an empty record and accepts a write
  silently.
- `list_due_reminders()` and `ack_reminder(reminder_id, fired_at_unix_ms)` (ADR-0025,
  `src/reminders.rs`) map each reply row to a core `DueReminder`, put the fire's stamp on
  `AckReminderRequest.fired_at_unix_ms`, and map the acknowledgement to its `acked` bool. Nothing
  special-cases a brain with no schedule backend, which answers an empty list and `acked=false`.
- Every `TransportError::Connection` message folds the error's full `source()` chain (for example
  `transport error: tcp connect error: Connection refused (os error 111)`), so tonic's opaque
  `"transport error"` `Display` still names the root cause.

`status_to_error(status: &Status) -> TransportError` (`src/status.rs`) is that mapping as a
function: a status with a `tonic::transport::Error` anywhere on its `source()` chain is
`Connection`, anything else is `Rpc`. It is public only so the contract suite can assert it against
statuses tonic really produces. Its crate-internal twin
`announced_status_to_error(status, announced)` is what a call that announced a deadline maps
through, and it adds one answer: a **brain-sent** `DEADLINE_EXCEEDED` becomes
`TransportError::Timeout { after }` naming the announcement, since the body's own expired clock and
the brain's report of the same deadline mean one thing above the adapter. tonic's local expiry is
caught by the transport-source case first, and a `DEADLINE_EXCEEDED` on a call that announced
nothing stays `Rpc`. All three are terminal.

## The server

`body_service(audio, notifier, token)` (`src/server.rs`, ADR-0023 and ADR-0025) is the brain to body
direction: it builds the `BodyService` server over an `AudioControl`, a `Notify` and a
`ScreenCapture` backend, behind the token validator.

- `OsService<A: AudioControl, N: Notify, S: ScreenCapture>` implements the generated `BodyService`
  trait over the injected backends. `get_volume` and `set_volume` map the wire messages onto the
  volume port, the level clamp living in `body_core::VolumeChange`; `notify` builds a
  `body_core::Notification`, which is where the inert-text rule is applied, and answers
  `NotifyReply { shown }`; `capture_screen` delegates to `src/screen.rs`; `inject_input` answers
  `Status::unimplemented`. No state is held: a capture's pixels live only for the call that returns
  them.
- `screen::capture(...)` (ADR-0029) owns the capture translation. It resolves the wire's `max_edge`,
  `max_bytes` and `target` into a `body_core::CaptureRequest`, then runs the blit, the pure
  `Capture::from_bgra` policy, the clock read and the receipt inside **one** `off_worker` hop, and
  maps the `Capture` onto `ImageBlob` (`source_width` and `source_height` staying the **display's**
  even when the picture is one window). `resolve_target` is where proto3's unknown-enum rule
  applies: a value this body does not name reads as `CaptureTarget::Display`. `encoded_target` fills
  the reply's `resolved_target` from `Capture::covers_display()`, the same predicate the receipt is
  picked by, so the sentence the user is shown and the one the brain shows the model cannot
  disagree. The reply's `target_width` and `target_height` are the `Capture`'s own, the size of
  the part of the display it shows. The receipt is **best effort**, the pixels having been read by
  the time it runs, and `receipts`, the host's `CORTEX_HOST_CAPTURE_NOTIFY` switch, turns it off.
- Error mapping is one code per variant: `NoDisplay` and `NoTarget` to `FailedPrecondition` (host
  state, which works again the moment a window is on screen), `Disabled` to `PermissionDenied`,
  `Backend` to `Internal`, `TooLarge` to `ResourceExhausted`. `audio_error_to_status` maps
  `NoEndpoint` to `FailedPrecondition` and `Backend` to `Internal`, and `notify_error_to_status`
  splits the same way; each variant keeps its `body_core` name, which is about the host rather than
  about gRPC. A declined notification is **not** an error: `shown=false` is in the reply, because
  the brain reads it as "push did not happen" exactly like a status. **Nothing this server answers
  is `Unavailable`**, the rule the brain's classifier rests on: tonic synthesizes that code
  client-side for a channel that cannot connect, so leaving it unused makes it mean exactly that the
  call never arrived (ADR-0023 decision 10).
- `off_worker(call, to_status)` is where every handler's **one synchronous OS call** actually runs:
  `tokio::task::spawn_blocking`, not inline. Both OS ports are synchronous because the OS is (Core
  Audio and the toast manager are COM), and a COM call parks its thread for as long as the audio
  stack or the notification service takes; inline, that would park an **async worker** of the
  runtime the overlay's own calls share. The backends sit behind an `Arc` inside `OsService` purely
  so a handler can lend one to the blocking thread, and each resolves its own COM interface *inside*
  the closure, so nothing COM-shaped crosses a thread. A backend that panics arrives as a join
  failure and answers `Internal`, letting the panic escape having cost the brain the whole
  connection.
- `RpcTokenValidator` (`src/auth.rs`) is a tonic server `Interceptor`, the mirror of the client one
  (ADR-0016). It rejects any call without a matching `x-cortex-seam-token` with `UNAUTHENTICATED`
  before any handler runs, on a constant-time compare. It is **always attached** but is a
  **pass-through when the configured token is empty**. It is deliberately not `Debug`: it holds the
  shared secret.
`generated` is the code generated for the whole proto package: the message types plus the client and
server types for both services. It is exempt from lint, coverage and the line cap (ADR-0002 decision
4), and public so contract tests and server wiring can drive it directly.

## Regenerating the stubs

Stubs are committed under `src/_generated/`, so normal builds and CI run **no** code generation and
never need `protoc`. After editing the proto (extend, never renumber, v0 field numbers being
frozen):

```sh
cd body && CORTEX_REGEN_PROTO=1 cargo build -p body-rpc
```

`build.rs` then runs `tonic-prost-build` (`protoc` 35.x on PATH) and rewrites
`src/_generated/cortex.seam.v1.rs`. The output is deterministic for a fixed toolchain, so
regenerating with an unchanged proto must leave `git diff` empty.

**Live checks** are the `#[ignore]`d tests in `tests/live.rs`, run by `just rpc-health`. The list
below names every one of them and nothing else, which `scripts/rostercheck.py` enforces (ADR-0044
decision 7). No count is given, because a tally beside a list goes stale first. Each bullet says
what its check needs, and not all of them need a brain:

```sh
cargo test -p body-rpc --test live -- --ignored
```

They read `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`, which matches the brain server's
`CORTEX_SEAM_HOST` and `CORTEX_SEAM_PORT` defaults `127.0.0.1`/`50051`) and `CORTEX_SEAM_TOKEN`,
which is **a precondition rather than an option**: one check proves a wrong token is refused, and a
brain serving without one accepts every token, so `just rpc-health` refuses to start without the
variable (ADR-0016 decision 8).

- `brain_reports_ready_over_the_live_rpc` calls `Health` through `BrainRpcClient` and asserts
  `ready`.
- `converse_round_trips_one_turn_over_the_live_rpc` drives the raw generated `BrainServiceClient`,
  sends one `ClientEvent{session_id, user_turn}` with a session id unique per run, collects
  `TextDelta`s until `TurnComplete`, and asserts that at least one delta arrived and that
  `TurnComplete` has a non-empty `turn_id`.
- `the_link_probe_classifies_the_live_brain_and_a_peer_that_cannot_serve` (ADR-0011 decision 8) runs
  `body_core::probe_link` over a **lazy** client: the live brain must classify `Ready` with a
  non-empty detail, and a peer that accepts the dial and drops it must classify `Down` with the dial
  failure rather than raising. The peer is the suite's own listener rather than a closed port, this
  client having no deadline and a closed port not being refused everywhere.
- `session_reads_round_trip_over_the_live_rpc` (ADR-0021) seeds one turn over the raw `Converse`,
  then reads it back over the typed `BrainTransport`: `list_sessions(50)` must return the chat with
  its derived title and a real timestamp, and `session_messages` both messages in order. It needs
  only the brain and Redis, no GPU.
- `the_ack_write_is_answered_once_against_the_live_brain` (ADR-0025) shows the refusal to retry on
  the wire: `ack_reminder` of an unknown id answers `false` and costs one round trip.
- `a_rejected_rpc_token_is_answered_at_once_and_never_retried` (ADR-0016) dials with a deliberately
  wrong token: the answer must be `Degraded`, the detail must open `Unauthenticated`, and it must
  arrive with no wait spent. It needs a brain serving with a token.
- `the_probe_budget_bounds_a_down_result_against_a_dead_address` (ADR-0024) probes
  `http://127.0.0.1:1` through `RetryingTransport` on a real `Sleeper` and asserts the answer is
  `Down` inside the budget. The bound is all it asserts: what a dial to a closed port costs is the
  host's fact.
- `the_probe_trims_its_attempts_where_a_read_spends_them_all` (ADR-0024 decision 24) is the one
  check here that needs no brain: against a loopback peer of its own that accepts each dial and
  drops it, **counting dials on the wire**, the probe must spend exactly 2 attempts with one real
  400 ms wait between them while the same schedule leaves the read all 5.

Being ignored, they never run in CI and never count toward coverage.

## Invariants

- A thin adapter: translate types and errors, nothing else. Everything crossing to the brain is
  declared in `proto/body.proto` first.
- Generated code lives only in `src/_generated/` and is never hand-edited. It is pulled in through
  the `generated` wrapper module, whose inner allows scope the clippy exemption, and the
  `check-body` coverage run excludes it with `--ignore-filename-regex '/_generated/'`. Hand-written
  code is covered 100% line, region and branch.
- The announced deadline is contract-tested off the **request the fake brain received**, since no
  reply echoes a header: the fake records every call's `grpc-timeout`, and the checks assert the
  per-method value, silence from a client with no plan and from every turn, silence rather than a
  panic for a deadline the header cannot express, silence for one it can express only in whole
  seconds with a header still sent for the last bound below that step, that a hanging brain still
  ends as `Timeout`, and that a brain-sent `DEADLINE_EXCEEDED` arrives as the same `Timeout`.
- Contract tests exercise a scripted in-process fake `BrainService` over loopback (`127.0.0.1:0`)
  only, which is CI-safe with no real network. They cover both sides of the status-origin split,
  including brain death after a successful connect, the lazy constructor, the confirmation round
  trip (ADR-0022) for approve, deny, a `ConfirmResolved` the caller never answers staying
  non-terminal and an empty decisions stream half-closing, and the reminder pull (ADR-0025). The
  `body_service` server is covered the same way, through a real loopback server over a fake
  `AudioControl` and a fake `Notify`: the volume paths, both `audio_error_to_status` cases, the
  `Unimplemented` handlers, the `RpcTokenValidator` pass-through and its accept and reject cases, a
  shown toast whose recorded `Notification` proves the wire text reached the backend already inert
  and badged, a declined one answering `shown=false`, and three `off_worker` cases, where both fakes
  record **which thread** each call ran on (a backend reporting a thread other than the
  current-thread test runtime's is the proof the call left the async worker) and a panicking backend
  answers `Internal` twice over the *same* channel, proving the connection survives it.
- Every one of those runs twice per check, alphabetically under the stable `cargo test` and permuted
  under the nightly coverage step's fixed shuffle seed; the rule for adding a test to the biggest
  binaries in this workspace is in [body-core.md](body-core.md).

**Dependencies.** `body-core` (the port), `tonic`, `tonic-prost` and `prost`, plus `async-stream`
(the `converse` reply mapping), `tokio-stream` (chaining the confirmation decisions onto the request
stream), `futures-core` (the `Stream` trait) and `tokio` with `rt` only (`spawn_blocking` for the
synchronous OS calls). Build dependency: `tonic-prost-build`, idle unless `CORTEX_REGEN_PROTO=1`.
Dev-only `tokio` features: `macros`, `net`, `rt-multi-thread` and `sync`.
