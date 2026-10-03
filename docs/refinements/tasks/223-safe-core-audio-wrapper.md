# A safe Core Audio wrapper

**Status:** open, waiting for its trigger
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** either of two. Task 224's dedicated COM thread being built, after which
`volumecontrol-windows`, the nearest crate below, would run its per-call guard on a thread that
already holds an initialization; or a crate on crates.io whose public API reads and writes the
default render endpoint's master volume and mute with no `unsafe` at the call site, returns a
missing endpoint as an error value rather than a panic, and does not initialize and uninitialize
COM around each call. The candidates are listed by `https://crates.io/api/v1/crates?q=volume%20control`
and each is read off its source. What such a crate would delete is listed by
`grep -n unsafe body/crates/os_windows/src/audio.rs`: four `unsafe` blocks, one `unsafe fn`, and the
module's scoped allow, six sites as of 2026-10-03.
**Verified:** 2026-10-03

`WindowsAudioControl` uses `unsafe` over the `windows` crate's COM API, authorized by ADR-0023. The
hotkey backend needs none, because `global-hotkey` wraps the OS calls for it; a crate that did the
same for `IAudioEndpointVolume` would let the audio module drop its own.

[audio.rs](../../../body/crates/os_windows/src/audio.rs) is 98 lines with four `unsafe` blocks and
one `unsafe fn`: `endpoint` wraps `CoInitializeEx`, `CoCreateInstance`, `GetDefaultAudioEndpoint`
and `Activate` in one block; `get_volume` and `set_volume` each open one around their call into
`read_state`, with `set_volume`'s also covering `SetMasterVolumeLevelScalar` and `SetMute`; and
`read_state` is an `unsafe fn` that opens a block of its own inside, because the crate compiles
under `unsafe_op_in_unsafe_fn`. Every COM pointer is created, used and dropped inside the one call
that made it, which is what lets the body server hand the call to an arbitrary blocking-pool thread.

The exception is two levels, and only the lower one belongs to audio. `body/Cargo.toml` sets
`unsafe_code = "forbid"` for the workspace. `body/crates/os_windows/Cargo.toml` relaxes that single
crate to `"deny"`, and four modules then re-enable `unsafe` with a scoped `#![allow(unsafe_code)]`
whose comment names the API that needs it. Each rests on a decision record: `audio` (Core Audio,
ADR-0023), `notify` (one apartment initialization, ADR-0025), `screen` (the GDI blit and the
display-affinity call, ADR-0029), and `focus` (the Z-order walk behind a targeted capture,
ADR-0029). A safe Core Audio crate retires one
of those four allows, not the crate-level relaxation, which three other modules rest on.

The nearest crate is `volumecontrol-windows` 0.1.2, a safe wrapper over `IAudioEndpointVolume` whose
`unsafe` is confined to its own `internal` module. It was first published on 2026-03-28 and last
released on 2026-04-02, so it already existed when this entry was read again on 2026-09-08. Three
things keep it out, read from its source:

- every call runs inside a `ComGuard` that calls `CoInitializeEx(COINIT_MULTITHREADED)` and, when
  that returns `S_OK` or `S_FALSE`, `CoUninitialize` on drop. On a blocking pool thread that no
  other code has initialized, that joins and leaves the multithreaded apartment per call, which
  [R-224](224-unbalanced-com-initialization.md) names as the wrong fix for this backend's own
  imbalance. On a thread that already holds an initialization, such as the dedicated thread R-224
  proposes, the same guard is harmless: its `CoInitializeEx` returns `S_FALSE`, which it balances
  with one `CoUninitialize`, and Microsoft documents that pair as a reference count rather than a
  teardown;
- it depends on `windows` 0.62. `os_windows` uses 0.58 and the Tauri stack (`tauri`, `tao`, `wry`,
  `webview2-com`) uses 0.61.3, so the shell's lockfile already holds two versions and adopting it
  would add a third ([R-780](780-os-windows-builds-a-second-windows-crate.md));
- its volume is a `u8` percentage, rounded on read and divided by 100 on write, where the port's
  `VolumeState::level` is an `f32` fraction, so a level set elsewhere reads back rounded to one
  percent. Windows' own volume flyout shows whole percentages, so this one is a difference rather
  than a blocker.

`cpvc` 0.6.0, released on 2026-04-01 and wrapped by `volume-control` 0.1.0, passes the `unsafe` and
COM conditions: its public `wasapi` module's `get_vol` and `set_vol` are safe, return a
`Result<f32, _>`, and never uninitialize COM. It stays out for three reasons: it calls `unwrap()` on
`GetDefaultAudioEndpoint`, so a machine with no render endpoint panics where the port expects
`AudioError::NoEndpoint`; it averages and sets the per-channel scalars rather than the master one;
and its per-call `CoInitializeEx` has no matching `CoUninitialize`, the imbalance R-224 records for
this tree.

`wasapi` 0.24.0, the widely used WASAPI crate, has no `IAudioEndpointVolume` wrapper at all. Two
older crates fail the first condition: `windows-volume-control` 0.1.1 and `winmix` 0.1.3 both
expose their volume calls as `pub unsafe fn`, and `winmix` sets per-application session volume
rather than the endpoint's.

Closing this means a crate meeting the trigger, adopted in `audio.rs`, its scoped allow deleted, and
the result checked on a Windows desktop the way the backend itself was.

## History

- 2026-09-08: Trigger rechecked and not fired. The claim that a safe crate would retire the
  exception was repaired: it would retire one of four scoped allows, not the crate-level opt-out. A
  stale three-module count was fixed in the manifest comment and
  [docs/modules/body-os.md](../../modules/body-os.md), both of which were right until `focus`
  arrived on 2026-08-10.
- 2026-09-10: The grep was run again and every count is unchanged. Nothing safe has been adopted for
  Core Audio: the crate's only dependencies under `cfg(windows)` are `body-core`, `global-hotkey`
  and the `windows` crate.
- 2026-09-17: The trigger was read against crates.io rather than against this tree's manifest, which
  is the question it asks, and the entry was wrong that no such crate existed.
  `volumecontrol-windows` 0.1.2 already met the condition as written; it stays out for the three
  reasons above. The trigger now names the COM condition, which is the one that decides. The tree is
  unchanged since 2026-09-10.
- 2026-09-24: Not fired. On crates.io `volumecontrol-windows` is still at 0.1.2, searches for
  endpoint volume crates found none released since 2026-09-17, and the two older ones above that the
  entry had not named fail on `unsafe`. No commit since 2026-09-17 touches `body/crates/os_windows`
  and the six sites are unchanged. One correction: `audio.rs` is 98 lines, not 113.
- 2026-10-03: Not fired. On crates.io `volumecontrol-windows` is still 0.1.2, and its guard, read
  from the 0.1.2 source, does balance an `S_FALSE` initialization. Three corrections: `cpvc` 0.6.0,
  not named before, passes both stated COM and `unsafe` conditions yet panics on a missing
  endpoint, so the trigger now also asks for an error value, and it names the R-224 route; the
  shell already builds two `windows` versions, filed as R-780; and the scoped allows name their API,
  not their decision record. The six sites in `audio.rs` are unchanged.
