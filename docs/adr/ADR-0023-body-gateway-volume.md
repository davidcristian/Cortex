# ADR-0023: The brain to body direction via `BodyGateway`, `AudioControl`, and volume as the first OS action

**Status:** Accepted (2026-08-22)

## Context

Every call between body and brain once ran one direction: the body connects to the brain's
`BrainService`. This decision opens the reverse direction, the brain calling the host body, and
adds the first host OS action: reading and setting the system volume. Volume was chosen as the
smallest reversible action that proves the direction. Further OS actions arrive as more
`BodyService` RPCs and `cfg`-conditional OS-trait methods behind the same two ports; the reminder
toast ([ADR-0025](ADR-0025-scheduling-reminders.md)) and screen capture
([ADR-0029](ADR-0029-vision-screen-capture.md)) have since done so.

Four facts shaped it:

- **The wire contract already declared it.** `proto/body.proto` had `BodyService` and its messages,
  and both code generators emit a client and a server for every service, so the first slice needed
  no proto edit, only hand-written, fully covered wiring on both sides
  ([ADR-0003](ADR-0003-generated-stubs.md)).
- **Two open questions came due.** [ADR-0001](ADR-0001-architecture.md) Q2 (body capabilities as
  MCP tools, or internal tools over a port) and Q3 (the brain connects to the body, or the body
  tunnels body-directed calls over a stream it opened). This ADR resolves both.
- **The roadmap's security assumption is revisited.** The setup was loopback-only listeners plus an
  optional shared token ([ADR-0016](ADR-0016-shared-token.md)). The body's `BodyService` listener may
  have to accept a connection from the dockerized brain, which is outside loopback, so the token
  becomes the boundary in that direction.
- **The one hard rule.** Volume is read from the OS on demand and the body server holds no turn or
  conversation state, so it needs no swap-safety design.

## Decision

### 1. Internal tool over a `BodyGateway` port, not an MCP tool (resolves Q2)

Volume is a pair of built-in tools, `get_volume` and `set_volume`, which the cortex calls like
`spawn_subagents`: merged ahead of the MCP tools by `CompositeToolRegistry` and dispatched through
the audited `ToolDispatcher`. They call a pure-core port, `BodyGateway`
(`cortex_core/ports_body.py`), whose volume methods are `get_volume()` and
`set_volume(*, level=None, mute=None)`, both returning the core value `VolumeState` (`level`,
`muted`). No wire type enters the core. The port has since gained `notify` (ADR-0025) and
`capture_screen` (ADR-0029).

Keeping OS actions internal means a jailbroken subagent never gets one: built-ins are cortex-only
by construction, since subagents receive only the remote MCP subset with the tools needing
confirmation removed ([ADR-0010](ADR-0010-subagents.md),
[ADR-0013](ADR-0013-untrusted-content.md)). Failures cross the port as a typed `BodyGatewayError`
(decision 8); the built-ins catch it and return an `is_error` result, so a dead body is a message
the cortex can recover from, never a turn-killing exception.

### 2. `GrpcBodyGateway` makes the brain a gRPC client (`body_client` package)

The real adapter is `GrpcBodyGateway` in the workspace package `body_client`
(`cortex_body_client`), the typed `BodyService` client ADR-0003 decision 5 reserved. It wraps
`cortex_seam.BodyServiceStub` over an injected `grpc.aio.Channel`, translates between proto and
domain values, builds `SetVolumeRequest` with explicit presence (only the fields the caller set),
attaches the token as `x-cortex-seam-token` metadata, and classifies every `AioRpcError` into a
`BodyGatewayError` kind (decision 9). Like `LlamaCppBackend` it holds no state, takes its transport
at construction, and offers a `connect(endpoint, *, token)` classmethod the composition root owns.
It is covered to 100% against a real `grpc.aio` loopback server hosting a fake servicer
(`test_gateway.py`); checks against a real body are `integration`-marked. The port stays abstract
on purpose: the Q3 fallback, a tunnel over a stream the body opens, would be a different
`BodyGateway` adapter plus one streaming RPC and the body's loop over it, with no core or tool change.

### 3. `AudioControl` OS trait; the body hosts a `BodyService` server

