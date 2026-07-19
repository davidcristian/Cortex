# ADR-0023: The brain→body seam via `BodyGateway`, `AudioControl`, and volume as the first OS action

- **Status:** Accepted (Slice 9)
- **Date:** 2026-07-08

## Context

Every seam call so far runs one direction: the body dials the brain's `BrainService`
(`Converse`/`Health`/session reads). Slice 9 opens the **reverse** direction (the brain
calls the host body) and lands the first host **OS action**: reading and setting the
system volume. Volume is chosen deliberately as the *smallest, reversible* surface that
proves the bidirectional seam; the OS-action catalogue then grows (brightness, media keys,
window/app control, input injection, …) as more `BodyService` RPCs + `cfg`-gated OS-trait
methods behind the *same* seams, never a seam change (ROADMAP Slice 9, AGENTS.md scope
policy).

Four facts shape the design:

- **The seam already declares it.** `proto/body.proto` has carried `BodyService`
  (`GetVolume`/`SetVolume`/`CaptureScreen`/`InjectInput`) and its messages since Slice 2,
  frozen at v0. Both codegens emit client **and** server for every service, so the brain
  already has `cortex_seam.BodyServiceStub` and the body already has
  `body_rpc::generated::body_service_server::{BodyService, BodyServiceServer}`. **Slice 9
  needs no proto edit and no regeneration**. It is only hand-written, fully-gated wiring on both
  sides (ADR-0003).
- **Two open questions come due.** ADR-0001 Q2 (do body capabilities surface to models as
  MCP tools, or as internal tools over a `BodyGateway`?) and Q3 (connectivity direction:
  brain dials the body, or the body tunnels body-directed calls over a body-initiated
  stream?). This ADR resolves both.
