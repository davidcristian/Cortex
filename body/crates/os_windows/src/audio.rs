//! The Windows [`AudioControl`] backend: Core Audio (`IAudioEndpointVolume`) master volume.
#![allow(unsafe_code)] // Core Audio is a COM API.

use std::ptr;

use body_core::{AudioControl, AudioError, VolumeChange, VolumeState};
use windows::Win32::Media::Audio::Endpoints::IAudioEndpointVolume;
use windows::Win32::Media::Audio::{IMMDeviceEnumerator, MMDeviceEnumerator, eConsole, eRender};
use windows::Win32::System::Com::{
    CLSCTX_ALL, COINIT_MULTITHREADED, CoCreateInstance, CoInitializeEx,
};
use windows::core::Error as WinError;

/// The Windows Core Audio volume backend.
pub struct WindowsAudioControl;

impl WindowsAudioControl {
    /// Creates the backend.
    #[must_use]
    pub const fn new() -> Self {
        Self
    }

    /// Resolves the default render endpoint's volume interface.
    fn endpoint() -> Result<IAudioEndpointVolume, AudioError> {
        unsafe {
            // Initializing COM again on this thread returns a non-fatal status, which is ignored.
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