Beside `Hotkey` ([ADR-0011](ADR-0011-body-v1.md)), `body_core::os` declares
`AudioControl: Send + Sync` with `get_volume` and `set_volume(VolumeChange)` over two pure values,
`VolumeState` (`level: f32`, `muted: bool`) and `VolumeChange` (both fields `Option`).
`Send + Sync` is required because the tonic service holding it is `Send + Sync + 'static`. The
clamp to [0.0, 1.0] that the proto documents is pure core logic in `VolumeChange::new` (NaN reads
as 0.0), covered at 100% in `body_core`, so an OS backend never receives an out-of-range scalar.

The measurable half of the server lives in `body_rpc::server`: `OsService<A: AudioControl, N:
Notify, S: ScreenCapture>` implements the generated `BodyService` trait, `audio_error_to_status`
and `notify_error_to_status` map port errors to statuses (the inverse of `status_to_error`), and
`body_service(audio, notifier, screen, receipts, token)` builds the server behind the token
validator. `inject_input` answers `Status::unimplemented` (decision 13). It is contract-tested over
an in-process loopback server driven by a generated client and fake backends, covering every
`Option` combination and every error branch, to 100% line, region and branch. The bind and serve
lifecycle lives in the Tauri shell, `body/app/src-tauri/src/body_server.rs`, outside the checks.

### 4. Volume needs no confirmation; the confirmer is available but not used

`get_volume` is a read and `set_volume` is reversible and low-harm, so both are `confirm_required=False`: a
spoken "set volume to 30%" should not raise an approval card. Both results are `Trust.TRUSTED`,
since host state is system-generated, so a volume call never taints a turn. A later OS action with
side effects can require confirmation by setting `confirm_required=True` on its spec. Volume itself has a
zero-code opt-in: adding `set_volume` to `CORTEX_TOOLS_GATED` makes the dispatcher's `confirm_names`
check require confirmation, confirming on a clean turn and denying on a tainted one, as on the
remote path.

### 5. The token, reversed (mirrors ADR-0016)

The body validates with a tonic server interceptor, `RpcTokenValidator` in `body_rpc::auth`: it
reads `x-cortex-seam-token`, compares in constant time with a dependency-free fixed-time byte
compare, and rejects `UNAUTHENTICATED` before any method runs. It is always attached and passes
everything through when the configured token is empty, which in Rust is simpler than a conditional
service type, and it deliberately does not derive `Debug`. The brain attaches the token in
`GrpcBodyGateway`, reusing the one `CORTEX_SEAM_TOKEN`. The header name lives in `cortex_seam` as
`RPC_TOKEN_HEADER`, re-exported from `cortex_orchestrator.auth`; `body_client` imports it from the
`cortex_seam` facade, never from the orchestrator. The Rust side keeps its own `const`.

### 6. Connectivity: the brain connects to the body (resolves Q3)

The brain connects to `CORTEX_BODY_ENDPOINT`, `host.docker.internal:50151` from the container;
`docker/docker-compose.body.yml` adds the `host-gateway` `extra_hosts` entry native Docker needs.
The body binds `CORTEX_BODY_ADDR`, default `127.0.0.1:50151`, which is safe for development and the
loopback contract tests. For the real container-to-host path the operator binds an interface the
container can reach (`0.0.0.0:50151`), which is the revisit the roadmap's assumption foresaw. The
boundary then is the token plus the host firewall keeping the port host-local.

### 7. `unsafe` for Core Audio: a narrowly scoped exception in `os_windows`

Windows Core Audio (`IMMDeviceEnumerator` to `IAudioEndpointVolume`) is COM, and the `windows`
crate presents every COM call as `unsafe`. The body workspace sets `unsafe_code = "forbid"`, which
a crate cannot relax locally, so `os_windows` opts out with its own `unsafe_code = "deny"`
(re-declaring the other workspace lints); each module that has an authorization re-enables it with
a scoped `#![allow(unsafe_code)]` naming the ADR that granted it. This ADR authorizes the
`audio` module. Three more have their own grants: `notify` (one `CoInitializeEx`, ADR-0025), and
`screen` and `focus` (GDI and the Z-order walk, ADR-0029). Every other crate keeps `forbid`.
`os_windows` is `cfg(windows)`, compiles to nothing on Linux and is validated on the host, never in
CI; `os_linux` and `os_macos` have `unimplemented!()` stubs under `#[coverage(off)]`.

### 8. The port reports every failure as one error with a kind

