# A safe Core Audio wrapper

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** a crate on crates.io whose public API reads and writes the default render
endpoint's master volume and mute with no `unsafe` at the call site, and which does not initialize
and uninitialize COM around each call. The second condition is what the nearest crate today fails,
and it is read off the crate's source. What such a crate would delete is listed by
`grep -n unsafe body/crates/os_windows/src/audio.rs`: four `unsafe` blocks, one `unsafe fn`, and the
module's scoped allow, six sites as of 2026-09-17.
**Verified:** 2026-09-17

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

**The nearest crate, and why it does not fire the trigger.** `volumecontrol-windows` 0.1.2
(first published 2026-03-28, last released 2026-04-02, so it existed before this entry's 2026-09-08
re-read) is a safe wrapper over `IAudioEndpointVolume`: `AudioDevice::from_default()` resolves the
default render endpoint, and `get_vol`, `set_vol`, `is_mute` and `set_mute` take `&self` with its
`unsafe` confined to its own `internal` module. Constructing the device on every call would keep
this backend's resolve-per-call behaviour, so the trigger as it was written before 2026-09-17 was
already met. Three things keep it out, read from its 0.1.2 source:

- every call runs inside a `ComGuard` that calls `CoInitializeEx(COINIT_MULTITHREADED)` and, when
  that returns `S_OK` or `S_FALSE`, `CoUninitialize` on drop. On a blocking pool thread that no
  other code has initialized, that joins and leaves the multithreaded apartment per call, which
  [R-224](224-unbalanced-com-initialization.md) names as the wrong fix for this backend's own
  imbalance;
- it depends on `windows` 0.62, where this tree's lockfile pins 0.58, so adopting it compiles a
  second `windows` major version unless the body moves first;
- its volume is a `u8` percentage, rounded on read and divided by 100 on write, where the port's
  `VolumeState::level` is an `f32` fraction, so a level set elsewhere reads back quantized to one
  percent. Windows' own volume flyout shows whole percentages, so this one is a difference rather
  than a bar.

`wasapi` 0.24.0, the widely used WASAPI crate, has no `IAudioEndpointVolume` wrapper at all.

**What would close it.** A crate meeting the trigger, adopted in `audio.rs`, its scoped allow
deleted, and the result validated on a Windows desktop the way the backend itself was.

## Trail

- 2026-09-08: Trigger rechecked and not fired. The claim that a safe crate would retire the
  exception was repaired: it would retire one of four scoped allows, not the crate-level opt-out.
  The stale three-module count was fixed in the manifest and the module doc.
- 2026-09-10: the prescribed grep was run again and every count it names is unchanged, so this
  entry now carries the date on its own field. `audio.rs` is still 113 lines with four `unsafe`
  blocks, one `unsafe fn` and one scoped allow; the four modules carrying an allow are still
  `audio`, `notify`, `screen` and `focus`; and the two levels are still `forbid` in
  `body/Cargo.toml` and `deny` in the crate's own. Nothing safe has been adopted for Core Audio:
  the crate's only dependencies under `cfg(windows)` are `body-core`, `global-hotkey` and the
  `windows` crate whose `Win32_Media_Audio` features are what the `unsafe` calls into.
- 2026-09-17: the trigger was read against crates.io rather than against this tree's manifest,
  which is the question it asks, and the entry was wrong that no such crate existed.
  `volumecontrol-windows` 0.1.2 already met the condition as written; it stays out because it
  balances COM per call, pulls `windows` 0.62 beside the pinned 0.58, and works in whole percent.
  The trigger now names the COM condition, which is the one that decides. The tree is unchanged
  since 2026-09-10: no commit touches `body/crates/os_windows` or the body manifests, `audio.rs` is
  113 lines with the same six sites, and the four modules carrying an allow are still `audio`,
  `notify`, `screen` and `focus`.