- **Assumption 5 is revisited.** The security posture has been *loopback-only listeners +
  an optional shared-secret seam token* (ADR-0016). This is the first slice where a listener
  (the body's `BodyService` server) may need to accept a connection from **outside**
  loopback (the dockerized brain reaching the host), so the seam token stops being optional
  in that direction (it is the boundary when the bind is not pure loopback).
- **The one hard rule.** No state in a model process. Volume is read from the OS on demand;
  the body server is a stateless function over the host, holding nothing turn- or
  conversation-scoped. It needs no swap-safety design because it holds no state at all.

## Decision

### 1. Internal tool over a `BodyGateway` port, not an MCP tool (resolves Q2)

Volume is a **built-in** tool (`get_volume`, `set_volume`) the cortex calls exactly like
`spawn_subagents`, merged ahead of the MCP tools by the existing `CompositeToolRegistry` and
dispatched through the Slice 6 audited `ToolDispatcher`. It is **not** an MCP sidecar tool.
The tools call a new pure-core port:

```python
class BodyGateway(Protocol):
    async def get_volume(self) -> VolumeState: ...
    async def set_volume(self, *, level: float | None = None, mute: bool | None = None) -> VolumeState: ...
```

`VolumeState` is a new pure-core value (`level: float`, `muted: bool`) and **no wire type
enters the core**. The port is the internal-tool seam ADR-0001 Q2 predicted; keeping OS
actions internal (not MCP) means a jailbroken *subagent* never gets one, because built-ins
are cortex-only by construction (subagents receive only the remote MCP subset,
`UngatedToolRegistry`-stripped, per ADR-0010/0013). Failures cross the port as a typed
`BodyGatewayError` (the adapter wraps `grpc.aio.AioRpcError`, cause chained); the volume
tools catch it and return an `is_error` result the cortex can recover from. A dead body is
a message, never a turn-killing exception.

### 2. `GrpcBodyGateway` makes the brain a gRPC client (`body_client` package)

The real adapter is `GrpcBodyGateway` in a **new workspace package `body_client`**
(`cortex_body_client`), the typed `BodyService` client wrapper ADR-0003 decision 5 reserved
for this slice. It wraps `cortex_seam.BodyServiceStub` over an injected `grpc.aio.Channel`,
translates proto↔domain `VolumeState`, builds `SetVolumeRequest` with **explicit presence**
(only the fields the caller set, whether level, mute, or both), attaches the seam token as
`x-cortex-seam-token` metadata, and maps `AioRpcError` → `BodyGatewayError`. It mirrors
`LlamaCppBackend`: a thin transport translator, no state, transport injected at construction,
a `connect(endpoint, *, token) -> (adapter, closer)` classmethod owned by the composition
root. It is 100%-covered without a live body by standing up a real `grpc.aio` loopback
server hosting a fake `BodyServiceServicer` (the `test_auth.py` pattern); real-body checks
are `integration`-marked.

Keeping the port abstract is deliberate: the Q3 **fallback** (tunnel body-directed calls
over a body-initiated bidi stream, if `host.docker.internal` proves brittle) becomes a
different `BodyGateway` adapter, with no core, tool, or proto change.

### 3. `AudioControl` OS trait; the body hosts a `BodyService` server

Mirroring the `Hotkey` seam (ADR-0011), a new pure port lives in `body_core::os`:

```rust
pub trait AudioControl: Send + Sync {
    fn get_volume(&self) -> Result<VolumeState, AudioError>;
    fn set_volume(&self, change: VolumeChange) -> Result<VolumeState, AudioError>;
}
```

with pure value types `VolumeState { level: f32, muted: bool }` and
`VolumeChange { level: Option<f32>, mute: Option<bool> }`. `AudioControl` gains a `Send + Sync`
supertrait (unlike `Hotkey`) because the tonic `BodyService` service is `Send + Sync + 'static`
and holds it. The **clamp-to-[0.0, 1.0]** rule the proto documents is *pure core logic*
(`VolumeChange::new`, NaN→0.0 the defensive floor), fully tested in `body_core` under the
100% gate. The OS backend never receives an out-of-range scalar.

The body now **hosts a gRPC server** for the first time. The thin, coverable half lives in
`body_rpc`: a generic `VolumeService<A: AudioControl>` implementing the generated
`BodyService` trait (`get_volume`/`set_volume` → the port; `capture_screen`/`inject_input`
→ `Status::unimplemented`, their slices later), an `audio_error_to_status` mapper (the
inverse of `status_to_error`), and a `body_service(audio, token)` constructor. It is
contract-tested over an in-process loopback server driven by a generated `BodyServiceClient`
and a fake `AudioControl`, covering every `Option` combination, the error arms, and the two
unimplemented arms, to 100% line+region+branch. The **bind/serve lifecycle** and the real
backend are host-only (see §5).

### 4. Volume is ungated (reversible); the gate is available but not spent

`get_volume` is a read; `set_volume` is reversible and low-harm. Both ship `gated=False`, so
the Slice 6.5/8.8 confirm gate is **not** exercised here, since a spoken "set volume to 30%"
should not demand an approval card. Both results are `Trust.TRUSTED` (host state is
system-generated, never third-party content) so a volume call never taints the turn or pulls
in the URL guardrail.

The gate is nonetheless *inherited for free* by any later side-effectful OS action (input
injection, launch/focus) by setting `gated=True` on its spec. And volume itself has a
zero-code **user opt-in**: adding `set_volume` to `CORTEX_TOOLS_GATED` makes the
dispatcher's authoritative `gated_names` backstop gate it (confirm on a clean turn, hard-deny
on a tainted one). The built-in path honours the same backstop the remote path uses
(ADR-0022), no wiring change. Default off.

### 5. The seam token, reversed (mirrors ADR-0016)

ADR-0016 shipped brain-as-server-validates / body-as-client-attaches. This direction is the
mirror image, reusing the identical header and shared secret (`CORTEX_SEAM_TOKEN`):