`BodyGatewayError` has `kind: BodyFailure`, keyword-only, with the enum beside it in
`cortex_core/errors.py`. One exception type rather than a subclass tree, so every `except
BodyGatewayError` keeps its meaning and a caller branches on one attribute. The six kinds are a
designed family ordered by how far the call got:

| Kind | The call got as far as |
| --- | --- |
| `UNREACHABLE` | nowhere: no answer arrived, for want of a route or of time |
| `REFUSED` | the body's policy check, which answers the same way every time (capture switched off, a rejected token) |
| `UNSUPPORTED` | the body, which has no such capability |
| `UNREADY` | the capability, whose host state is not there (no display, no audio endpoint) |
| `OVERSIZE` | done, and the result will not fit the reply's size limit |
| `FAULTED` | tried, and broke |

Three are absences, marked as a set by the `un` prefix, and three are events. `REFUSED` rather than
`DENIED`, because `DENIED_MSG` is already the denial for a tool that needs confirmation. `FAULTED`
is the default, and the brain-side refusals of a capture reply end up in it: a failure nobody
classified must never claim the body was unreachable, which was the defect removed here: before
it, one failure in eight told the cortex the truth
([readings](../readings/body-failure-leads.md)).

### 9. The adapter classifies, the core words it, and both tables are declarative

`cortex_body_client/failures.py` holds the one status-code table (`kind_of`), split from
`gateway.py` as `status.rs` is from `client.rs` on the body side. `cortex_core/body_failure.py`
holds the one wording table and `body_failure_message(err, action=...)`, so every body built-in
shares an opening sentence per kind and names only its infinitive (`control volume`, `capture the
screen`). Neither table has a code path: a kind without a sentence fails a test that walks the
enum, and an unclassified code falls to `FAULTED`. The body's own sentence follows after a colon.

### 10. A body that answered never says `UNAVAILABLE`

A client-synthesized `UNAVAILABLE` from a connection that never opened is the same code a body
would send for a shut lid, and grpc-python does not mark a synthesized status as tonic does. So
here `UNAVAILABLE` means the call did not arrive, and nothing the body writes uses it. Host-state
failures (`CaptureError::NoDisplay`, `AudioError::NoEndpoint`, `NotifyError::Unavailable`) answer
`FAILED_PRECONDITION`; `CaptureError::TooLarge` answers `RESOURCE_EXHAUSTED`; `Disabled` stays
`PERMISSION_DENIED` and backend faults stay `INTERNAL`. `NotifyError` keeps its variant name, which
is `body_core` vocabulary about the host. The proto did not change, and an older body's
`UNAVAILABLE` classifies as `UNREACHABLE`, the sentence every failure used to have.

### 11. Every OS call runs off the async worker

Every `OsService` handler hands its one synchronous OS call to `off_worker`, which runs it on
tokio's blocking pool. The reason is not the call's latency: the `BodyService` server shares its
runtime with the overlay's own calls to the brain, so a worker parked on COM delays unrelated work.
It is safe because no `!Send` COM object crosses a thread: `WindowsAudioControl` is a unit struct
that resolves its `IAudioEndpointVolume` per call and `WindowsNotify` holds only an app-id
`String`, so each COM pointer is created, used and dropped inside one closure. `OsService` holds
each backend behind an `Arc` only to lend it to that thread. A backend that panics answers
`Internal` rather than tearing down the brain's connection.

### 12. The body's port number is declared in the shell

`DEFAULT_BODY_PORT` (`50151`) is a `const` in `body/app/src-tauri/src/body_server.rs`, the module
that binds it, `cfg(windows)` like `start` itself. Hoisting it into `body_core` or `body_rpc`,
which `just check` compiles, was declined: neither crate binds anything, so the value would be
exported for one consumer outside the workspace to buy a compiler's opinion of a `u16`. What can
diverge is the compose default, the runbooks, the module contracts, the `docs/host/`
prerequisites and the brain's live gateway test, and `scripts/crosscheck.py` compares every one of
them with this declaration ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)). The scan fails
closed, so a rename in the shell fails `just check` even though only CI's `check-shell` compiles it.

### 13. `InjectInput` waits for a consumer; volume is not overlay state

