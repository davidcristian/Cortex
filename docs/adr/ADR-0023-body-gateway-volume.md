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
[docs/refinements/index.md#body-gateway](../refinements/index.md#body-gateway) as fix-when-it-bites, the fix
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
([docs/refinements/index.md#cross-cutting](../refinements/index.md#cross-cutting)).

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
in [docs/refinements/index.md#body-gateway](../refinements/index.md#body-gateway), and it now has its own line
in [docs/refinements/index.md](../refinements/index.md) under dead until a consumer, where it had
been counted but never placed.

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-07-19): the cortex-driven half of the volume check is not VRAM-blocked

The Agent-Docker paragraph above says "On this host the 8 GB GPU cannot hold the gemma-4-12B
cortex, so a full cortex-*driven* `set_volume` is bounded by what fits". That first clause was
measured false before it was acted on. [ADR-0029](ADR-0029-vision-screen-capture.md) brought the
real `gemma-4-12b-it-qat-q4_0.gguf` up **beside its projector** on the dev machine's 8 GB card at
`--ctx-size 4096 --parallel 1` on 2026-07-17 and drove a real vision turn through the
shipped inference adapter on 2026-07-18; the MiB figure is
[ADR-0030](ADR-0030-brain-handoff.md)'s, which records the model alone taking 7715 of that card's
8188 MiB. The 11.3 GB reservation the sentence leaned on is an ADR-0004 16K-context
figure, not a floor. (Corrected later the same day: this paragraph first added "a resident cortex
had already emitted a native tool call here on 2026-07-03", which was agent-run on the user's
24 GB card, the machine the agent had then. It says nothing about the dev GPU, and the
2026-07-18 turn is the evidence that does.)

**What this changes.** Nothing in the decision, and one tag. The remaining "set volume to 30%"
check had been filed as needing a Windows desktop **and** a 24 GB card, which is the kind of item
a user must not start until both are in the room, and if those are two machines the wrong tag
costs the trip. It needs a Windows desktop and any card that holds the cortex, so it is
Windows-blocked only ([docs/host/index.md#windows-desktop](../host/index.md#windows-desktop)), and one
sitting closes the cortex-driven half with it. The same sentence had been copied into
[docs/runbooks/body-volume.md](../runbooks/body-volume.md) and is corrected there the same day.

**What is unchanged.** The Host-Windows paragraph above. The Core Audio backend, the Tauri-shell
bind and serve, and the spoken end-to-end action are OS-native, and no amount of VRAM substitutes
for a real desktop session.

## Addendum (2026-08-08): the gateway's error currency grows a kind, and the seam's status codes start carrying it

The port shipped with one untyped failure channel. `BodyGatewayError` carried a sentence and
nothing else, `GrpcBodyGateway` flattened every `AioRpcError` into it keeping only
`err.details()`, and the two built-ins on the other side each prefixed whatever came out with a
fixed lead: `could not reach the body to control volume` in `volume.py`, `could not reach the body
to capture the screen` in `screen_tool.py`. On a shipping default install that lead is **false**,
and this addendum records the measurement, the port change that fixes it, and the status-code
corrections the fix needed on the body side.

### What the model was actually told

Measured on 2026-08-08 by driving the real `GrpcBodyGateway` against a loopback `BodyService` that
answers the exact codes and sentences `body/crates/rpc/src/screen.rs` and
`body/crates/rpc/src/server.rs` write, plus a genuinely absent body. Every row is a real string a
cortex would have read:

| Failure | Code the body sent | What the model read |
| --- | --- | --- |
| Capture switched off (`CORTEX_HOST_CAPTURE` unset, **the shipping default**) | `PERMISSION_DENIED` | `could not reach the body to capture the screen: body capture_screen failed: screen capture is disabled on this host` |
| Capture too large even downscaled | `INTERNAL` | `could not reach the body to capture the screen: body capture_screen failed: the capture is too large for the seam: 41231 bytes` |
| No display (lid shut, headless) | `UNAVAILABLE` | `could not reach the body to capture the screen: body capture_screen failed: no display: lid shut` |
| Capture backend fault | `INTERNAL` | `could not reach the body to capture the screen: body capture_screen failed: screen capture backend error: BitBlt 0x2` |
| A body predating the capture slice | `UNIMPLEMENTED` | `could not reach the body to capture the screen: body capture_screen failed: screen capture lands in a later slice` |
| Wrong or missing seam token | `UNAUTHENTICATED` | `could not reach the body to capture the screen: body capture_screen failed: invalid or missing seam token` |
| Body genuinely absent | none, client synthesized | `could not reach the body to capture the screen: body capture_screen failed: Deadline Exceeded` |
| No audio endpoint | `UNAVAILABLE` | `could not reach the body to control volume: body get_volume failed: no audio endpoint: no device` |

One row out of eight is honest. In every other row the body answered, promptly and precisely, and
the model was told the opposite before being handed the truth after a colon. It is a framing
defect rather than a lost fact, which is why it waited, and the reason it stopped waiting is that
the most reachable row is the first one: an install that has never set `CORTEX_HOST_CAPTURE` gets
it on the very first capture the cortex tries.

### 1. The port's error currency is a kind, not a sentence

`BodyGatewayError` grows `kind: BodyFailure`, keyword-only, and the enum lives in the core beside
the exception. One exception type rather than a subclass tree, so every existing `except
BodyGatewayError` keeps its meaning, and a caller that wants to branch reads one attribute instead
of running an `isinstance` ladder. The kinds are a designed family, not a transcription of gRPC's
code list, and the family's structure is the journey a call takes:

| Kind | The call got as far as | The lead the core renders |
| --- | --- | --- |
| `UNREACHABLE` | nowhere: no answer arrived, whether for want of a route or of time | `could not reach the body to {action}` |
| `REFUSED` | the door: a standing policy answer, not a transient one | `the body refused to {action}` |
| `UNSUPPORTED` | the body, which has no such capability | `this body has no way to {action}` |
| `UNREADY` | the capability, whose host state is not there | `the host is not in a state to {action}` |
| `OVERSIZE` | done, and the result will not fit the seam's budget | `the body could not {action} within the size the seam allows` |
| `FAULTED` | tried, and broke | `the body failed to {action}` |

Three of the six are **absences** (`UNREACHABLE`, `UNSUPPORTED`, `UNREADY`): the thing needed to
do the work is not there, and the `un` prefix marks them as a set. Three are **events**
(`REFUSED`, `OVERSIZE`, `FAULTED`): something happened and it went a particular way. `REFUSED`
rather than `DENIED` because `DENIED_MSG` is already the core's gated-tool denial and a reader
should never have to ask which denial a name means.

`FAULTED` is the default, and the choice is deliberate. A failure nobody classified must never
claim the body was unreachable, since that claim is the defect this addendum exists to remove; it
should say the honest, uninformative thing instead. That makes the three brain-side refusals in
`_to_capture` (a reply with no image, an image the domain will not accept, a reply outside the
bound the call asked for) and the misconfigured-bound refusal land in `FAULTED` without argument:
none of them is the body being out of reach.

### 2. The adapter classifies, the core words it, and both tables are declarative

`cortex_body_client/failures.py` holds the one status-code table, split from `gateway.py` for the
same reason `status.rs` is split from `client.rs` on the body side: the classifier is the shared
thing, and the file that owns the calls stays under the cap. `cortex_core/body_failure.py` holds
the one wording table and the `body_failure_message(err, action=...)` that renders it, so the two
built-ins share a lead per kind and differ only in the infinitive they name (`capture the screen`,
`control volume`). Neither table has a code path in it. A kind added without a lead fails a test
that walks the enum, and a status code nobody classified falls to `FAULTED` rather than to a
`KeyError`.

The detail still rides after the colon, unchanged. The lead says what happened; the body's own
sentence says why, and it is the more specific of the two on every row.

### 3. A body that answered never says `UNAVAILABLE`

This is the decision that made the classification possible, and it was forced rather than chosen.
`CaptureError::NoDisplay` mapped to `Status::unavailable`, and so did `AudioError::NoEndpoint` and
`NotifyError::Unavailable`. A client-synthesized `UNAVAILABLE` from a dial that never connected is
the same code. So on the old mapping the brain could not tell *there is no body* from *the body is
here and the lid is shut*, and no amount of care on the brain side could recover the difference:
grpc-python does not tag a locally synthesized status the way tonic does, which is why
`status.rs` on the body side can walk a `source()` chain and `gateway.py` cannot.

The rule this seam now holds is that **`UNAVAILABLE` on `BodyService` means the call did not
arrive**. Nothing the body writes claims it. The three host-state failures move to
`FAILED_PRECONDITION`, which is what gRPC's own guidance reserves for a request that will keep
failing until the system state is explicitly fixed, and a shut lid or an unplugged speaker is
exactly that. `NotifyError`'s Rust variant keeps the name `Unavailable`, because it is `body_core`
vocabulary about the host rather than about gRPC, and renaming it would say less than the mapping
comment does.

The capture set was re-read whole rather than at the one variant the backlog named:

| `CaptureError` | Was | Is | Why |
| --- | --- | --- | --- |
| `NoDisplay` | `UNAVAILABLE` | `FAILED_PRECONDITION` | aliased with a dead channel; host state, fixed by opening the lid |
| `Disabled` | `PERMISSION_DENIED` | unchanged | already exact, and it is the shipping default's answer |
| `Backend` | `INTERNAL` | unchanged | a fault is a fault |
| `TooLarge` | `INTERNAL` | `RESOURCE_EXHAUSTED` | a picture that was taken and will not fit is not a broken backend |

`AudioError::NoEndpoint` and `NotifyError::Unavailable` move with `NoDisplay` for the same reason,
and they had to: the classifier is shared, so leaving volume on the old codes would have made the
same table honest for capture and lying for volume, in the very file this change is fixing the
lead in.

### 4. No proto change, verified

`proto/body.proto` is untouched. gRPC status codes are already on the wire for every call on this
seam; the whole defect was that one side never wrote an informative one and the other side never
read it. The seam's message shapes, its `MAX_RECEIVE_BYTES`, and its deadline behaviour are
unchanged, and a body built before this change still interoperates: its `UNAVAILABLE` for a shut
lid classifies as `UNREACHABLE`, which is the old sentence, so an old body degrades to exactly the
old behaviour instead of breaking.

### What the model is told now

Same harness, same codes, after the change:

| Failure | Code | What the model reads |
| --- | --- | --- |
| Capture switched off (the shipping default) | `PERMISSION_DENIED` | `the body refused to capture the screen: body capture_screen failed: screen capture is disabled on this host` |
| Capture too large even downscaled | `RESOURCE_EXHAUSTED` | `the body could not capture the screen within the size the seam allows: body capture_screen failed: the capture is too large for the seam: 41231 bytes` |
| No display | `FAILED_PRECONDITION` | `the host is not in a state to capture the screen: body capture_screen failed: no display: lid shut` |
| Capture backend fault | `INTERNAL` | `the body failed to capture the screen: body capture_screen failed: screen capture backend error: BitBlt 0x2` |
| A body predating the capture slice | `UNIMPLEMENTED` | `this body has no way to capture the screen: body capture_screen failed: screen capture lands in a later slice` |
| Wrong or missing seam token | `UNAUTHENTICATED` | `the body refused to capture the screen: body capture_screen failed: invalid or missing seam token` |
| Body genuinely absent | client synthesized | `could not reach the body to capture the screen: body capture_screen failed: Deadline Exceeded` |
| No audio endpoint | `FAILED_PRECONDITION` | `the host is not in a state to control volume: body get_volume failed: no audio endpoint: no device` |

The one honest row is still honest, and it is now the only row that claims what it claims. Its
detail reads `Deadline Exceeded` rather than a connection error because the capture call carries
one and a fresh channel retries the dial until it elapses; both codes classify the same way, which
is the reason `UNREACHABLE` is defined as *no answer arrived* rather than as *no route existed*.

**Backward compatibility, measured rather than argued.** The same harness was run once more with a
body still sending the old codes. Its `UNAVAILABLE` for a shut lid reads back as `could not reach
the body to capture the screen`, which is exactly the sentence every failure used to carry, and its
`INTERNAL` for a too-large capture reads back as `the body failed to capture the screen`. An old
body therefore degrades to the old behaviour, never to a wrong new claim.

### What was validated, and what a Windows desktop still owes

Validated here, on Linux, in this session: the classifier against every code the body can send and
against a body that is not there; the core's wording for all six kinds; the Rust mapping for every
`CaptureError`, `AudioError` and `NotifyError` variant; and, as the tie between the two toolchains,
the **real** tonic `body_service` running over loopback with `DeniedScreenCapture` (which is
literally the shipping default's backend) answered by the **real** `GrpcBodyGateway`, so the
`PERMISSION_DENIED` on the wire, the `REFUSED` kind, and the sentence the tool builds were observed
end to end across the language boundary rather than asserted on each side separately.

Not validated here, and recorded in [docs/host/index.md#windows-desktop](../host/index.md#windows-desktop): a
capture failing on a real Win32 desktop session. Every row above rides a fake or a stub backend,
because `os_linux`'s `ScreenCapture` is an `unimplemented!()` stub and this machine has no desktop
session. The rows that a real GDI backend alone can produce (`NoDisplay` from an actually shut lid,
`Backend` from a real `BitBlt` failure) have never been seen from real hardware, only constructed.

## Addendum (2026-08-22): the body's own port becomes a declaration, and the shell becomes a site

The brain's seam port has been the worked example of a coupling done right since the compose
survey: `DEFAULT_SEAM_PORT` is declared once in
`brain/packages/orchestrator/src/cortex_orchestrator/config.py`, and `scripts/crosscheck.py` holds
the compose publish, the healthcheck dial and the two Tauri modules that spend it to that one
number. The body's own port had none of it.
`body/app/src-tauri/src/body_server.rs` bound `SocketAddr::from((Ipv4Addr::LOCALHOST, 50151))` as a
bare literal inside a fallback expression, so no tree declared the value and nothing compared the
files that spell it ([R-356](../refinements/tasks/356-the-body-port-is-a-bare-literal.md)).

### One claim in the task file did not survive re-derivation

The entry says "six files spell one number and nothing compares them". Six is the number of files
the entry **enumerates**, and every one of them held. It is not the number of files that spell it:
eighteen do, outside the backlog itself. The twelve the entry does not name are the ADR you are
reading, two module contracts that quote the endpoint as an example, the body app's own contract,
four host-task files carrying it as an operator prerequisite, the gateway docstring's `host:50151`,
and three orchestrator wiring tests that set the endpoint as an env value. The count read like a
survey and was an enumeration, which is the standing warning about a task file recording what
somebody once measured rather than what the tree does now. Everything else held: the bind really
is a bare literal in a fallback, the scan really reads Rust `const`/`static` at item level, and the
brain's port really is spent by two mentions in this same crate.

The twelve are not all far sides, and sorting them is what the follow-up task is for. Three of them
are not far sides at all: a wiring test that sets `CORTEX_BODY_ENDPOINT` to a string and asserts
the composition root read it back is testing the plumbing and not the number, and would go on
passing with any port in it. The rest are unregistered on purpose for now
([R-383](../refinements/tasks/383-the-body-port-past-the-six-that-were-registered.md)).

### The constant lives in the shell, and that is the argument rather than the convenience

The port is declared as `DEFAULT_BODY_PORT` in `body/app/src-tauri/src/body_server.rs`, the module
that binds it, `cfg(windows)` like the `DEFAULT_TOAST_APP_ID` beside it, since `start` is Windows
only and an item nothing on this platform reads is a clippy failure rather than a spare constant.

The alternative was to hoist it into the gated workspace, `body_core` or `body_rpc`, where
`just check` compiles it and clippy sees it. That was declined. `body_rpc::body_service` builds a
service and never binds one; `body_core` is pure logic and OS traits. A host process's deployment
default in either of them is a value the crate declaring it has no opinion about, exported for one
consumer outside the workspace, and it would buy a compiler's opinion of a `u16` literal, which is
not the thing that can go wrong. What can go wrong is a YAML string, a runbook table cell and a
test module's fallback disagreeing with the bind, and no compiler in either toolchain can hold
those. The scan can, and the scan runs unconditionally.

**The split is real and it is the same one the entry above already lives with, upside down.** The
Tauri shell is outside `just check`: only CI's `check-shell` compiles it, and `cargo fmt --check`
is all `check-body` does to it. So this declaration is read by the cross-tree scan on every commit
and compiled by nothing on most of them. The brain's seam port has had the mirror of that since
the survey: it is declared in a tree every gate builds and spent by two mentions in this same
unbuilt crate. What makes both safe is that the scan fails closed. A declaration it cannot find is
a fault and never a skip, so a rename in the shell reddens `just check` before the compiler that
would have caught it ever runs, and the gate that reads the value runs more often than the
compiler that builds it. That is the argument for reading it here rather than the objection to it.

### What got registered, and what it is now tied to

One entry in `scripts/seamcouplings.py`, beside the brain's port and written as its mirror: one
site, the shell's declaration, and five mentions, the body override's endpoint default, the volume
runbook's bind sentence, the WSL runbook's table cell, the scheduling runbook's recipe line, and
the brain's live gateway fallback in `test_gateway_live.py`. The live test module is the second
`integration`-marked file the registry reaches and it is registered for the same reason as the
first: the suite that would notice never runs in CI.

`seamcouplings.py` is the right part rather than `shippedcouplings.py`, by that file's own test.
The question that files a coupling there is whether the far side's own code has to hold the value
for the two trees to work together, and here it does: the brain's live gateway test dials this port
when nothing names another, which is a tree's code holding a number the other tree's code declares.

### Proved able to fail, six times, over the crosscheck registry

Each place was planted with a real disagreement one at a time on the real tree, the gate run, the
file restored, and the restoration compared by digest against what it held before. The counts are
over the crosscheck registry as it stands after this change and the fixture registration landed
beside it (the ADR-0029 fixture addendum), 55 entries over 64 sites and 105 mentions, and not over
any test suite: a suite's numbers say nothing about the collection this table is about. This entry
is 1 of those entries, 1 of those sites and 5 of those mentions.

| planted drift | what the gate said |
|---|---|
| `DEFAULT_BODY_PORT` becomes `50251` | 5 faults, one per mention, which is the site being read |
| the body override dials `50251` | 1 fault naming that substitution |
| the volume runbook's bind default says `50251` | 1 fault naming that runbook |
| the WSL runbook's table cell says `50251` | 1 fault naming that runbook |
| the scheduling runbook's recipe says `50251` | 1 fault naming that runbook |
| the live gateway fallback says `50251` | 1 fault naming the test module |

All six exited 1 and all six restorations matched by digest. The first row is the one that answers
the question the placement raised: the scan does read the declaration in the ungated shell, and it
reads it as the value every other place is compared against rather than as one more far side.

### What was verified here, and the one thing that could not be

`just check-shell` ran green in the session that landed this, over the sudo-less prefix the
ADR-0011 shell-clippy addendum records: `apt-get download` of the five `-dev` roots and their
closure (131 packages here, 60.8 MB fetched), `dpkg-deb -x` into a scratch prefix outside the repo,
and `PKG_CONFIG_PATH` naming its two `pkgconfig` directories. `cargo clippy --locked --all-targets
-- -D warnings` finished in 1m 15s and exited 0.

**That is a Linux clippy, and the new constant is `cfg(windows)`, so clippy compiled it out.** The
honest reading is that the shell as a whole still lints clean and the changed item itself was not
seen by it. Clippying the shell for the Windows target does not work on this machine either: the
crate's own build script runs `tauri-winres`, which needs `llvm-rc` and panics without it, before
any Rust in the crate is read. So the item was checked in isolation instead, the same declaration
and the same bind expression compiled by `rustc -D warnings` in a standalone file, which typechecks
the `u16` against the `From<(Ipv4Addr, u16)>` the tuple goes through and prints `127.0.0.1:50151`.
That plus the unchanged shape of the edit is what stands behind it here; the Windows build on a
real desktop session is where it becomes a full measurement, as it already is for everything else
in this module.

### Records

The record is the task file
[R-356](../refinements/tasks/356-the-body-port-is-a-bare-literal.md), which closes,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it, and this
addendum. One narrower task opens in its place, the twelve other files that spell the port
([R-383](../refinements/tasks/383-the-body-port-past-the-six-that-were-registered.md)).

## Addendum (2026-08-23): the port read out of prose, and what a host file is

The port addendum above registered six files and left the other twelve sorted only by a promise
([R-383](../refinements/tasks/383-the-body-port-past-the-six-that-were-registered.md)). This is
that sort, finished. The entry goes from five far sides to twenty three, and every place outside
the decision records, the backlog and three wiring tests is now held.

### The eighteen held, and the two counts that did not

The entry's file count is right, which is worth saying after the count it corrected: eighteen files
spell the port outside the backlog, seventeen of them plus this ADR. Two smaller numbers in it are
not. It says this ADR spells the port four times; it spells it **seven**. And its framing counts
**files**, which hid the rest: the port is spelled **33 times in 17 files** outside the decision
records and the backlog, and eight of those spellings sit inside files that already carried a row.
`docs/runbooks/body-volume.md` alone spells it six times and had one row; a presence check was
satisfied by that one and would have gone on passing while the other five drifted. A file with a
row is not a file whose every spelling moved, and that is the shape both of this month's registry
tasks keep finding.

### Four shapes, and the shapes do the excluding

No needle here pins a word of the sentence around the number. Every one of the twenty three is
built from one of four things the port is written **inside**:

| shape | what it reaches | why it states |
|---|---|---|
| `default 127.0.0.1:{value}` | the bind a reader is told the body takes | wrong the moment the bind moves |
| `CORTEX_BODY_ADDR=0.0.0.0:{value}` | the export the container path needs | an instruction, not an observation |
| `host.docker.internal:{value}` | the endpoint the brain dials from a container | wrong the moment the body listens elsewhere |
| the declaring module's own doc comments | what `body_server.rs` says it binds | a module documenting a port it stopped binding |

That is what keeps the sort out of the registry's judgement and inside the text. The volume
runbook's paragraph recording that a fake `BodyService` once served on `0.0.0.0:50151` writes the
**address** and not the export, so none of the four reaches it, which is correct: it is a dated
reading of what was run, it stays true after the default moves, and history is never a far side.
The exclusion is a consequence of the shape rather than a decision applied on top of it.

Three wiring tests are out for the other reason, and the entry had this right. Each sets
`CORTEX_BODY_ENDPOINT` to a string and asserts the composition root read it back; any port would
pass, and tying a fixture to a deployment default would redden on a change that broke nothing. The
contrast with `capture_bytes.rs` is the useful one: that suite's `BRAIN_EDGE` **is** the brain's
number and was promoted to a site the same day (the ADR-0029 legibility-prose addendum), because
what it measures is meaningless at any other value. A test constant is a far side when the test is
wrong without it, and a fixture when the test is merely specific.

### The judgement call: a host file is a live instruction, not a record

The entry named this as the thing it must leave written down, and it is settled: **in**. Three
things decide it, and none of them is a preference.

`docs/host/` holds work that is **built and unrun**. Its prerequisites section opens "Sittings die
on setup. Have these before starting", which is an imperative in the present tense addressed to
somebody who has not started yet. Its own index says a completed item's file **shrinks to a
heading, its status and a pointer**, so the sentence naming a port is deleted when the sitting
finishes: the record form the reading against this was worried about is a form these sentences
never take. And the cost of being wrong is exactly the failure that section exists to prevent. An
operator who exports a stale port loses the sitting to a bind nothing dials, on a machine this repo
is not developed on, where the next attempt may be weeks away.

So `docs/host/index.md` and the three host tasks under it are far sides, along with the capture
check the legibility pair registered on the same reading. Four of the twenty three mentions and the
first four `docs/host/` files this registry holds.

### Proved able to fail, eighteen times, over the crosscheck registry

Each new place was planted with a real disagreement one at a time on the real tree, the gate run,
the file restored, and the gate re-run green. The counts are over the crosscheck registry as it
stands after this change, 56 entries over 66 sites and 139 mentions, and not over any test suite: a
suite's numbers say nothing about the collection this table is about. This entry is 1 of those
entries, 1 of those sites and 23 of those mentions.

| planted drift | what the gate said |
|---|---|
| `body_server.rs` documents a different bind | 1 fault naming the module |
| `body_server.rs` documents a different export | 1 fault naming the module |
| the override's header names a different bind | 1 fault naming the override |
| the override's header opens a different port | 1 fault naming the override |
| the override's inline comment names another | 1 fault naming the override |
| the gateway docstring's endpoint shape moves | 1 fault naming the gateway |
| the live test's run command moves | 1 fault naming the test |
| the volume runbook's first endpoint moves | 1 fault: found 1 of the 2 pinned |
| the volume runbook's first export moves | 1 fault: found 1 of the 2 pinned |
| the WSL table's endpoint moves | 1 fault naming the runbook |
| the WSL table's open bind moves | 1 fault naming the runbook |
| the host index's prerequisite moves | 1 fault naming the index |
| the bring-up task's PowerShell export moves | 1 fault naming the task |
| the volume check's prerequisite moves | 1 fault naming the task |
| the toast check's prerequisite moves | 1 fault naming the task |
| the body app contract's config list moves | 1 fault: found 1 of the 2 pinned |
| the body client contract's example moves | 1 fault naming the contract |
| the orchestrator contract's example moves | 1 fault naming the contract |

All eighteen exited 1 and all eighteen restorations returned the gate to green. Four **controls**
ran the other way and all four stayed green: the volume runbook's dated record of the address a
fake server once served on, and the three wiring tests' fixture endpoints. The two counted mentions
are what the eighth, ninth and sixteenth rows show, a file losing one of a pair reddening as loudly
as one losing both.

### What this opened

The brain's own seam port has the same gap with the roles reversed. `DEFAULT_SEAM_PORT` is held to
a compose publish, a healthcheck dial and two Tauri modules, and to no prose at all, while nine
documents state it: the same host prerequisites list, four module contracts, the overlay and WSL
runbooks. It was the worked example this port was measured against, and it is now the looser of the
two ([R-389](../refinements/tasks/389-the-brain-port-is-held-in-code-and-not-in-prose.md)).

### Records

The record is the task file
[R-383](../refinements/tasks/383-the-body-port-past-the-six-that-were-registered.md), which closes,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it,
`body/app/src-tauri/src/body_server.rs` and
[modules/body-app.md](../modules/body-app.md), whose accounts of what is tied were both stale by
this change, [modules/repo-gates.md](../modules/repo-gates.md), and this addendum.

## Addendum (2026-08-23): the brain's own port, which was loose in code as well as in prose

The addendum above closed the body's bind port and recorded that the port it had been modelled on
was now the looser of the two, held to four places of code and to no prose at all
([R-389](../refinements/tasks/389-the-brain-port-is-held-in-code-and-not-in-prose.md)). This is
that sort, finished. The entry goes from four far sides to twenty three, over twenty six spellings
in eighteen files.

### The entry was wrong about what kind of gap this was

It says nine documents state the port, and names six. It says four module contracts restate it,
and names three. Counted off the tree, the port is spelled **32 times in 19 files** outside the
decision records, the backlog and this gate's own suite, and **six** documents carry it, fourteen
times between them.

The load-bearing error is not arithmetic. The entry is titled for a port held in code and loose in
prose, and that is not what the tree looks like: **eight of the loose spellings are code**, in
files the entry never reaches. `brain/Dockerfile` declares `EXPOSE 50051`, so an image could go on
advertising a port the server had stopped binding. `body/crates/rpc/src/client.rs` carries the
endpoint as its dial example. `body/crates/rpc/tests/live.rs` states the default in its module doc
and falls back to it in `unwrap_or_else`, twice in one file. `body_server.rs` names this port in
the doc comment that explains why the body's own is different, and the body override's comment
does the same beside its own endpoint. And two `integration`-marked suites in the brain itself,
`test_schedule_live_seam.py` and `test_turn_cost_live.py`, fall back to it when no endpoint is
exported. A survey that had asked which documents were loose would have registered thirteen
spellings and left those eight, which is how an entry's own framing decides what a reader finds.

### A suite that runs on every commit holds itself

The one judgement here, and it settles a question the two earlier sorts left implicit. Three
suites spell this port, and they do not all sort the same way.

`brain/packages/orchestrator/tests/test_config.py` asserts this very default three times, in a
test named for it. It is **out**, and not because a test is a fixture: it is out because it runs
on every commit, so a retune that left it behind fails in the suite that owns the constant, and a
second gate over that drift would report a fault that cannot be silent. The two live seam suites
are **in** for the mirror of that reason. They are `integration`-marked, so they never run in CI
and run on a host only when somebody chooses to measure; a retune leaves them dialling a port
nothing listens on, and the failure surfaces weeks later worded as a server that is not answering.

That is the same line `capture_bytes.rs` was promoted to a site across, `#[ignore]`d rather than
`integration`-marked but unrun for the same reason, and it is a sharper rule than the one the body
port's sort wrote down. That one said a test constant is a far side when the test would be wrong
without it and a fixture when the test is merely specific, which is true and still needs a reader
to judge. **When the suite runs is a fact about the file.** A suite CI runs holds itself; a suite
CI does not run is held here or nowhere.

### The shapes, and the one paste that stays out

No needle pins a word of an explanation. Every one of the twenty three is built from something the
port is written inside: the stated `CORTEX_BRAIN_ADDR` default, an export a reader copies, the
endpoint a copyable snippet dials, an env table's own cell, `EXPOSE`, and a declaring or
falling-back file's own prose.

`docs/runbooks/local-dev-wsl.md` writes `port=50051` inside a fenced block of captured server
output, shown to explain that a log line carries its fields in name order. None of the shapes
reaches it, which is right: it is a paste of what one run printed, it stays true of that run after
the default moves, and it is the same exclusion the volume runbook's fake `BodyService` address
earned above.

### Proved able to fail, twenty three times, over the crosscheck registry

Each place was planted with a real disagreement one at a time on the real tree, the gate run, the
file restored from a copy taken before anything was touched, and the gate re-run green. The counts
are over the crosscheck registry as it stands after this change, 57 entries over 67 sites and 159
mentions, and not over any test suite: a suite's numbers say nothing about the collection this
table is about. This entry is 1 of those entries, 1 of those sites and 23 of those mentions.

| planted drift | what the gate said |
|---|---|
| the base compose publish moves | 1 fault naming the compose file |
| the healthcheck dial inside it moves | 1 fault naming the compose file |
| the image exposes another port | 1 fault naming the Dockerfile |
| the body override's comment names another | 1 fault naming the override |
| the Tauri seam module's endpoint moves | 1 fault naming the module |
| the Tauri converse module's endpoint moves | 1 fault naming the module |
| the body server's doc comment moves | 1 fault naming the module |
| the tonic client's dial example moves | 1 fault naming the client |
| the Rust live suite's stated default moves | 1 fault: found 1 of the 2 pinned |
| the schedule live suite's fallback moves | 1 fault naming the suite |
| the turn-cost live suite's fallback moves | 1 fault naming the suite |
| the host index's prerequisite moves | 1 fault naming the index |
| the body app contract's config list moves | 1 fault naming the contract |
| the body rpc contract's dial example moves | 1 fault: found 1 of the 2 pinned |
| the body rpc contract's paired defaults move | 1 fault naming the contract |
| the orchestrator contract's field default moves | 1 fault naming the contract |
| the orchestrator contract's endpoint moves | 1 fault naming the contract |
| the overlay runbook's prerequisite moves | 1 fault naming the runbook |
| the overlay runbook's PowerShell export moves | 1 fault naming the runbook |
| the WSL table's port row moves | 1 fault naming the runbook |
| the WSL table's endpoint row moves | 1 fault naming the runbook |
| the WSL runbook's async one-liner moves | 1 fault naming the runbook |
| the WSL runbook's health one-liner moves | 1 fault naming the runbook |

All twenty three exited 1 and all twenty three restorations returned the gate to green. Three
**controls** ran the other way and all three stayed green: the WSL runbook's captured log line
rewritten to another port, `test_config.py` rewritten to another port throughout, and this gate's
own contract rewritten so the substring defect it records reads `6006` inside `60061`. A sort that
cannot be shown to exclude anything is a sort nobody made.

### What this opened

Two things, and the second is larger than the entry that found it.

`CORTEX_SEAM_HOST` is spelled beside this port in a dozen of the templates above, and it is tied
nowhere. Its default is a pydantic field rather than a module constant, so there is no declaration
this scan can read, and the loopback address rides along inside the port's own needles as shape
([R-396](../refinements/tasks/396-the-seam-host-rides-inside-the-ports-needles.md)).

And three sorts in a row have now corrected their own count upward, by hand, and the corrections
found whole files. The registry can say that every place it names still agrees; nothing says that
it names every place. That question is answerable off the same data the scan already holds
([R-397](../refinements/tasks/397-nothing-counts-what-the-registry-does-not-name.md)).

### Records

The record is the task file
[R-389](../refinements/tasks/389-the-brain-port-is-held-in-code-and-not-in-prose.md), which closes,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it,
`brain/packages/orchestrator/src/cortex_orchestrator/config.py` and
[modules/brain-orchestrator.md](../modules/brain-orchestrator.md), whose accounts of what is tied
were both stale by this change, [modules/repo-gates.md](../modules/repo-gates.md), whose count of
counted mentions was stale by five before this change touched it, and this addendum.

## Addendum (2026-08-23): the bind host, and what a needle's own literals are

The seam port's sort recorded that `CORTEX_SEAM_HOST` rides inside a dozen of that entry's needles
as shape while nothing holds it as a value
([R-396](../refinements/tasks/396-the-seam-host-rides-inside-the-ports-needles.md)). The host is
registered now, over three places rather than twelve, and the reason for the difference is the
ruling this addendum exists for.

### The entry was wrong about which value those needles carry

Counted off the tree, `127.0.0.1` appears in **24** needles, not twelve: 18 on the brain's seam
port and 6 on the body's own listen port, which the entry never mentions. That count is the smaller
correction. The larger one is that **those digits are not one value.** They are five:

| what the digits are | where | moves when |
|---|---|---|
| the brain's own bind default | `SeamServerConfig.host` | somebody rebinds the brain |
| the body's own bind default | `DEFAULT_BODY_PORT`'s two doc comments | somebody rebinds the body |
| the `CORTEX_BRAIN_ADDR` client default | `seam.rs`, `converse.rs`, six documents | the body dials elsewhere |
| the compose publish's host-side interface | `docker/docker-compose.yml`'s `ports` | the loopback-only posture changes |
| a loopback dial | a healthcheck, two live suites, two one-liners | never; it is localhost |

The shipped stack settles it. `docker/docker-compose.yml` sets `CORTEX_SEAM_HOST: "0.0.0.0"` and
`brain/Dockerfile` says why: the in-process default is loopback and Compose binds all interfaces so
the published port can reach the server. So the container the repo ships does not run on
`127.0.0.1` at all, and the publish's `127.0.0.1` is the host machine's interface, chosen by the
security posture rather than by the server's default. Retune `SeamServerConfig.host` and **one** of
those 24 needles is stale. The entry's own prediction, twelve needles unfound at once and twelve
ports named in the fault, would have been a false red twelve times over.

### The ruling: a shadow is not a hold, and not even evidence

An incidentally-pinned value is **shadowed**. The gate does compare the digits, but three
properties keep that from being a coupling:

- The comparison runs against the **registry's own text**, not against a declaration. That makes
  the registry one more uncoupled copy of the value, which is the argument that has always kept a
  proto comment from being a master.
- It fails in **one direction only**. Move the far side and the needle is unfound; move the
  declaration and every needle goes on rendering the old digits, green.
- The fault **names the wrong constant**. This was measured rather than argued: moving the compose
  publish's host-side interface, and moving the body app contract's `CORTEX_BRAIN_ADDR` default,
  each reddened *the brain's seam port*, a value neither of them spells.

And the fourth property is the one that decides the remedy: a shadow is not evidence the value is
there. Reading those 24 needles as coverage of the loopback address would have been reading four
other values as this one. So a value gets held by getting an **entry**, and the shadow stays what
it is, a maintenance cost visible in the registry: a needle must carry enough neighbouring text to
be a claim about the right sentence, and some of that text is other people's values. What a new
entry can do, and this one does, is carry only its own value where the shape allows. The RPC
contract writes the host and the port on one line, and the two entries pay that line once each from
opposite ends, ``defaults `{value}`/`` against ``defaults `127.0.0.1`/`{value}` ``.

The hoist itself is the idiom the port beside it already lives under: `DEFAULT_SEAM_HOST` is a
module constant because a pydantic field is indented and this scan's Python declaration form is
anchored at column 0, and the comment above it says so.

### The registry took a ninth part

`seamcouplings.py` reached the 300-line cap on this entry, and the two endpoint entries had grown
into more than half of it, so they moved to `endpointcouplings.py` with the bind host joining them.
The seam that split is the one both were already written to: an endpoint is not a number two trees
compute with but a place one listens and the other dials. The move cost one import and one name in
`registry.py`, which is the fourth time that file's one-line claim has been paid rather than argued.

### Proved able to fail, seven times, over the crosscheck registry

Each place was planted with a real disagreement one at a time on the real tree, the gate run, the
file restored from a copy taken beforehand, and the gate re-run green. The counts are over the
crosscheck registry as it stands after this change, 61 entries over 71 sites and 176 mentions, and
not over any test suite: a suite's numbers say nothing about the collection this table is about.
This entry is 1 of those entries, 1 of those sites and 3 of those mentions.

| planted drift | what the gate said |
|---|---|
| `DEFAULT_SEAM_HOST` moved alone | 3 faults, one per mention, each naming its own file |
| the orchestrator contract's stated default moves | 1 fault naming the contract |
| the RPC contract's paired defaults move | 2 faults: the bind host, and the port, which shadows it |
| the WSL table's bind host row moves | 1 fault naming the runbook |
| the compose publish's host-side interface moves | 1 fault naming **the seam port**, which it is not |
| the body app contract's brain dial default moves | 1 fault naming **the seam port**, which it is not |

The first four are the entry proving able to fail, all exiting 1 and all restorations returning the
gate to green. The last three rows are the ruling above, measured: three moves of a value that is
not the seam port, each reported as the seam port, one of them alongside the correct fault. Two
**controls** ran the other way and both stayed green: the shipped `CORTEX_SEAM_HOST=0.0.0.0`
override, which is not a restatement of the default, and a wiring test exporting the host as a
fixture, which any address would pass.

### What this opened

The misattribution is the residue. A fault says a constant is not tied when what moved is a
neighbour's value sitting inside its needle, and the reader is sent to the wrong declaration. That
is answerable, by rendering a needle's literals against the registry and saying which one moved, or
by letting a template render a registered neighbour's value instead of spelling it
([R-403](../refinements/tasks/403-a-needles-literal-reddens-the-wrong-entry.md)).

### Records

The record is the task file
[R-396](../refinements/tasks/396-the-seam-host-rides-inside-the-ports-needles.md), which closes,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it,
`brain/packages/orchestrator/src/cortex_orchestrator/config.py`, which carries the hoist,
`scripts/endpointcouplings.py` and `scripts/registry.py`, which carry the split,
[modules/brain-orchestrator.md](../modules/brain-orchestrator.md), whose restatement of the field
moved with it, [AGENTS.md](../../AGENTS.md) and
[modules/repo-gates.md](../modules/repo-gates.md), whose accounts of how many parts the registry
has were both stale by this change, and this addendum.

## Addendum (2026-08-23): what an unfound needle now says about whose literal moved

The bind-host sort above measured a misattribution and left it standing: a needle is a value plus
shape, the shape is other people's text, and moving a neighbour's value reddens the entry beside it
under a fault naming a constant that did not move
([R-403](../refinements/tasks/403-a-needles-literal-reddens-the-wrong-entry.md)). This is that
fault answered. It is a message change and a new module; no registry row moved and no value changed.

### The two shapes, and why the cheap one is the only one that reaches these cases

The entry offered a better fault or a template that renders a **registered neighbour's** value, and
said to try them in that order. The order turned out not to matter, because the expensive shape
cannot reach either measured case at all. Both neighbours are unregistered **on purpose**: the sort
above counted `127.0.0.1` as five different values, held the brain's bind host and deliberately
declined the other four, one of them the compose publish's host-side interface and another the
`CORTEX_BRAIN_ADDR` client default. A template rendering a neighbour's entry can only name a
neighbour that has one, so fixing these two cases that way would first mean registering four values
the ruling had just refused, and inventing an edge between registry entries to spend them through.
The cheap shape needs neither: it reads the file it already read.

### What the fault says, and why it says the value first

`scripts/needles.py` is the mention's side of the scan, standing to a `Mention` as `values.py` and
`readings.py` stand to a `Site`. It holds `bounded()`, which moved there whole, and answers an
unfound needle with two readings.

**Whether the file still spells this constant's own value** as a token of its own. If it does, what
stopped matching is shape, and the entry the fault names is probably not the entry to change. That
is the misattribution said out loud, and it is deliberately worded as a likelihood: a file may
spell the same digits under two meanings, which is the same reason a survey by number cannot be
trusted. A mention rendering only a name spells no value at all and is told that instead.

**The longest opening run of the needle the file carries**, which pinpoints the divergence where
the needle's shape is unique to it: the body app contract's fault now quotes the run back and it
stops at `http://127.0.0.`, which is exactly where the address moved.

The run is the second half of the message rather than the first, and the reason is a surprise
worth recording. It was written first, on the assumption that the run ends at the divergence. It
does not always. A mention names a **file**, so the run is measured over the whole file, and a
prefix satisfied on some other line makes it longer than the divergence the reader means: with the
compose publish's interface moved to `0.0.0.0`, the run still reaches `"127.0.0.1:`, carried by the
**redis** publish forty lines below. The first draft's stronger claim, that a run ending before the
value proves the value did not move, was false on exactly the case this entry exists for. So the
value's own presence carries the claim, the run is worded as the most of the needle the file
carries anywhere, which is precisely what it is, and the misreading is written down here rather
than shipped as a fault that is confidently wrong.

### Proved able to fail, three times, over the crosscheck registry

Each drift was planted on the real tree one at a time, the gate run before the change and after
it, the file restored from a copy taken beforehand, and the gate re-run green. The counts are over
the crosscheck registry as it stands, 61 entries over 71 sites and 176 mentions, unchanged by this
work and not over any test suite: a suite's numbers say nothing about the collection this table is
about.

| planted drift | before | after |
|---|---|---|
| compose publish's host-side interface to `0.0.0.0` | the seam port is not tied, no more | the seam port, plus "the file does still spell `50051` as a token of its own, so what moved is likely shape this needle carries rather than this value, and the constant to change may not be the one named here" |
| body app contract's `CORTEX_BRAIN_ADDR` to `127.0.0.2` | the seam port is not tied, no more | the same clause, and a run stopping at `http://127.0.0.` |
| the image's own `EXPOSE 50051` to `50052` | the seam port is not tied, no more | "the file does not spell `50051` as a token of its own either", blaming no shape |

The first two are the misattribution the entry was filed for, still reported under the seam port
and now saying so. The third is the **control** that keeps the new clause from being a rubber
stamp: a drift where the value really is what moved must not blame a neighbour, and does not. All
three exited 1 before and after, and all three restorations returned the gate to green, at
`crosscheck OK: 61 cross-tree constant(s) under .. agree`.

### What this leaves

Two residues, both narrow and both written down. A mention with a pinned `occurrences` count that
finds **zero** still gets the old bare count message, the new reading being wired into the presence
check alone
([R-405](../refinements/tasks/405-a-counted-mention-that-finds-nothing-says-nothing.md)). And the
run overstates itself whenever another line in the same file carries a longer prefix, which is the
surprise above left as a limitation rather than papered over
([R-406](../refinements/tasks/406-the-carried-run-is-measured-over-a-whole-file.md)).

### Records

The record is the task file
[R-403](../refinements/tasks/403-a-needles-literal-reddens-the-wrong-entry.md), which closes,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it,
`scripts/needles.py`, which is the new module, `scripts/crosscheck.py`, which hands it the text it
already read, [AGENTS.md](../../AGENTS.md), whose repo map now names it, and
[modules/repo-gates.md](../modules/repo-gates.md), whose count of the modules here that have no CLI
of their own was already stale by one before this change touched it, and this addendum.