- **Body validates** with a new Rust tonic **server** interceptor (`SeamTokenValidator` in
  `body_rpc`): reads `x-cortex-seam-token`, **constant-time** compares (a dependency-free
  fixed-time byte compare, matching `secrets.compare_digest`'s posture), rejects
  `UNAUTHENTICATED` before any method runs. It is **always attached** but a **no-op when the
  configured token is empty** (the single-type equivalent of the brain's
  "register-only-when-set", since Rust's type system makes always-attach-noop cleaner than a
  conditional service type), so a tokenless deployment behaves byte-for-byte as before. It is
  deliberately not `Debug` (no secret in a log), like the client interceptor.
- **Brain attaches** the token as call metadata in `GrpcBodyGateway`.

The shared wire constant is **lifted to `cortex_seam`** (`SEAM_TOKEN_HEADER`), its natural
home as a seam-contract detail, and re-exported from `cortex_orchestrator.auth` so nothing
downstream breaks; `body_client` imports it from the seam facade, never from the orchestrator
(dependency direction). The Rust side keeps its own `const` (different language).

### 6. Connectivity: the brain dials the body (resolves Q3), and assumption 5's revisit

Q3's default is taken: **the brain dials the host body** at `CORTEX_BODY_ENDPOINT`
(`host.docker.internal:<port>` from the dockerized brain; the compose overlay adds the
`host-gateway` `extra_hosts` entry native Docker needs). The body binds a configurable
`CORTEX_BODY_ADDR` (default `127.0.0.1:50151`, which is safe for dev and the loopback contract
tests). For the **real** brain→body path the user binds an interface the container can reach
(e.g. `0.0.0.0:50151`); this is the moment assumption 5 foresaw ("revisit only if anything
ever listens beyond loopback"). The boundary when the bind is not pure loopback is the **seam
token + the host firewall** (the port is host-local, allowed inbound only for the body). The
abstract `BodyGateway`/`AudioControl` seams keep the tunnel fallback a pure adapter swap if
`host.docker.internal` proves brittle on a WSL2 host.

### 7. `unsafe` for Core Audio: a narrowly-scoped, ADR-authorized exception in `os_windows`

Windows Core Audio (`IMMDeviceEnumerator` → `IAudioEndpointVolume`) is COM, and the official
`windows` crate surfaces every COM method call as `unsafe` (unlike `global-hotkey`, which fully
hides its `unsafe`, so the `WindowsHotkey` precedent does not carry over). The body workspace
sets `unsafe_code = "forbid"`, which a crate cannot locally downgrade. **This ADR authorizes
`unsafe` in `os_windows` only** (AGENTS.md gate 5): that crate opts out of the workspace
`forbid` with its own `[lints.rust] unsafe_code = "deny"` and `#![allow(unsafe_code)]` scoped to
the Core Audio module, re-declaring the other workspace lints (clippy pedantic, the `coverage`
cfg). Every other crate keeps `forbid`. `os_windows` is `cfg(windows)`, compiles to nothing on
Linux, and is host-validated, never in CI, so the exception never touches the gated build;
`os_linux`/`os_macos` get `unimplemented!()` + `#[coverage(off)]` `AudioControl` stubs. The real
`WindowsAudioControl` is authored here (host-authored, like `WindowsHotkey` in Slice 8) and
validated on Windows by the user.

## Consequences

**CI-gated (mine, 100% under `just check`, no GPU/OS/GUI):** the `BodyGateway` port +
`VolumeState` value + `BodyGatewayError` + `InMemoryBodyGateway` fake; the `get_volume`/
`set_volume` built-ins; the `GrpcBodyGateway` adapter (`body_client`) over a loopback fake
server; `BodyConfig` + `build_body_gateway` + the `build_cortex_tools` extension + the
`run_from_env` thread-through; the `AudioControl` trait + pure clamp + `body_core` contract
test; the `VolumeService` server adapter + `SeamTokenValidator` + `audio_error_to_status` in
`body_rpc` with loopback contract tests; `os_linux`/`os_macos` stubs; the `SEAM_TOKEN_HEADER`
lift.

**Agent-Docker (mine):** the brain→body dial across the container boundary, with the brain's
`GrpcBodyGateway` reaching a body-side `BodyService` server over `host.docker.internal`,
`integration`-marked. On this host the 8 GB GPU cannot hold the gemma-4-12B cortex, so a
full cortex-*driven* `set_volume` is bounded by what fits; the seam and tool path are
validated with whatever tool-calling model fits, or against the Echo path for the wire.

**Host-Windows (host-only):** the real `WindowsAudioControl` Core Audio backend; the
`BodyService` server bind/serve started in the Tauri shell's `setup()`; and the end-to-end
"set volume to 30%" spoken to the overlay moving host volume through the real seam.

**Deferrals** (recorded in ROADMAP's deferred-refinements section, each behind these unchanged
seams): the Q3 body-initiated-stream tunnel fallback; a hardened non-loopback posture (mTLS /
per-direction tokens) if the machine ever leaves single-user; `spawn_blocking` for the sync
OS call inside the async handler (fine at personal scale, a fast COM call); `GetVolume`
surfaced as overlay state; and the remaining `BodyService` RPCs (`CaptureScreen` in Slice 10;
`InjectInput` comes later).

## Alternatives considered

- **Volume as an MCP tool.** Rejected (Q2): it would need a body-side MCP server *and* leak
  the capability into the subagent tool set; the internal `BodyGateway` keeps OS actions
  first-party and cortex-only.
- **A new `Volume` RPC / streaming.** Rejected: `GetVolume`/`SetVolume` unary already exist
  and volume is a point read/write; no stream needed.
- **Gating `set_volume` by default.** Rejected as UX friction on a reversible action; the
  opt-in backstop (`CORTEX_TOOLS_GATED`) covers the cautious user without taxing everyone.
- **A separate `BodyService` server crate.** Rejected: the coverable adapter fits in
  `body_rpc` beside the client (its natural home); only the bind/serve glue is host-only, and
  that lives in the ungated shell like every other Tauri command.
- **Body binds loopback only.** Rejected as insufficient for the container→host path (the
  brain cannot reach the host's `127.0.0.1`); a configurable bind + the seam token is the
  chosen resolution of assumption 5's revisit.

## Addendum (2026-07-08): agent-Docker validation of the dial across the container boundary

The agent half is validated. A host-side fake `BodyService` (the runbook's blessed path: the
`test_gateway.py` `FakeBody` as template, with stateful volume and a required token) was served on
`0.0.0.0:50151` from the brain venv, and `test_gateway_live.py` ran **from a container** (the
uv builder image with the brain workspace mounted; the shipped runtime image carries no dev
deps) with `--add-host host.docker.internal:host-gateway`, `CORTEX_BODY_ENDPOINT=
host.docker.internal:50151`, and the shared `CORTEX_SEAM_TOKEN`:

- **Tokened dial: 1 passed (0.14 s).** The containerized `GrpcBodyGateway` resolved
  `host.docker.internal`, attached `x-cortex-seam-token`, and round-tripped
  `GetVolume` → `SetVolume(0.8)` → restore `SetVolume(0.5)`. The server log shows exactly
  those three calls, and the test left the state as it found it.
- **Untokened dial: rejected.** The same run without the token failed with
  `UNAUTHENTICATED: invalid or missing seam token`, surfaced as `BodyGatewayError`. So the
  reversed seam token is enforced across the container boundary, not just on loopback.

Assumption 3 (`host.docker.internal` reachability, here via the `host-gateway` mapping on a
native WSL2 dockerd) holds. Remaining for the slice: only the **Host-Windows** half, the real
`WindowsAudioControl` Core Audio backend and the spoken "set volume to 30%" end to end
([body-volume.md](../runbooks/body-volume.md)).

## Addendum (2026-07-16): the `BodyService` server type was renamed

When the reminder toast joined this direction of the seam
([ADR-0025](ADR-0025-scheduling-reminders.md)), the server stopped answering one OS capability:
`VolumeService<A: AudioControl>` is now `OsService<A: AudioControl, N: Notify>` and
`body_service(audio, token)` is `body_service(audio, notifier, token)`. Nothing above changed
in behavior, and the `unsafe` authorization this ADR scoped to Core Audio widened by one line,
still COM only and still `os_windows` only: activating a WinRT factory needs a COM-initialized
thread, so the toast module makes the same idempotent `CoInitializeEx` call the audio backend
does. The text above is left as the record of what Slice 9 decided.

## Addendum (2026-07-16): the sync OS calls moved off the async worker; the overlay volume indicator is declined

Two of this ADR's deferrals came due together and closed as opposite outcomes.

**`spawn_blocking` landed, for a better reason than the deferral gave.** The deferral called
the inline call "fine at personal scale, as it is a fast COM call", which measures the wrong
thing. The cost is not the call's latency; it is that the `BodyService` server shares its
runtime with the overlay's own seam calls, so parking an async worker on Core Audio delays work
that has nothing to do with audio. `body_rpc::server::off_worker` now hands each handler's one
synchronous call to `tokio::task::spawn_blocking`, and the deferral's "the sync OS call"
(singular) is three: the reminder toast (ADR-0025) is the same shape, and it is the slower
backend, since activating the WinRT factory and reading `ToastNotifier.Setting` both cross to
the notification service.

**The safety question was answered from the types before the change was made**, because a
`spawn_blocking` that moves a `!Send` COM object across threads is a bug, not a fix. Neither
backend holds one: `WindowsAudioControl` is a unit struct that resolves its
`IAudioEndpointVolume` per call, `WindowsNotify` holds only an app-id `String`, and decision 3
had already made both ports `Send + Sync`. Every COM pointer is therefore created, used, and
dropped inside one closure on one thread. `OsService` holds each backend behind an `Arc` purely
to lend it to that thread, and still holds no state. One behaviour improved on the way: a
backend that panics mid-call used to cost the brain the connection (`Cancelled`), and now
answers `Internal` like any other backend fault. The proof is behavioural rather than
structural: the contract fakes record which thread each call ran on, and `#[tokio::test]`'s
current-thread runtime makes an inline call observable as "the test's own thread".

**`GetVolume` as overlay state is declined.** The deferral assumed the overlay could surface
the RPC, but the body *serves* `GetVolume`; the overlay lives inside the body and would never
call it. It would need a new Tauri command over `AudioControl` and a new overlay port, since
`BrainBridge` is the overlay's port to the brain and a host-local fact does not belong on it.
Past that, nothing in the overlay reads or changes volume, and the summon-edge latch that keeps
the connection dot honest cannot keep a volume number honest: volume changes from hardware keys
and other applications with nothing to tell the overlay, next to an OS tray icon that is always
right. That is the always-green dot ADR-0011 removed, in another form. It reopens with a real
consumer (an overlay control that changes volume) or a real producer (a host-side change event
such as `IAudioEndpointVolumeCallback`). The rest of that entry, `CaptureScreen` and
`InjectInput`, stays deferred to its slices.

**One deferral opened behind the change:** both Windows backends still call `CoInitializeEx`
per call without a matching `CoUninitialize`, which was already true on the async workers but
now applies to blocking-pool threads tokio reaps after an idle timeout. Recorded in
[docs/refinements/body-gateway.md](../refinements/body-gateway.md) as fix-when-it-bites, the fix
being one dedicated COM-initialized thread for the OS calls.

**Validated:** `just check` (both trees, 100%); the brain's own `GrpcBodyGateway` dialling the
real Rust `BodyService` over loopback, tokened round-trip passing and untokened still
`UNAUTHENTICATED`, with the server log showing all three OS calls on a blocking-pool thread;
and `cargo clippy --target x86_64-pc-windows-msvc` over the whole workspace, so the real Core
Audio and toast backends are known to still satisfy the bounds. Unchanged and still host-side:
the real "set volume to 30%" on Windows.

## Addendum (2026-07-16): pointer-input injection is declined, dead until a consumer

The last of this ADR's `InjectInput` deferrals to be triaged is the cross-cutting backlog's
**pointer-input injection** entry, and it closes as declined, dead until a consumer, on the evidence
rather than the entry's cost estimate.

The entry framed pointer as a small increment over an existing text/keyboard input-injection
capability, needing only a proto extension for a pointer event. Read against the tree, no input
injection exists at any tier. `proto/body.proto` has carried the `InjectInput` RPC and its
`TypeText`/`KeyChord` messages since Slice 2, but as a forward-looking stub beside `CaptureScreen`,
decision 3 above having wired only volume; there is no input trait in `body_core` (only `Hotkey`,
`AudioControl`, `Notify`), no `os_windows` adapter, the `BodyService` server answers `inject_input`
with `Status::unimplemented` (the state this ADR set and a test pins), the brain's `BodyGateway` port
carries no inject method, and no built-in tool drives it. So pointer is not one level over a built
base; it is part of the whole input-injection slice this ADR defers ("`InjectInput` comes later").

Two things make declining it the honest call rather than building the clean seam and adapter slice
the entry imagined. First, no consumer: nothing in the brain or the overlay asks the body to move the
pointer, so the capability would be shipped ahead of any use, and its permanent seam shape (coordinate
space, button identity, press/release/click, scroll axis and delta) cannot be designed correctly
against a use that does not exist. Second, and unlike volume, it is the highest-harm OS action.
Decision 4 makes a side-effectful OS action safe only by being a `gated=True` audited tool that
inherits the confirmer and the tainted-turn denial (a gated call on a tainted turn returns
`DENIED_MSG` and never reaches the confirmer). That gate lives on the brain's tool dispatch, not on
`BodyService`, whose only guard is the seam token. Building the Windows `SendInput` adapter and wiring
the server handler ahead of that tool would let the body move the real mouse for anyone holding the
seam token, shipping an irreversible machine-control primitive (click "OK", approve a dialog, drag a
file) without the front door that would gate it. That is the same fail-closed reasoning the
`GetVolume` and real-file-attachment declines turned on, on the most dangerous surface in this
catalogue.

It reopens the day a real feature drives input injection, built then as one slice rather than a
pointer increment: the whole InputInjector trait (text, keyboard, and pointer, since the server
dispatches the whole `oneof`) behind one `gated=True` audited tool inheriting the confirmer and taint
block, one Windows `SendInput` adapter under a **new `unsafe` authorization** (this ADR scoped
`unsafe` in `os_windows` to Core Audio and, later, the toast; `SendInput` is a third COM/FFI `unsafe`
site that needs its own ADR line, per AGENTS.md gate 5), and one proto pointer extension designed with
that consumer. `CaptureScreen` (Slice 10) is unaffected.

No code changed. The seam, the OS traits, the `BodyGateway` port, and the tool dispatch are untouched;
this is a backlog decision recorded at its origin
([docs/refinements/cross-cutting.md](../refinements/cross-cutting.md)).

## Addendum (2026-07-19): `CaptureScreen` closed, and it did not stay behind this seam

This ADR's Deferrals paragraph promised "the remaining `BodyService` RPCs (`CaptureScreen` in
Slice 10; `InjectInput` comes later)" **behind these unchanged seams**, and two later paragraphs
repeat that `CaptureScreen` "stays deferred to its slices" and "is unaffected". All three are now
out of date. `CaptureScreen` landed on 2026-07-18 with the vision slice
([ADR-0029](ADR-0029-vision-screen-capture.md)), and the closure was recorded in the area doc and
the backlog index while this ADR, the one a reader of that Deferrals paragraph actually reaches,
was left saying the opposite. That is the same two-of-three miss caught earlier for the ADR-0012
host half, and this addendum is the third record.

**The cost estimate was wrong in the way the backlog's own opening warning describes.** The seam
did change. `proto/body.proto` gained five fields: `CaptureScreenRequest.max_edge` and `max_bytes`,
and `ImageBlob.source_width`, `source_height` and `captured_at_unix_ms`. The brain-side
`BodyGateway` port gained a method returning a new pure-core value. Two of those fields were not in
the vision design either: `max_bytes` exists because a fixed byte ceiling made the shrink ladder's
give-up arm unreachable, and putting the budget on the request is what makes the brain's bound and
the body's ceiling one number rather than two constants coupled by prose. So "behind the same seam"
was a hypothesis, not a finding, exactly as the index warns for every entry that still carries that
phrasing.

**What is unchanged.** `InjectInput` is now the only unbuilt `BodyService` RPC, and it stays
deferred on the terms the 2026-07-16 pointer-input addendum set: it reopens with a real consumer,
built then as one slice (the whole `InputInjector` trait, text plus keyboard plus pointer, behind
one `gated=True` audited tool inheriting the confirmer and the tainted-turn denial, one Windows
`SendInput` adapter under a new `unsafe` authorization, and one proto pointer extension designed
with that consumer), never as a wired handler shipped ahead of the tool that would gate it. The
backlog holds this area's count unchanged for that reason: half an entry closing does not close the
entry, and a count moved for a half-closed one is how an open deferral gets lost. The entry lives
in [docs/refinements/body-gateway.md](../refinements/body-gateway.md), and it now has its own line
in [docs/refinements/index.md](../refinements/index.md) under dead until a consumer, where it had
been counted but never placed.

No code changed here; this is a records correction at the origin ADR.
