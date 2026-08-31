# brain/packages/body_client (`cortex_body_client`)

**Purpose.** The gRPC client adapter for the core's `BodyGateway` port (ADR-0023), the brain's side
of the brain-to-body direction of the wire contract. It is a thin transport translator: it wraps the
committed `BodyService` stub over a `grpc.aio` channel to the host-native body, so the cortex's
volume, notification and capture tools reach the host behind the unchanged `BodyGateway` port. No
orchestration and no state (the one hard rule); the composition root owns the channel's lifetime.

## Public contract

`__all__` is `GrpcBodyGateway`, `kind_of`, `DEFAULT_CAPTURE_TIMEOUT_S`, `DEFAULT_CALL_TIMEOUT_S` and
`MAX_RECEIVE_BYTES`.

- `kind_of(err) -> BodyFailure` classifies one `AioRpcError` into the port's error vocabulary; it is
  the single table every call routes its failures through (see the error contract below).
- `GrpcBodyGateway(channel, *, token="", capture_timeout_s=10.0)` is a `BodyGateway`.
  - `get_volume() -> VolumeState` calls `BodyService.GetVolume` and maps the wire `VolumeState` to
    the core value.
  - `set_volume(*, level=None, mute=None) -> VolumeState` calls `BodyService.SetVolume` with proto
    **explicit presence**, so a `None` field is left unset and the body sets level, mute or both,
    and reports the state afterwards.
  - `capture_screen(*, max_edge=0, max_bytes=0, target=CaptureTarget.DISPLAY) -> ScreenCapture`
    calls `BodyService.CaptureScreen` and maps `ImageBlob` onto the core value, building an
    `ImagePart` (which re-checks the mime type, the declared size and the byte count) and reading
    `captured_at_unix_ms` as an aware UTC datetime. A reply with no blob at all raises instead of
    mapping, because a body that returned OK for a capture it never took would otherwise be read as
    a screen of zeros. A body that leaves `source_width` and `source_height` at their proto3 zeros
    reports the image's own size, so the model is never told it is looking at a downscaled view of a
    zero-sized display.
  - All of them attach the token as `x-cortex-seam-token` metadata when `token` is non-empty, built
    once at construction (ADR-0016, mirrored for this direction), and no metadata when it is empty,
    which matches the tokenless body server.
- `GrpcBodyGateway.connect(endpoint, *, token="", capture_timeout_s=DEFAULT_CAPTURE_TIMEOUT_S, call_timeout_s=DEFAULT_CALL_TIMEOUT_S) -> (GrpcBodyGateway, closer)`
  opens an insecure channel to `endpoint` (`host:port`, for example `host.docker.internal:50151`
  from the dockerized brain) and returns the adapter plus the coroutine that closes the channel, so
  the root's shutdown path is the same shape as the other builders. The channel connects **lazily**,
  so an unreachable body shows up on the first call rather than at connect, and within
  `call_timeout_s` rather than after grpc's own connect backoff.
- `DEFAULT_CAPTURE_TIMEOUT_S = 10.0` and `DEFAULT_CALL_TIMEOUT_S = 5.0` are the two deadlines,
  declared **here** and imported by the orchestrator's `BodyConfig`, which publishes them as
  `CORTEX_BODY_CAPTURE_TIMEOUT_S` and `CORTEX_BODY_CALL_TIMEOUT_S`. This package owns the calls, so
  it owns how long they may take; a settings module with its own `5.0` would be a second default
  that only looks like the first.
- `MAX_RECEIVE_BYTES = 16 * 1024 * 1024` is the channel's raised `grpc.max_receive_message_length`,
  and the **only** transport limit this repo changes (ADR-0029). grpc's own default is 4 MiB, which
  a legitimate capture can exceed. The limit deliberately sits above both the body's 6 MiB ceiling
  and the brain's own image budget, so a reply that breaks the *domain* bound is refused by the
  domain with a message the cortex can read, rather than killed by the transport with one nobody can
  act on. No other direction sends a payload, and raising a limit with nothing behind it is an untestable change.

## Capture bounds

