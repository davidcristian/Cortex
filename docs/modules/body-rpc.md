# body/crates/rpc (`body_rpc`)

**Purpose.** The body's gRPC adapter for the seam ([proto/body.proto](../../proto/body.proto),
the single source of truth): the committed tonic/prost stubs for `cortex.seam.v1` plus
`BrainSeamClient`, the tonic implementation of the `body_core::BrainTransport` port.
Thin translation only. No business logic, no retries (retry policy is a later slice).

**Public contract.**

- `BrainSeamClient` (`Clone` lets clones share the channel; `Debug`).
  - `BrainSeamClient::connect(addr: &str) -> Result<Self, TransportError>` (async)
    dials e.g. `http://127.0.0.1:50051`; an invalid URI or unreachable endpoint maps to
    `TransportError::Connection`.
  - `impl BrainTransport`: `health()` calls `BrainService.Health`; an Ok reply maps to
    `SeamHealth { ready, detail }`. A non-OK gRPC status splits by origin: a status
    tonic *synthesized* from a client-local transport failure (detected by a
    `tonic::transport::Error` in the status's `source()` chain, e.g. the brain died
    after the channel connected) maps to `TransportError::Connection`; a status
    genuinely reported by the brain maps to `TransportError::Rpc { code, message }`
    where `code` is the status-code name (`Internal`, `Unimplemented`, …).
  - `converse(session_id, text)` opens `BrainService.Converse` (`src/converse.rs`), sends
    one `ClientEvent{session_id, user_turn}` then half-closes (one turn per call, ADR-0011),
    and maps each streamed `ServerEvent` to a `TurnEvent`: `TextDelta`→`Delta`,
    `ToolActivity`→`ToolActivity`, `StatusUpdate`→`Status`, `TurnComplete`→`Complete`
    (terminal), `SeamError`→`Failed` (terminal). A status raised at the call or mid-stream
    reuses the same origin split (`status_to_error`, shared with `health`) → `Rpc`/`Connection`;
    an empty `ServerEvent` or a stream that ends before `TurnComplete` → `Protocol`. The
    request stream is built with `async-stream`.
  - Every `TransportError::Connection` message folds the error's full `source()` chain
    (e.g. `transport error: tcp connect error: Connection refused (os error 111)`), so
    tonic's opaque `"transport error"` `Display` still names the root cause.
- `generated` is the codegen for the whole proto package: message types plus
  `brain_service_client::BrainServiceClient`,
  `brain_service_server::{BrainService, BrainServiceServer}` (and the `BodyService`
  counterparts, unused until Slice 9). Generated code: exempt from lint, coverage, and
  the line cap (ADR-0002 decision 4). Public so contract tests and later server wiring
  can drive it directly.

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
server's `CORTEX_SEAM_HOST`/`CORTEX_SEAM_PORT` defaults `127.0.0.1`/`50051`):

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
  fake shutdown → next `health()` must be `Connection`, not `Rpc`).

**Dependencies.** `body-core` (the port), `tonic` + `tonic-prost` + `prost`, plus
`async-stream` (builds the one-turn `converse` request stream) and `futures-core` (the
`Stream` trait); build-dependency `tonic-prost-build` (idle unless `CORTEX_REGEN_PROTO=1`);
dev-only `tokio`, `tokio-stream`.
