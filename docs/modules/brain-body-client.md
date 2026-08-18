# brain/packages/body_client (`cortex_body_client`)

**Purpose.** The gRPC client adapter for the core's `BodyGateway` port (ADR-0023). It is the brain's
side of the first **brain→body** seam direction. A thin transport translator: it wraps the
committed `BodyService` stub over a `grpc.aio` channel to the host-native body, so the cortex's
volume tools can read/set host volume behind the unchanged `BodyGateway` port. The typed
`BodyService` client wrapper ADR-0003 decision 5 reserved for Slice 9. No orchestration, no
state (the one hard rule). The composition root owns the channel's lifecycle.

**Public contract** (`__all__` is the API):

- `kind_of(err) -> BodyFailure` classifies one `AioRpcError` into the port's error currency; it
  is the single table every call routes its failures through (see the error contract below).
- `GrpcBodyGateway(channel, *, token="", capture_timeout_s=10.0)` is a `BodyGateway`.
  - `get_volume() -> VolumeState` calls `BodyService.GetVolume`, maps the wire `VolumeState`
    to the core value.
  - `set_volume(*, level=None, mute=None) -> VolumeState` calls `BodyService.SetVolume` with
    proto **explicit presence** (a `None` field is left unset, so the body sets level, mute, or
    both), and reports the state after.
  - `capture_screen(*, max_edge=0, max_bytes=0, target=CaptureTarget.DISPLAY) -> ScreenCapture`
    calls `BodyService.CaptureScreen` and maps `ImageBlob` onto the core value, building an
    `ImagePart` (which re-checks the mime, the declared size, and the byte count) and reading
    `captured_at_unix_ms` as an aware UTC datetime. A reply with no blob at all is refused: a
    body that answers OK to a capture it did not take would otherwise read as a screen of
    zeros. A body that leaves `source_width`/`source_height` at their proto3 zeros (an older
    body) reports the image's own size, so nothing tells the model it is looking at a shrunk
    view of nothing. **Both arguments are also bounds on the reply, verified after receipt**
    (ADR-0029 decision 7, which rejects `max_edge` as the sole size defense, and which is the
    core's `hold_to_the_bounds_asked_for` rather than this adapter's own, since every
    implementation of the port owes it): a non-zero
    `max_edge` refuses a longer declared edge and a non-zero `max_bytes` refuses more bytes,
    each naming the number the body broke, because under proto3 an older body ignores both and
    answers full resolution, and `ImagePart`'s own 6 MiB / 8192 px are the domain ceiling rather
    than the number this deployment chose. A **zero** asked for the body's own default, so there
    is nothing to hold it to and only that ceiling applies. A bound outside uint32 (which the
    config's own `ge`/`le` refuse at boot) fails as a `BodyGatewayError` too, since the request
    is built inside the mapping: this port promises one failure channel, and a bare `ValueError`
    from the wire types would kill the turn instead of the capture.
    `target` crosses through `_TARGET_TO_WIRE`, the one place the domain enum and the wire enum
    meet, spelled out pair by pair rather than derived from either side's ordering. It is the
    third thing the wire cannot guarantee and the **one the receiver cannot re-verify from the
    payload**, a crop and a shrunk screen being the same blob with the same `source_*`, so the
    reply's own `resolved_target` is what the returned `ScreenCapture` reports and the ask is
    never echoed. A body that sets nothing leaves the proto3 zero, which reads as `DISPLAY` and
    is the truth about a body predating the field; a value this brain does not know reads as
    `DISPLAY` too, for proto3's own reason and because the screen a picture came off is the
    honest thing to say about it.
  - All attach the seam token as `x-cortex-seam-token` metadata when `token` is non-empty
    (built once at construction; ADR-0016, mirrored for this direction), and no metadata when
    empty, which matches the tokenless body server.
- `GrpcBodyGateway.connect(endpoint, *, token="", capture_timeout_s=DEFAULT_CAPTURE_TIMEOUT_S,
  call_timeout_s=DEFAULT_CALL_TIMEOUT_S) -> (GrpcBodyGateway, closer)` opens an
  insecure channel to `endpoint` (`host:port`, e.g. `host.docker.internal:50151` from the
  dockerized brain) and returns the adapter plus the coroutine that closes the channel, so the
  root's shutdown path is uniform with the other builders. The channel connects **lazily**, so an
  unreachable body surfaces on the first call, not at connect, and within `call_timeout_s` rather
  than after grpc's own connect backoff.
- `DEFAULT_CAPTURE_TIMEOUT_S = 10.0` and `DEFAULT_CALL_TIMEOUT_S = 5.0` are the two deadlines,
  declared **here** and imported by the orchestrator's `BodyConfig`, which publishes them as
  `CORTEX_BODY_CAPTURE_TIMEOUT_S` and `CORTEX_BODY_CALL_TIMEOUT_S`. This package owns the calls,
  so it owns how long they may take; a settings module spelling its own `5.0` would be a second
  default that only looks like the first.
- `MAX_RECEIVE_BYTES = 16 * 1024 * 1024` is the channel's raised
  `grpc.max_receive_message_length`, and the **only** transport limit this repo changes
  (ADR-0029). grpc's own default is 4 MiB, which a legitimate capture can exceed. The limit
  deliberately sits above both the body's 6 MiB ceiling and the brain's own image budget, so a
  reply that breaks the *domain* bound is refused by the domain with a message the cortex can
  read, rather than killed by the transport with one nobody can act on. No other direction on
  either seam carries a payload, and raising a limit with nothing behind it is an untestable
  change.

**Every call carries a deadline, and the two numbers differ because the calls do** (ADR-0029's
uniform-deadline addendum). A capture gets `capture_timeout_s`, the long one, since a 4K blit plus
a downscale plus a PNG encode is real work. `get_volume`, `set_volume` and `notify` get
`call_timeout_s`, the short one, because they are fast when they work at all. What they are not is
safe to leave unbounded: the body runs **every** handler on `spawn_blocking` precisely because
Core Audio and the toast manager are COM, which has no async form, and its own `off_worker` doc
says a COM call can park its thread for as long as the audio stack or the notification service
takes (`body/crates/rpc/src/server.rs`). Nothing above this adapter bounds a tool call, so a
wedged endpoint used to hang the turn forever, and a body that is merely absent cost the caller
grpc's own connect backoff. Folding both onto one number would either end a legitimate capture or
hand a volume read ten seconds of patience it can never spend.

**An expired deadline is never read as an answer from the body.** grpc-python surfaces a
client-side timeout as `DEADLINE_EXCEEDED`, which `kind_of` classifies `UNREACHABLE`, the kind
whose contract is "no answer arrived at all, whether for want of a route or of time". That is
the honest reading and it is pinned by test rather than inherited from the library, which is the
lesson the other direction of this seam learned the hard way: tonic's own expiry was *recorded*
as a sourceless `Cancelled` its classifier would read as a reply, on a reading of tonic's source,
and running it showed the classification is `Connection` instead, honest about the absent answer
but sitting in that side's retryable set (ADR-0024's deadline addendum and its correction). The
claim was wrong and the correction was found only by running it.

