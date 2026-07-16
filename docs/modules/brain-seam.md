# brain/packages/seam (`cortex_seam`)

**Purpose.** The brain's side of the gRPC seam: the committed wire code generated from
[proto/body.proto](../../proto/body.proto) plus a thin typed facade. Every brain package
imports seam names from `cortex_seam` and never from `cortex_seam._generated` directly.

**Public contract** (everything importable from `cortex_seam`; `__all__` is the API):

- Every proto message class: `ClientEvent`, `UserTurn`, `Cancel`, `ServerEvent`,
  `TextDelta`, `ToolActivity`, `StatusUpdate`, `TurnComplete`, `SeamError`,
  `ConfirmRequest`, `ConfirmResponse`, `ConfirmResolved` (the gated-tool confirm
  exchange and the brain-side end of an unanswered one, ADR-0022),
  `HealthRequest`, `HealthReply`, `ListSessionsRequest`, `ListSessionsReply`,
  `SessionSummary`, `GetSessionMessagesRequest`, `GetSessionMessagesReply`,
  `SessionMessage` (the read-only session views, ADR-0021; `SessionSummary` carries a `pinned`
  bool, ADR-0021 pinning addendum), `RenameSessionRequest`,
  `RenameSessionReply` (the gated user-only rename write on the catalog, ADR-0021 management
  addendum), `DeleteSessionRequest`, `DeleteSessionReply` (the gated user-only DESTRUCTIVE
  delete write, which hard-deletes a chat and cascades to its private memories, ADR-0021
  delete addendum), `SetSessionPinnedRequest`, `SetSessionPinnedReply` (the gated user-only pin
  toggle on the catalog, which lifts a chat above the recency window, ADR-0021 pinning addendum),
  `CaptureScreenRequest`,
  `CaptureScreenReply`, `ImageBlob`, `GetVolumeRequest`, `SetVolumeRequest`,
  `VolumeState`, `InjectInputRequest`, `TypeText`, `KeyChord`, `InjectInputReply`.
- `BrainServiceServicer` (base class to implement), `BrainServiceStub` (client), and
  `add_BrainServiceServicer_to_server` belong to `BrainService`, hosted by the brain
  (`cortex_orchestrator`), called by the body.
- `BodyServiceServicer`, `BodyServiceStub`, and `add_BodyServiceServicer_to_server` cover
  `BodyService`, hosted by the body; the brain-side typed client wrapper lands with
  Slice 9 as `cortex_body_client` (`GrpcBodyGateway` over the committed
  `BodyServiceStub`, ADR-0023).
- `SEAM_TOKEN_HEADER = "x-cortex-seam-token"` is the metadata key for the seam token
  (ADR-0016). Lifted here as its natural home (Slice 9, ADR-0023): a seam-contract
  detail shared by the brain server interceptor (`cortex_orchestrator`'s `auth.py`) and
  the `BodyService` client (`cortex_body_client`); the body's Rust side keeps its own
  const of the same value.
- Typing: message classes are fully typed via the committed `body_pb2.pyi`; the two
  `add_*` registration helpers are re-annotated in the facade as
  `Callable[[<Servicer>, grpc.Server | grpc.aio.Server], None]`. The generated stub
  classes' *attributes* (`stub.Health`, …) are untyped, so consumers pin the reply types
  at the call site (see `packages/orchestrator/tests/test_server.py` for the pattern).

**Regenerating the wire code** (the `just proto` recipe; rerun whenever
`proto/body.proto` changes, then commit the output):

```sh
mkdir -p /tmp/protostage/cortex_seam/_generated
cp proto/body.proto /tmp/protostage/cortex_seam/_generated/
cd brain && uv run python -m grpc_tools.protoc -I /tmp/protostage \
  --python_out=packages/seam/src --grpc_python_out=packages/seam/src \
  --pyi_out=packages/seam/src /tmp/protostage/cortex_seam/_generated/body.proto
```

The staging copy under `cortex_seam/_generated/` makes protoc emit the correct absolute
import (`from cortex_seam._generated import body_pb2`) in the generated files.

**Invariants.**
- `src/cortex_seam/_generated/` contains ONLY protoc output (`body_pb2.py`,
  `body_pb2.pyi`, `body_pb2_grpc.py`), all committed, never hand-edited, exempt from
  lint/type/coverage/line-cap gates (ADR-0001 d7, ADR-0002 d4). No `__init__.py`:
  it resolves as a namespace subpackage.
- `proto/body.proto` v0 field numbers are frozen: extend, don't renumber.
- The facade holds no logic and carries re-exports and type annotations only; PEP 561 `py.typed`
  ships with the package and pyright strict stays clean for consumers.
- The generated code pins minimums at generation time (currently grpcio ≥ 1.81.1,
  protobuf runtime 6.33.x); keep `grpcio`/`grpcio-tools`/`protobuf` moving together.

**Dependencies.** grpcio + protobuf (runtime). Dev-only (workspace root): grpcio-tools
(codegen), types-grpcio (strict typing of `grpc`/`grpc.aio`).