**Both size arguments are also bounds on the reply, verified after receipt** (ADR-0029 decision 7,
which rejects `max_edge` as the only size defence, and which is the core's
`hold_to_the_bounds_asked_for` rather than this adapter's own, since every implementation of the
port owes it): a non-zero `max_edge` rejects a longer declared edge and a non-zero `max_bytes`
rejects more bytes, each naming the number the body broke, because under proto3 an older body
ignores both and answers at full resolution, and `ImagePart`'s own 6 MiB and 8192 px are the domain
ceiling rather than the number this deployment chose. A **zero** asked for the body's own default,
so there is nothing to hold it to and only that ceiling applies. A bound outside uint32 (which the
config's own `ge` and `le` reject at boot) also fails as a `BodyGatewayError`, since the request is
built inside the mapping: this port promises one failure channel, and a bare `ValueError` from the
wire types would kill the turn instead of the capture.

`target` crosses through `_TARGET_TO_WIRE`, the one place the domain enum and the wire enum meet,
written out pair by pair rather than derived from either side's ordering. It is the third thing the
wire cannot guarantee, and the **one the receiver cannot re-verify from the payload**: a cropped
window and a downscaled display are the same blob with the same `source_*` values. The returned
`ScreenCapture` therefore reports the reply's own `resolved_target` and never echoes the requested
one. A body that sets nothing leaves the proto3 zero, which reads as `DISPLAY` and is correct for a
body predating the field; a value this brain does not recognize also reads as `DISPLAY`, both for
that same proto3 reason and because the display a picture came off is the widest accurate
description of it.

## Deadlines

**Every call has a deadline, and the two numbers differ because the calls do** (ADR-0029 decision
12). A capture gets `capture_timeout_s`, the long one, since a 4K blit plus a downscale plus a PNG
encode is real work. `get_volume`, `set_volume` and `notify` get `call_timeout_s`, the short one,
because they are fast whenever they work at all. None of the three is safe to leave unbounded: the
body runs **every** handler on `spawn_blocking` precisely because Core Audio and the toast manager
are COM, which has no async form, and a COM call can block its thread for as long as the audio stack
or the notification service takes (`body/crates/rpc/src/server.rs`). Nothing above this adapter
bounds a tool call, so a wedged endpoint used to hang the turn forever, and a body that is merely
absent cost the caller grpc's own connect backoff. One shared number would either cut off a
legitimate capture or give a volume read a ten-second deadline it can never use.

**An expired deadline is never read as an answer from the body.** grpc-python surfaces a client-side
timeout as `DEADLINE_EXCEEDED`, which `kind_of` classifies `UNREACHABLE`, the kind whose contract is
that no answer arrived at all, whether for want of a route or of time. A test asserts that
classification rather than trusting the library to keep it, because the same assumption was easy to
get wrong on the other direction: a reading of tonic's source suggests its own expiry is a
sourceless `Cancelled`, which that classifier would treat as a reply, while running it shows the
classification is `Connection` instead, which does report the absent answer but sits in that side's
retryable set (ADR-0024 decision 14).

**Capture is attempted exactly once**, and it is **never retried**, recorded as a decision rather
than built as code: a second capture photographs a different screen, possibly after the user
switched windows, so it neither reproduces the answer nor leaves the world unchanged, and it would
produce a second host receipt for one user intent. A deadline is not a retry, so the other three
calls are each bounded by their own argument and nothing here repeats a call.

## Error contract

Every gRPC failure (the body unreachable, a non-OK status) is caught as `grpc.aio.AioRpcError` and
re-raised as `BodyGatewayError` with the cause chained and the status detail in the message, **and
the status classified into a `BodyFailure` kind** by `kind_of` (`failures.py`), which is what lets
the core describe each failure accurately to the user:

| Status | Kind |
| --- | --- |
| `UNAVAILABLE`, `DEADLINE_EXCEEDED` | `UNREACHABLE` |
| `PERMISSION_DENIED`, `UNAUTHENTICATED` | `REFUSED` |
| `UNIMPLEMENTED` | `UNSUPPORTED` |
| `FAILED_PRECONDITION` | `UNREADY` |
| `RESOURCE_EXHAUSTED` | `OVERSIZE` |
| anything else, and every refusal raised here rather than received | `FAULTED` |

`UNAVAILABLE` is reserved for a call that never arrived, which the body-side mapping guarantees by
never using that code (ADR-0023 decision 10); grpc-python cannot tell a locally synthesized status
from a sent one, so the reservation is the only way the distinction survives. The volume and capture
tools in `cortex_core` catch the error and return an `is_error` result the cortex can recover from,
so an unreachable body ends a tool call and never the turn.

## Shared contract

`tests/gateway_contract.py` holds the ten checks every `BodyGateway` implementation owes and
`tests/test_gateway_contract.py` drives them over both: the core's `InMemoryBodyGateway` and this
adapter against a `BodyService` served on loopback, so nothing on the adapter's side is stubbed.
They cover the volume read, the write that touches only the field it was given, the write that
reports the state afterwards, the clamp, the notification that reaches the body with its taint bit,
the decline that answers `False` rather than raising, the capture that reports what the body pointed
at, the capture rejected for breaking the bound it asked for, the capture attempted exactly once,
and the single `BodyGatewayError` every method fails with.

The checks deliberately leave two differences unchecked. The level is a 32-bit float on the wire and
a Python float in the fake, so every level the checks use is exact in both and they compare which
field moved rather than how many bits survived. The clamp also happens in two different places, the
fake applying it itself and the adapter receiving a value the body already clamped, so the check
requires only that a legal state comes back.

## Invariants

- Stateless per call; the adapter holds only its stub and prebuilt metadata (the one hard rule).
- Real network I/O lives here, never in the core. Wire types are imported only through the
  `cortex_seam` facade, never `cortex_seam._generated`.
- Fully typed, pyright strict clean, 100% line and branch against a real `grpc.aio` loopback server hosting a fake `BodyServiceServicer`. No live body. Live checks against the real Rust body
  are `integration`-marked, per [docs/runbooks/body-volume.md](../runbooks/body-volume.md).

**Dependencies.** cortex-core (the `BodyGateway` port, the `VolumeState` value, `BodyGatewayError` and its `BodyFailure` kind), `cortex-seam` (the `BodyServiceStub`, the volume wire messages and `SEAM_TOKEN_HEADER`) and grpcio. The composition root (`cortex_orchestrator.wiring`) builds the
channel from `CORTEX_BODY_ENDPOINT` and injects the shared `CORTEX_SEAM_TOKEN`.
