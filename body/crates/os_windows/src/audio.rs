//! The Windows [`AudioControl`] backend: Core Audio (`IAudioEndpointVolume`) master volume.
//!
//! A thin adapter (AGENTS.md gate 3): it resolves the default render endpoint and reads/writes
//! its master scalar volume and mute, mapping each COM failure to an [`AudioError`]. Core Audio
//! is COM, so this module uses `unsafe`, which ADR-0023 authorizes narrowly for `os_windows`
//! (`Cargo.toml`'s per-crate `[lints]`); the rest of the workspace keeps `unsafe_code = forbid`.
//!
//! Host-authored and validated on Windows by the user. Like `WindowsHotkey`, it is never built
//! or measured in CI, since the whole crate is `cfg(windows)` and compiles to nothing on Linux.
//!
//! [`AudioControl`]: body_core::AudioControl
#![allow(unsafe_code)] // ADR-0023: Core Audio (IAudioEndpointVolume) is COM.

use std::ptr;

use body_core::{AudioControl, AudioError, VolumeChange, VolumeState};
use windows::Win32::Media::Audio::Endpoints::IAudioEndpointVolume;
use windows::Win32::Media::Audio::{IMMDeviceEnumerator, MMDeviceEnumerator, eConsole, eRender};
use windows::Win32::System::Com::{
    CLSCTX_ALL, COINIT_MULTITHREADED, CoCreateInstance, CoInitializeEx,
};
use windows::core::Error as WinError;

/// The Windows Core Audio volume backend. Stateless, since each call resolves the current default
/// render endpoint, so a device change between calls is picked up (the one hard rule: the body
/// server holds no state).
pub struct WindowsAudioControl;

impl WindowsAudioControl {
    /// Creates the backend.
    #[must_use]
    pub const fn new() -> Self {
        Self
    }

    /// Resolves the default render endpoint's volume interface. COM is initialized on the
    /// calling thread (idempotent, multithreaded apartment, so any async worker may call).
    /// Takes no `self`: the backend is stateless, so the lookup depends only on the OS.
    fn endpoint() -> Result<IAudioEndpointVolume, AudioError> {
        unsafe {
            // Idempotent per thread: a prior initialization returns a non-fatal status, which
            // is ignored.
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
            let enumerator: IMMDeviceEnumerator =
                CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL)
                    .map_err(|error| no_endpoint(&error))?;
            let device = enumerator
                .GetDefaultAudioEndpoint(eRender, eConsole)
                .map_err(|error| no_endpoint(&error))?;
            device
                .Activate(CLSCTX_ALL, None)
                .map_err(|error| backend(&error))
        }
    }
}

impl Default for WindowsAudioControl {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioControl for WindowsAudioControl {
    fn get_volume(&self) -> Result<VolumeState, AudioError> {
        let endpoint = Self::endpoint()?;
        unsafe { read_state(&endpoint) }
    }

    fn set_volume(&self, change: VolumeChange) -> Result<VolumeState, AudioError> {
        let endpoint = Self::endpoint()?;
        unsafe {
            if let Some(level) = change.level {
                endpoint
                    .SetMasterVolumeLevelScalar(level, ptr::null())
                    .map_err(|error| backend(&error))?;
            }
            if let Some(mute) = change.mute {
                endpoint
                    .SetMute(mute, ptr::null())
                    .map_err(|error| backend(&error))?;
            }
            read_state(&endpoint)
        }
    }
}

/// Reads the endpoint's current scalar level + mute into the core value.
///
/// # Safety
///
/// `endpoint` must be a live `IAudioEndpointVolume` from [`WindowsAudioControl::endpoint`].
unsafe fn read_state(endpoint: &IAudioEndpointVolume) -> Result<VolumeState, AudioError> {
    unsafe {
        let level = endpoint
            .GetMasterVolumeLevelScalar()
            .map_err(|error| backend(&error))?;
        let muted = endpoint
            .GetMute()
            .map_err(|error| backend(&error))?
            .as_bool();
        Ok(VolumeState { level, muted })
    }
}

/// Maps a COM failure to acquire the endpoint to `NoEndpoint`.
fn no_endpoint(error: &WinError) -> AudioError {
    AudioError::NoEndpoint(error.message())
}

/// Maps a COM failure operating the endpoint to `Backend`.
fn backend(error: &WinError) -> AudioError {
    AudioError::Backend(error.message())
}
