# `brain/packages/seam` (`cortex_seam`)

**Purpose.** The brain's side of the gRPC contract between body and brain: the committed wire code
generated from [proto/body.proto](../../proto/body.proto), plus a thin typed facade. Every brain
package imports wire names from `cortex_seam` and never from `cortex_seam._generated` directly.

## Public contract

`__all__` is the API. It re-exports every proto message class, both services' generated types, and
one constant.

- **The turn stream**: `ClientEvent`, `UserTurn`, `Cancel`, `ServerEvent`, `TextDelta`,
  `ToolActivity`, `ToolOutcome`, `StatusUpdate`, `TurnComplete` and `SeamError`, plus the
  confirmation exchange for a tool that needs approval and the brain-side end of an unanswered one,
  `ConfirmRequest`, `ConfirmResponse` and `ConfirmResolved` (ADR-0022).
- **Health**: `HealthRequest` and `HealthReply`.
- **The session catalog** (ADR-0021): `ListSessionsRequest`, `ListSessionsReply`, `SessionSummary`
  (which has a `pinned` bool, ADR-0021 decision 12), `GetSessionMessagesRequest`,
  `GetSessionMessagesReply` and `SessionMessage` are the read-only views;
  `RenameSessionRequest`/`RenameSessionReply`, `DeleteSessionRequest`/`DeleteSessionReply` (the
  destructive write, which hard-deletes a chat and cascades to its private memories) and
  `SetSessionPinnedRequest`/`SetSessionPinnedReply` are the three user-only writes on it (ADR-0021
  decisions 10 to 12).
- **Reminders** (ADR-0025): `ListDueRemindersRequest`, `ListDueRemindersReply`, `DueReminder`,
  `AckReminderRequest` and `AckReminderReply`.
- **Preferences** (ADR-0032): `GetPreferencesRequest`, `GetPreferencesReply`, `Preference`,
  `SetPreferenceRequest` and `SetPreferenceReply`.
- **Screen capture** (ADR-0029): `CaptureScreenRequest` has `max_edge` and `max_bytes`, both proto3
  hints the body clamps and the brain re-verifies on receipt, plus `target`. `CaptureTarget` is
  `CAPTURE_TARGET_DISPLAY` (0, the whole primary display and the behaviour this contract shipped
  with) and `CAPTURE_TARGET_FOCUS` (1, the window the user is looking at, which the **body**
  resolves). The target is not a hint, and it was added together with the body that implements it,
  because proto3 gives the brain no way to tell an applied field from an ignored one: a body that
  dropped the target would leave the brain reporting a constraint that never applied.
  `CaptureScreenReply` has the `image` plus `resolved_target`, what the body actually captured, read
  off the encoded picture rather than off the request, so a window filling the display reports
  `CAPTURE_TARGET_DISPLAY` and the OS receipt, picked by the same predicate, agrees. The reply names
  the resolved target and never the rectangle, because the request offers the model no rectangle to
  choose and returning coordinates would hand it that frame anyway. `ImageBlob` has `data`,
  `mime_type`, `width`, `height`, `source_width` and `source_height`, which are the **display's**
  before the body's crop and downscale even when the picture is one window, and
  `captured_at_unix_ms`.
- **Volume, notifications and input**: `GetVolumeRequest`, `SetVolumeRequest`, `VolumeState`,
  `NotifyRequest`, `NotifyReply`, `InjectInputRequest`, `TypeText`, `KeyChord` and
  `InjectInputReply`.
- **Services**: `BrainServiceServicer` (the base class to implement), `BrainServiceStub` (the
  client) and `add_BrainServiceServicer_to_server` belong to `BrainService`, which the brain hosts
  (`cortex_orchestrator`) and the body calls. `BodyServiceServicer`, `BodyServiceStub` and
  `add_BodyServiceServicer_to_server` cover `BodyService`, which the body hosts and
  `cortex_body_client` calls through `GrpcBodyGateway` (ADR-0023).
- `SEAM_TOKEN_HEADER = "x-cortex-seam-token"` is the metadata key for the shared token (ADR-0016).
  It lives here because both directions need it: the brain server's interceptor
  (`cortex_orchestrator`'s `auth.py`) and the `BodyService` client (`cortex_body_client`). The
  body's Rust side keeps its own constant of the same value.

**Typing.** Message classes are fully typed through the committed `body_pb2.pyi`. The two `add_*`
registration helpers are re-annotated in the facade as
`Callable[[<Servicer>, grpc.Server | grpc.aio.Server], None]`. The generated stub classes'
*attributes* (`stub.Health` and the rest) are untyped, so consumers annotate the reply types at the
call site (`packages/orchestrator/tests/test_server.py` shows the pattern).

## Regenerating the wire code

This is the `just proto` recipe. Rerun it whenever `proto/body.proto` changes, then commit the
output:

```sh
mkdir -p /tmp/protostage/cortex_seam/_generated
cp proto/body.proto /tmp/protostage/cortex_seam/_generated/
cd brain && uv run python -m grpc_tools.protoc -I /tmp/protostage \
  --python_out=packages/seam/src --grpc_python_out=packages/seam/src \
  --pyi_out=packages/seam/src /tmp/protostage/cortex_seam/_generated/body.proto
```

The staging copy under `cortex_seam/_generated/` is what makes protoc emit the correct absolute
import (`from cortex_seam._generated import body_pb2`) in the generated files.

## Invariants

- `src/cortex_seam/_generated/` holds ONLY protoc output (`body_pb2.py`, `body_pb2.pyi`,
  `body_pb2_grpc.py`), all committed, never hand-edited, and exempt from the lint, type, coverage
  and line-cap checks (ADR-0001 decision 7, ADR-0002 decision 4). It has no `__init__.py` and
  resolves as a namespace subpackage.
- `proto/body.proto` v0 field numbers are frozen: extend, do not renumber.
- The facade holds no logic and has re-exports and type annotations only. PEP 561 `py.typed` ships
  with the package and pyright strict stays clean for consumers.
- The generated code sets minimums at generation time (currently grpcio 1.81.1 or later and the
  protobuf 6.33.x runtime); keep `grpcio`, `grpcio-tools` and `protobuf` moving together.

**Dependencies.** grpcio and protobuf at runtime. Dev-only from the workspace root: grpcio-tools
(code generation) and types-grpcio (strict typing of `grpc` and `grpc.aio`).
