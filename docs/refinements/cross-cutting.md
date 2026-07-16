# Cross-cutting

This area is the ROADMAP's old catch-all list of unordered cross-cutting deferrals; it has no single origin ADR. Two ADRs are now cited inside it: [ADR-0022](../adr/ADR-0022-email-write-confirmer.md), attached to the one entry that has landed (the email-write tool), and [ADR-0023](../adr/ADR-0023-body-gateway-volume.md), the OS-action ADR where the pointer-input injection entry was decided. Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed and declined entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** richer memory policies, macOS/Linux OS backends, more subagent roles

**Cross-cutting (originally "Later, unordered"):** pointer-input injection (extend the proto
first), richer memory policies (**the email-write tool landed 2026-07-08 as Slice 8.8**,
ADR-0022), macOS/Linux OS backends, more subagent roles.

## Pointer-input injection closed 2026-07-16 as declined, dead until a consumer ([ADR-0023 addendum](../adr/ADR-0023-body-gateway-volume.md))

The entry's premise is that a text/keyboard input-injection capability exists and pointer is the
increment one level over it, needing only a proto extension for a pointer event. Read against the
tree, that premise is false at every tier, and the correction changes the outcome.

**Input injection is entirely unbuilt, not a built base with pointer missing.** `proto/body.proto`
has carried the `InjectInput` RPC and its `TypeText`/`KeyChord` messages since Slice 2, but as a
forward-looking stub beside `CaptureScreen`, not a wired capability. There is no input-injection
trait in `body_core` (`os.rs` and `lib.rs` export only `Hotkey`, `AudioControl`, `Notify`); no
Windows adapter (`os_windows` exports only `WindowsAudioControl`, `WindowsNotify`, `WindowsHotkey`);
the body server answers `inject_input` with `Status::unimplemented`, pinned by
`capture_screen_and_inject_input_are_unimplemented` in `body_server.rs`; the brain's `BodyGateway`
port carries `get_volume`/`set_volume`/`notify` and no inject method; and no built-in tool drives it
(the only OS-action tools are `GetVolumeTool`/`SetVolumeTool`). So pointer is not a small change one
level over a built base; it is part of a whole unbuilt slice ADR-0023 already defers ("`InjectInput`
comes later", "stays deferred to its slices"), and [body-gateway.md](body-gateway.md) tracks the
base `InjectInput` RPC under "remaining `BodyService` RPCs".

**No consumer, and the highest-harm OS action to ship speculatively.** Nothing drives input
injection of any kind: not the model (no tool), not the overlay (it injects nothing). Unlike volume,
which ADR-0023 chose as the first OS action because it is reversible and low-harm, a model-driven
pointer is irreversible machine control (click "OK", approve a dialog, drag a file), exactly the
capability an injection attack wants. Its gate is not free-standing: ADR-0023 makes a side-effectful
OS action safe only by being a `gated=True` audited tool that inherits the confirmer and the
tainted-turn denial, and that denial lives on the brain's tool dispatch (`dispatch.py`: a gated call
on a tainted turn returns `DENIED_MSG` and never reaches the confirmer), not on `BodyService`, whose
only guard is the seam token. Building the Windows `SendInput` adapter and wiring the server handler
ahead of that tool would let the body move the real mouse for anyone holding the seam token, shipping
the machine-control primitive ahead of the front door that would gate it. That is the same
fail-closed reasoning the GetVolume and real-file-attachment declines turned on, applied to the most
dangerous surface in the OS-action catalogue.

**Building pointer requires building the whole base, so it is a slice, not a refinement.** Pointer
cannot land one level over a base that does not exist: the InputInjector trait (text, keyboard, and
pointer, since the server dispatches the whole `oneof`), its Windows `SendInput` adapter, a new
`unsafe` authorization for `SendInput` (like the Core Audio and WinRT `unsafe` ADR-0023 scoped to
`os_windows`), the `BodyGateway` inject method, and a `gated=True` tool would all have to be built
together. That is the deferred input-injection slice, not a small refinement behind a
mostly-unchanged seam.

**Declined and moved to dead-until-a-consumer.** It reopens the day a real feature drives input
injection, and is built then as one slice: the whole InputInjector trait (text plus keyboard plus
pointer) behind one gated audited tool that inherits the confirmer and taint block, one Windows
`SendInput` adapter under a new `unsafe` authorization, and one proto pointer extension designed with
that consumer so the coordinate space (which monitor, pixels or normalized), button identity,
press/release/click, and scroll axis and delta are fixed against a real use rather than guessed into
a permanent seam wart. No code changed; the seam, the OS traits, the `BodyGateway` port, and the tool
dispatch are untouched.
