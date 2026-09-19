# The `InjectInput` RPC, the last unbuilt `BodyService` RPC

**Status:** open, waiting for a consumer
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** A real consumer for input injection, built then as one slice, not as a wired handler.
**Verified:** 2026-09-19

`InjectInput` is the only one of the five RPCs `BodyService` declares that is not built. It is
unbuilt at every tier: the RPC and its `TypeText` and `KeyChord` messages are forward-looking
declarations, there is no input trait in `body_core`, no `os_windows` adapter, the body server
answers `inject_input` with `Status::unimplemented`, the brain's `BodyGateway` has no inject method,
and no tool drives it. It reopens with its consumer as one slice rather than as a wired handler
waiting for the confirmation that would make it safe.

It stays a refinement rather than moving to [docs/host/](../../host/index.md): the proto field, the
core trait, the gateway method, the fake and its contract test are all reachable and covered here,
and only the real `SendInput` adapter and its validation need a Win32 desktop session.

## History

- 2026-07-18: `CaptureScreen` closed with the vision slice
  ([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)), leaving `InjectInput` alone in the
  entry it was grouped into. On that half the "behind the same interface" estimate proved wrong, at
  five proto fields plus a new brain-side port method returning a new pure-core value.
- 2026-07-19: Given its own line in the index's dead-until-a-consumer list, where it had been
  counted since the extraction but never placed.
- 2026-09-13: Checked against all five tiers and every one still reads as the 2026-07-19 note
  recorded it. The RPC and its messages are declarations only
  ([proto/body.proto](../../../proto/body.proto) lines 282 and 369 to 377);
  `body/crates/core/src/os/` holds `notify` and the four screen modules; `os_windows` has no input
  adapter; `body/crates/rpc/src/server.rs:121` still answers `Status::unimplemented`; and the
  brain's gateway (`brain/packages/body_client/src/cortex_body_client/gateway.py`) exposes
  `get_volume`, `set_volume`, `notify` and `capture_screen`.
- 2026-09-19: Checked again, and the 2026-09-13 reading holds line for line. No code under `body/`,
  `brain/` or `proto/` mentions `SendInput`, and no tool or surface asks to type or press a key
  combination, so the trigger has not fired. [270](270-pointer-input-injection.md) is declined, and
  the two feature-breadth entries that mention input injection
  ([271](271-macos-linux-os-backends.md), [272](272-more-subagent-roles.md)) wait on nothing here.