**Capture is attempted exactly once**, and it is **never retried**, recorded as a decision rather
than built as code: a re-capture photographs a different screen, possibly after the user switched
windows, so it neither reproduces the answer nor leaves the world unchanged, and it would fire a
second host receipt for one user intent. Bounding is not repeating, though, so the other three
calls are bounded on their own argument and nothing here retries anything.

**Error contract.** Every gRPC failure (the body unreachable, a non-OK status) is caught as
`grpc.aio.AioRpcError` and re-raised as `BodyGatewayError` with the cause chained (and the status
detail in the message) **and the status classified into a `BodyFailure` kind** by `kind_of`
(`failures.py`), which is the whole reason the core can word a refusal as a refusal. The table:

| Status | Kind |
| --- | --- |
| `UNAVAILABLE`, `DEADLINE_EXCEEDED` | `UNREACHABLE` |
| `PERMISSION_DENIED`, `UNAUTHENTICATED` | `REFUSED` |
| `UNIMPLEMENTED` | `UNSUPPORTED` |
| `FAILED_PRECONDITION` | `UNREADY` |
| `RESOURCE_EXHAUSTED` | `OVERSIZE` |
| anything else, and every refusal raised here rather than received | `FAULTED` |

`UNAVAILABLE` is reserved for a call that never arrived, which is what the body-side mapping
guarantees by never spending that code (ADR-0023's 2026-08-08 addendum); grpc-python cannot tell
a locally synthesized status from a sent one, so the reservation is the only way the distinction
survives. The volume and capture tools (`cortex_core`) catch the error and return an `is_error`
result the cortex can recover from. A dead body is a message, never a turn-killing exception.

**Shared contract.** `tests/gateway_contract.py` holds the ten checks every `BodyGateway`
implementation owes and `tests/test_gateway_contract.py` drives them over both: the core's
`InMemoryBodyGateway` and this adapter against a `BodyService` served on loopback, so nothing on
the adapter's side is stubbed. They cover the volume read, the write that touches only the field
it was given, the write that reports the state after it, the clamp, the notification that reaches
the body with its taint bit, the decline that answers `False` rather than raising, the capture
that reports what the body pointed at, the capture refused for breaking the bound it asked for,
the capture attempted exactly once, and the single `BodyGatewayError` every verb fails with.

Two divergences the list deliberately stays above. The level is a 32-bit float on the wire and a
Python one in the fake, so every level the checks use is exact in both and the checks are about
which field moved rather than how many bits survived. And the clamp happens in different places,
the fake doing it where it stands and the adapter's answer arriving already clamped by the body,
which is why the check asks only that a legal state comes back.

**Invariants.**
- Stateless per call; the adapter holds only its stub + prebuilt metadata (the one hard rule).
- Adapter-only: real network I/O lives here, never in the core (AGENTS.md gate 3). Wire types
  are imported only through the `cortex_seam` facade, never `cortex_seam._generated`.
- Fully typed, pyright strict clean; 100% line+branch by standing up a real `grpc.aio` loopback
  server hosting a fake `BodyServiceServicer` (the `test_auth.py` pattern). No live body. Live
  checks against the real Rust body are `integration`-marked (per
  `docs/runbooks/body-volume.md`).

**Dependencies.** cortex-core (the `BodyGateway` port, `VolumeState` value, `BodyGatewayError`
and its `BodyFailure` kind),
cortex-seam (the `BodyServiceStub` + volume wire messages + `SEAM_TOKEN_HEADER`), grpcio (the
async channel). The composition root (`cortex_orchestrator.wiring`) builds the channel from
`CORTEX_BODY_ENDPOINT` and injects the shared `CORTEX_SEAM_TOKEN`.