`InjectInput` is the one `BodyService` RPC left unbuilt, and it is built only when a real feature
drives input injection, as one slice: an input trait covering text, keys and pointer (the server
dispatches the whole `oneof`), behind one `confirm_required=True` audited tool that inherits the confirmer and
the tainted-turn denial, one Windows `SendInput` adapter under its own `unsafe` authorization, and
a proto pointer extension designed with that consumer. Wiring the handler first would let anyone
holding the token move the real mouse without the check that requires confirmation, since that
check lives on the brain's dispatch and `BodyService`'s only guard is the token. Pointer injection
alone is declined for the same reason.

Showing `GetVolume` as overlay state is declined. The body serves `GetVolume` and the overlay lives
inside the body, so it would need a new Tauri command and overlay port for a number that changes
from hardware keys and other applications with nothing to tell the overlay, beside an OS tray icon
that is always right. It reopens with a consumer (an overlay control that changes volume) or a
producer (a host change event such as `IAudioEndpointVolumeCallback`).

## Consequences

- **Covered by `just check`:** the port, its errors and fake, the built-ins, `GrpcBodyGateway` over
  a loopback fake, the composition root wiring, `AudioControl` and its clamp, `OsService`,
  `RpcTokenValidator`, the status mappers, and the Linux and macOS stubs.
- **Validated in Docker (2026-07-08):** a containerized `GrpcBodyGateway` reached a host-side
  `BodyService` over `host.docker.internal` with the token, and got `UNAUTHENTICATED` without it.
- **Host-only:** the real `WindowsAudioControl`, the shell's bind and serve, and "set volume to
  30%" spoken end to end ([H-002](../host/tasks/002-core-audio-volume-action.md)). It needs a
  Windows desktop and any GPU that holds the cortex, not a 24 GB one specifically.
- Both Windows backends call `CoInitializeEx` per call without a matching `CoUninitialize`, now on
  blocking-pool threads tokio reclaims after its idle keep-alive; the fix is one dedicated
  COM-initialized thread ([R-224](../refinements/tasks/224-unbalanced-com-initialization.md),
  observed on the host by [H-009](../host/tasks/009-unbalanced-com-initialization.md)).
- A safe Core Audio crate would retire only the `audio` module's allow; the one examined
  initializes COM per call, which R-224 rejects ([R-223](../refinements/tasks/223-safe-core-audio-wrapper.md)).
- The non-loopback setup stays one shared token over plaintext. Transport credentials would touch
  four places (`aio.insecure_channel` in `GrpcBodyGateway.connect`, `Server::builder()` in
  `body_server::start`, the brain's `add_insecure_port` and the body's `Channel::from_shared`), and
  the tree builds tonic without TLS features, so enabling one is the first step
  ([R-219](../refinements/tasks/219-hardened-non-loopback-posture.md), triggered by the machine
  leaving single-user). The tunnel fallback stays deferred while `host.docker.internal` from a
  bridge container reaches a host listener on `0.0.0.0` ([R-218](../refinements/tasks/218-tunnel-fallback.md)).

## Alternatives rejected

- **Volume as an MCP tool**: needs a body-side MCP server and leaks the capability to subagents.
- **A new volume RPC or stream**: unary `GetVolume` and `SetVolume` already exist.
- **Confirming `set_volume` by default**: friction on a reversible action (decision 4).
- **A separate `BodyService` server crate**: the measurable adapter fits in `body_rpc` beside the
  client; only the bind glue is host-only, and it lives in the shell.
- **A loopback-only body bind**: the container cannot reach the host's `127.0.0.1`.
- **A subclass per failure kind**: callers would need an `isinstance` ladder.

## Related

- Modules: [brain-body-client](../modules/brain-body-client.md),
  [brain-core](../modules/brain-core.md), [body-rpc](../modules/body-rpc.md),
  [body-os](../modules/body-os.md), [body-app](../modules/body-app.md).
- Runbook: [body-volume](../runbooks/body-volume.md).
- Readings: [what the cortex reads when a body call fails](../readings/body-failure-leads.md).
- ADRs: [ADR-0016](ADR-0016-shared-token.md) (the token this mirrors),
  [ADR-0025](ADR-0025-scheduling-reminders.md) (the toast in this direction),
  [ADR-0029](ADR-0029-vision-screen-capture.md) (capture in this direction),
  [ADR-0042](ADR-0042-cross-tree-constant-registry.md) (the registry covering the port number).
