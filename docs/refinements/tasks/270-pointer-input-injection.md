# Pointer-input injection

**Status:** declined 2026-07-16
**Area:** cross-cutting
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

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
comes later", "stays deferred to its slices"), and [body-gateway.md](../index.md#body-gateway) tracks the
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
ahead of that tool would let the body move the real mouse for anyone holding the seam token,
shipping the machine-control primitive ahead of the tool dispatch that would gate it. That is the
same fail-closed reasoning the GetVolume and real-file-attachment declines turned on, applied to the
most dangerous surface in the OS-action catalogue.

**Building pointer requires building the whole base, so it is a slice, not a refinement.** Pointer
cannot land one level over a base that does not exist: the InputInjector trait (text, keyboard, and
pointer, since the server dispatches the whole `oneof`), its Windows `SendInput` adapter, a new
`unsafe` authorization for `SendInput` (like the Core Audio and WinRT `unsafe` ADR-0023 scoped to
`os_windows`), the `BodyGateway` inject method, and a `gated=True` tool would all have to be built
together. That is the deferred input-injection slice, not a small refinement behind a
mostly-unchanged seam.

**Correction 2026-07-18: the `CaptureScreen` half of the premise is no longer true.** This entry
reads `CaptureScreen` and `InjectInput` as one pair of forward-looking stubs. The vision slice
(ADR-0029) built the capture half: `body_core` has a `ScreenCapture` port with its whole size
policy, `os_windows` gains a GDI backend, and the body answers the RPC for real. The reasoning
above is unaffected, because it turns on input injection having no trait, no adapter, no gated
tool, and no consumer, all of which still hold; only the stub the entry stood beside has moved.
The Rust pin it names, `capture_screen_and_inject_input_are_unimplemented`, is now
`inject_input_is_unimplemented`.

**Declined and moved to dead-until-a-consumer.** It reopens the day a real feature drives input
injection, and is built then as one slice: the whole InputInjector trait (text plus keyboard plus
pointer) behind one gated audited tool that inherits the confirmer and taint block, one Windows
`SendInput` adapter under a new `unsafe` authorization, and one proto pointer extension designed
with that consumer so the coordinate space (which monitor, pixels or normalized), button identity,
press/release/click, and scroll axis and delta are fixed against a real use rather than guessed into
a permanent flaw in the seam. No code changed; the seam, the OS traits, the `BodyGateway` port, and
the tool dispatch are untouched.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as the first clause of the
  "Later, unordered" list, where it read "pointer-input injection (extend the proto first)".
- 2026-07-16: Closed as declined, dead until a consumer, on the evidence rather than on the entry's
  own cost estimate, and recorded at the ADR-0023 pointer-input addendum as the last of that ADR's
  `InjectInput` deferrals to be triaged. It declines on the same want-of-a-consumer test the day's
  other declines used, sharpened by being the highest-harm OS action, and it took the area from 4
  open to 3 as the first cross-cutting entry to close since the extraction. The index's ledger of
  that close also recorded it as the entry whose premise the tree contradicted most sharply.
- 2026-07-18: Corrected by the vision slice (ADR-0029), which built the `CaptureScreen` half of the
  stub pair this entry stood beside and renamed the Rust pin the entry names from
  `capture_screen_and_inject_input_are_unimplemented` to `inject_input_is_unimplemented`. The
  reasoning is unaffected, since input injection still has no trait, no adapter, no gated tool and
  no consumer.
