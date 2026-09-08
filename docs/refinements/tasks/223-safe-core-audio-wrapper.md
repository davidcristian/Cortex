# A safe Core Audio wrapper

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** a fully-safe wrapper crate over the Core Audio volume API maturing, the way
`global-hotkey` already covers the hotkey. What such a crate would delete is listed by
`grep -n unsafe body/crates/os_windows/src/audio.rs`: four `unsafe` blocks, one `unsafe fn`, and the
module's scoped allow, six sites as of 2026-09-08. The trigger has fired when a crate can carry all
six and still resolve the default render endpoint on every call.

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

`WindowsAudioControl` uses the ADR-0023-scoped `unsafe` over the `windows` crate's COM API. The
hotkey backend needs none, because `global-hotkey` wraps the OS calls for it; a crate that did the
same for `IAudioEndpointVolume` would let the audio module drop its own.

**Re-read 2026-09-08, and the entry was wrong about what a safe crate would retire.** No such crate
has been adopted, so the trigger has not fired, and the exception it names is two things rather than
one.

**What the audio module holds today.**
[audio.rs](../../../body/crates/os_windows/src/audio.rs) is 113 lines and carries four `unsafe`
blocks and one `unsafe fn`: `endpoint` wraps `CoInitializeEx`, `CoCreateInstance`,
`GetDefaultAudioEndpoint` and `Activate` in one block; `get_volume` and `set_volume` each open one
around their call into `read_state`, with `set_volume`'s also covering
`SetMasterVolumeLevelScalar` and `SetMute`; and `read_state` is an `unsafe fn` that opens a block of
its own inside, because the crate compiles under `unsafe_op_in_unsafe_fn`. Every COM pointer is
created, used and dropped inside the one call that made it, which is what lets the body server hand
the call to an arbitrary blocking-pool thread.

**The exception is two levels, and only the lower one is audio's.** `body/Cargo.toml` sets
`unsafe_code = "forbid"` for the workspace. `body/crates/os_windows/Cargo.toml` relaxes that single
crate to `"deny"` and re-declares the other workspace lints, and four modules then re-enable
`unsafe` with a scoped `#![allow(unsafe_code)]` naming the authorization it stands on: `audio`
(Core Audio, ADR-0023), `notify` (one apartment initialization, ADR-0025), `screen` (the GDI blit
and the display-affinity call, ADR-0029), and `focus` (the Z-order walk behind a targeted capture,
ADR-0029). A safe Core Audio crate retires one of those four allows. The crate-level relaxation
stays, because three modules outside this entry's subject rest on it, and so retiring the whole
exception is not something this entry can deliver.

**Two counts were repaired the same day.** The manifest comment and
[docs/modules/body-os.md](../../modules/body-os.md) both said three modules carry a scoped allow,
a count that was right until `focus` arrived on 2026-08-10 and stale after it; `lib.rs` had already
been corrected to four. Both now say four.

**What would close it.** A crate that resolves the default render endpoint and reads and writes its
master scalar volume and mute without exposing raw COM, adopted in `audio.rs`, its scoped allow
deleted, and the result validated on a Windows desktop the way the backend itself was.

## Trail

- 2026-09-08: Trigger rechecked and not fired. The claim that a safe crate would retire the
  exception was repaired: it would retire one of four scoped allows, not the crate-level opt-out.
  The stale three-module count was fixed in the manifest and the module doc.
