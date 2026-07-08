# brain/packages/body_client (`cortex_body_client`)

**Purpose.** The gRPC client adapter for the core's `BodyGateway` port (ADR-0023). It is the brain's
side of the first **brain→body** seam direction. A thin transport translator: it wraps the
committed `BodyService` stub over a `grpc.aio` channel to the host-native body, so the cortex's
volume tools can read/set host volume behind the unchanged `BodyGateway` port. The typed
`BodyService` client wrapper ADR-0003 decision 5 reserved for Slice 9. No orchestration, no
state (the one hard rule). The composition root owns the channel's lifecycle.

**Public contract** (`__all__` is the API):

- `GrpcBodyGateway(channel: grpc.aio.Channel, *, token: str = "")` is a `BodyGateway`.
  - `get_volume() -> VolumeState` calls `BodyService.GetVolume`, maps the wire `VolumeState`
    to the core value.
  - `set_volume(*, level=None, mute=None) -> VolumeState` calls `BodyService.SetVolume` with
    proto **explicit presence** (a `None` field is left unset, so the body sets level, mute, or
    both), and reports the state after.
  - Both attach the seam token as `x-cortex-seam-token` metadata when `token` is non-empty
    (built once at construction; ADR-0016, mirrored for this direction), and no metadata when
    empty, which matches the tokenless body server.
- `GrpcBodyGateway.connect(endpoint, *, token="") -> (GrpcBodyGateway, closer)` opens an
  insecure channel to `endpoint` (`host:port`, e.g. `host.docker.internal:50151` from the
  dockerized brain) and returns the adapter plus the coroutine that closes the channel, so the
  root's shutdown path is uniform with the other builders. The channel connects **lazily**, so an
  unreachable body surfaces on the first call, not at connect.

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
