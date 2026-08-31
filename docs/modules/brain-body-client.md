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
    `captured_at_unix_ms` as an aware UTC datetime. A reply with no blob at all raises instead
    of mapping, because a body that returns OK for a capture it never took would otherwise be
    read as a screen of zeros. A body that leaves `source_width`/`source_height` at their proto3
    zeros (an older body) reports the image's own size, so the model is never told it is looking
    at a downscaled view of a zero-sized display.
    **Both arguments are also bounds on the reply, verified after receipt**
    (ADR-0029 decision 7, which rejects `max_edge` as the sole size defense, and which is the
    core's `hold_to_the_bounds_asked_for` rather than this adapter's own, since every
    implementation of the port owes it): a non-zero
    `max_edge` rejects a longer declared edge and a non-zero `max_bytes` rejects more bytes,
    each naming the number the body broke, because under proto3 an older body ignores both and
    answers full resolution, and `ImagePart`'s own 6 MiB / 8192 px are the domain ceiling rather
    than the number this deployment chose. A **zero** asked for the body's own default, so there
    is nothing to hold it to and only that ceiling applies. A bound outside uint32 (which the
    config's own `ge`/`le` reject at boot) fails as a `BodyGatewayError` too, since the request
    is built inside the mapping: this port promises one failure channel, and a bare `ValueError`
    from the wire types would kill the turn instead of the capture.
    `target` crosses through `_TARGET_TO_WIRE`, the one place the domain enum and the wire enum
    meet, spelled out pair by pair rather than derived from either side's ordering. It is the
    third thing the wire cannot guarantee, and the **one the receiver cannot re-verify from the
    payload**: a cropped window and a downscaled display are the same blob carrying the same
    `source_*` values. The returned `ScreenCapture` therefore reports the reply's own
    `resolved_target` and never echoes the requested one. A body that sets nothing leaves the
    proto3 zero, which reads as `DISPLAY` and is correct for a body predating the field; a value
    this brain does not recognize also reads as `DISPLAY`, both for that same proto3 reason and
    because the display a picture came off is the widest accurate description of it.
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
`call_timeout_s`, the short one, because they are fast whenever they work at all. None of the
three is safe to leave unbounded: the body runs **every** handler on `spawn_blocking` precisely
because Core Audio and the toast manager are COM, which has no async form, and its own
`off_worker` doc says a COM call can block its thread for as long as the audio stack or the
notification service takes (`body/crates/rpc/src/server.rs`). Nothing above this adapter bounds a
tool call, so a wedged endpoint used to hang the turn forever, and a body that is merely absent
cost the caller grpc's own connect backoff. One shared number would either cut off a legitimate
capture or give a volume read a ten-second deadline it can never use.

**An expired deadline is never read as an answer from the body.** grpc-python surfaces a
client-side timeout as `DEADLINE_EXCEEDED`, which `kind_of` classifies `UNREACHABLE`, the kind
whose contract is "no answer arrived at all, whether for want of a route or of time". A test pins
that classification rather than trusting the library to keep it, because the same assumption was
already wrong on the other direction of this seam: tonic's own expiry was *recorded* as a
sourceless `Cancelled`, which that classifier would have treated as a reply, on a reading of
tonic's source. Running it showed the classification is `Connection` instead, which does report
the absent answer but sits in that side's retryable set (ADR-0024's deadline addendum and its
correction). Only running the code found the error.

**Capture is attempted exactly once**, and it is **never retried**, recorded as a decision rather
than built as code: a re-capture photographs a different screen, possibly after the user switched
windows, so it neither reproduces the answer nor leaves the world unchanged, and it would fire a
second host receipt for one user intent. A deadline is not a retry, so the other three calls are
each bounded by their own argument and nothing here repeats a call.

**Error contract.** Every gRPC failure (the body unreachable, a non-OK status) is caught as
`grpc.aio.AioRpcError` and re-raised as `BodyGatewayError` with the cause chained (and the status
detail in the message) **and the status classified into a `BodyFailure` kind** by `kind_of`
(`failures.py`), which is what lets the core describe each failure accurately to the user. The
table:

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
result the cortex can recover from, so an unreachable body ends a tool call and never the turn.

**Shared contract.** `tests/gateway_contract.py` holds the ten checks every `BodyGateway`
implementation owes and `tests/test_gateway_contract.py` drives them over both: the core's
`InMemoryBodyGateway` and this adapter against a `BodyService` served on loopback, so nothing on
the adapter's side is stubbed. They cover the volume read, the write that touches only the field
it was given, the write that reports the state after it, the clamp, the notification that reaches
the body with its taint bit, the decline that answers `False` rather than raising, the capture
that reports what the body pointed at, the capture rejected for breaking the bound it asked for,
the capture attempted exactly once, and the single `BodyGatewayError` every verb fails with.

The checks deliberately leave two divergences unpinned. The level is a 32-bit float on the wire
and a Python float in the fake, so every level the checks use is exact in both and the checks
compare which field moved rather than how many bits survived. The clamp also happens in two
different places, the fake applying it itself and the adapter receiving a value the body already
clamped, so the check requires only that a legal state comes back.

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
