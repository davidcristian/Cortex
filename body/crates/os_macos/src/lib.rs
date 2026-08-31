//! macOS OS backends for the Cortex body.
//!
//! The body targets Windows first, so every backend here is an `unimplemented!()` stub that
//! lets the workspace build. Calling one panics, so each is `#[coverage(off)]`.
#![cfg_attr(coverage, feature(coverage_attribute))]

use body_core::{
    AudioControl, AudioError, CaptureError, CaptureRequest, CapturedFrame, Hotkey, HotkeyCallback,
    HotkeyChord, HotkeyError, Notification, Notify, NotifyError, ScreenCapture, VolumeChange,
    VolumeState,
};

/// The macOS `Hotkey` backend, not implemented.
pub struct MacosHotkey;

impl Hotkey for MacosHotkey {
    #[cfg_attr(coverage, coverage(off))]
    fn register(
        &self,
        _chord: &HotkeyChord,
        _on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        unimplemented!("the macOS Hotkey backend is not implemented (this crate is Windows-first)")
    }
}

/// The macOS `AudioControl` backend, not implemented.
pub struct MacosAudioControl;

impl AudioControl for MacosAudioControl {
    #[cfg_attr(coverage, coverage(off))]
    fn get_volume(&self) -> Result<VolumeState, AudioError> {
        unimplemented!(
            "the macOS AudioControl backend is not implemented (this crate is Windows-first)"
        )
    }

    #[cfg_attr(coverage, coverage(off))]
    fn set_volume(&self, _change: VolumeChange) -> Result<VolumeState, AudioError> {
        unimplemented!(
            "the macOS AudioControl backend is not implemented (this crate is Windows-first)"
        )
    }
}

/// The macOS `Notify` backend, not implemented.
pub struct MacosNotify;

impl Notify for MacosNotify {
    #[cfg_attr(coverage, coverage(off))]
    fn show(&self, _notification: &Notification) -> Result<bool, NotifyError> {
        unimplemented!("the macOS Notify backend is not implemented (this crate is Windows-first)")
    }
}

/// The macOS `ScreenCapture` backend, not implemented.
pub struct MacosScreenCapture;

impl ScreenCapture for MacosScreenCapture {
    #[cfg_attr(coverage, coverage(off))]
    fn capture(&self, _request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        unimplemented!(
            "the macOS ScreenCapture backend is not implemented (this crate is Windows-first)"
        )
    }
}
