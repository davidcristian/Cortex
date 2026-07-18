# brain/packages/body_client (`cortex_body_client`)

**Purpose.** The gRPC client adapter for the core's `BodyGateway` port (ADR-0023). It is the brain's
side of the first **brain→body** seam direction. A thin transport translator: it wraps the
committed `BodyService` stub over a `grpc.aio` channel to the host-native body, so the cortex's
volume tools can read/set host volume behind the unchanged `BodyGateway` port. The typed
`BodyService` client wrapper ADR-0003 decision 5 reserved for Slice 9. No orchestration, no
state (the one hard rule). The composition root owns the channel's lifecycle.

**Public contract** (`__all__` is the API):

- `GrpcBodyGateway(channel, *, token="", capture_timeout_s=10.0)` is a `BodyGateway`.
  - `get_volume() -> VolumeState` calls `BodyService.GetVolume`, maps the wire `VolumeState`
    to the core value.
  - `set_volume(*, level=None, mute=None) -> VolumeState` calls `BodyService.SetVolume` with
    proto **explicit presence** (a `None` field is left unset, so the body sets level, mute, or
    both), and reports the state after.
  - `capture_screen(*, max_edge=0, max_bytes=0) -> ScreenCapture` calls
    `BodyService.CaptureScreen` and maps `ImageBlob` onto the core value, building an
    `ImagePart` (which re-checks the mime, the declared size, and the byte count) and reading
    `captured_at_unix_ms` as an aware UTC datetime. A reply with no blob at all is refused: a
    body that answers OK to a capture it did not take would otherwise read as a screen of
    zeros. A body that leaves `source_width`/`source_height` at their proto3 zeros (an older
    body) reports the image's own size, so nothing tells the model it is looking at a shrunk
    view of nothing.
  - All attach the seam token as `x-cortex-seam-token` metadata when `token` is non-empty
    (built once at construction; ADR-0016, mirrored for this direction), and no metadata when
    empty, which matches the tokenless body server.
- `GrpcBodyGateway.connect(endpoint, *, token="", capture_timeout_s=10.0) -> (GrpcBodyGateway,
  closer)` opens an
  insecure channel to `endpoint` (`host:port`, e.g. `host.docker.internal:50151` from the
  dockerized brain) and returns the adapter plus the coroutine that closes the channel, so the
  root's shutdown path is uniform with the other builders. The channel connects **lazily**, so an
  unreachable body surfaces on the first call, not at connect.
- `MAX_RECEIVE_BYTES = 16 * 1024 * 1024` is the channel's raised
  `grpc.max_receive_message_length`, and the **only** transport limit this repo changes
  (ADR-0029). grpc's own default is 4 MiB, which a legitimate capture can exceed. The limit
  deliberately sits above both the body's 6 MiB ceiling and the brain's own image budget, so a
  reply that breaks the *domain* bound is refused by the domain with a message the cortex can
  read, rather than killed by the transport with one nobody can act on. No other direction on
  either seam carries a payload, and raising a limit with nothing behind it is an untestable
  change.

**Capture is attempted exactly once, with a deadline.** It is the first call on this seam to
carry a `timeout` (`CORTEX_BODY_CAPTURE_TIMEOUT_S`, default 10.0), because a 4K blit plus a
downscale plus a PNG encode is the first that can genuinely park a host thread, and with no
deadline a wedged backend hangs the tool call, which hangs the turn, forever. The volume and
notify calls keep their live-validated no-deadline behaviour. It is also **never retried**,
recorded as a decision rather than built as code: a re-capture photographs a different screen,
possibly after the user switched windows, so it neither reproduces the answer nor leaves the
world unchanged, and it would fire a second host receipt for one user intent.

**Error contract.** Every gRPC failure (the body unreachable, a non-OK status
(`UNAVAILABLE`/`UNAUTHENTICATED`/`INTERNAL`)) is caught as `grpc.aio.AioRpcError` and re-raised
as `BodyGatewayError` with the cause chained (and the status detail in the message). The volume
tools (`cortex_core`) catch it and return an `is_error` result the cortex can recover from. A
dead body is a message, never a turn-killing exception.

**Invariants.**
- Stateless per call; the adapter holds only its stub + prebuilt metadata (the one hard rule).
- Adapter-only: real network I/O lives here, never in the core (AGENTS.md gate 3). Wire types
  are imported only through the `cortex_seam` facade, never `cortex_seam._generated`.
- Fully typed, pyright strict clean; 100% line+branch by standing up a real `grpc.aio` loopback
  server hosting a fake `BodyServiceServicer` (the `test_auth.py` pattern). No live body. Live
  checks against the real Rust body are `integration`-marked (per
  `docs/runbooks/body-volume.md`).

**Dependencies.** cortex-core (the `BodyGateway` port, `VolumeState` value, `BodyGatewayError`),
cortex-seam (the `BodyServiceStub` + volume wire messages + `SEAM_TOKEN_HEADER`), grpcio (the
async channel). The composition root (`cortex_orchestrator.wiring`) builds the channel from
`CORTEX_BODY_ENDPOINT` and injects the shared `CORTEX_SEAM_TOKEN`.
