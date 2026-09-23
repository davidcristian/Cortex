# Pointer-input injection

**Status:** declined 2026-07-16
**Area:** cross-cutting
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

The entry assumed that a text and keyboard input-injection capability exists and that pointer is
one step beyond it, needing only a proto extension. Read against the tree, that is false at every
level.

Input injection is entirely unbuilt. `proto/body.proto` has had the `InjectInput` RPC and its
`TypeText` and `KeyChord` messages since Slice 2, but as a placeholder beside `CaptureScreen`.
There is no input-injection trait in `body_core` (`os.rs` and `lib.rs` export only `Hotkey`,
`AudioControl`, `Notify`); no Windows adapter (`os_windows` exports only `WindowsAudioControl`,
`WindowsNotify`, `WindowsHotkey`); the body server answers `inject_input` with
`Status::unimplemented`, asserted by a test in `body_server.rs`; the brain's `BodyGateway` port has
`get_volume`, `set_volume` and `notify` and no inject method; and no built-in tool drives it. So
pointer is part of a whole unbuilt slice ADR-0023 already defers, tracked in
[body-gateway.md](../index.md#body-gateway) under the remaining `BodyService` RPCs.

There is no consumer, and this is the highest-harm OS action to ship speculatively. Nothing drives
input injection of any kind: not the model, which has no tool, and not the overlay. Unlike volume,
which ADR-0023 chose as the first OS action because it is reversible and low-harm, a model-driven
pointer is irreversible machine control (click "OK", approve a dialog, drag a file), exactly what
an injection attack wants. Its confirmation is not separate: ADR-0023 makes a side-effectful
OS action safe only by being a `confirm_required=True` audited tool that inherits the confirmer and the
tainted-turn denial, and that denial lives on the brain's tool dispatch (`dispatch.py`), not on
`BodyService`, whose only protection is the transport token. Building the Windows `SendInput`
adapter and wiring the server handler ahead of that tool would let the body move the real mouse for
anyone holding that token.

Building pointer therefore means building the whole base, which is a slice and not a refinement:
the `InputInjector` trait (text, keyboard and pointer, since the server dispatches the whole
`oneof`), its Windows `SendInput` adapter, a new `unsafe` authorization for `SendInput`, the
`BodyGateway` inject method, and a confirmed tool.

It reopens the day a real feature drives input injection, and is built then as one slice, with the
proto pointer extension designed together with that consumer so the coordinate space (which
monitor, pixels or normalized), button identity, press, release and click, and scroll axis and
delta are fixed against a real use rather than guessed into a permanent flaw on the wire. No code
changed.

## History

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as the first clause of the
  "Later, unordered" list, where it read "pointer-input injection (extend the proto first)".
- 2026-07-16: Declined for want of a consumer, sharpened by being the highest-harm OS action, and
  recorded at ADR-0023, now its decision 13.
- 2026-07-18: Corrected by the vision slice (ADR-0029), which built the `CaptureScreen` half of the
  placeholder pair this entry stood beside and renamed the Rust test from
  `capture_screen_and_inject_input_are_unimplemented` to `inject_input_is_unimplemented`. The
  reasoning is unaffected, since input injection still has no trait, no adapter, no confirmed tool
  and no consumer.
