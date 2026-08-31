//! Linux OS backends for the Cortex body.
//!
//! this crate is Windows-first (ADR-0011, ROADMAP), so this crate provides the trait-satisfying
//! `unimplemented!()` stubs that let the workspace build, and it is where the coverage
//! escape-hatch policy is set (AGENTS.md gate 2). Each stub body is unreachable: calling it
//! panics, and a real Linux backend is a later slice, so each is `#[coverage(off)]` under
//! `cargo llvm-cov`. Real OS backends, when they land, are thin adapters validated by host and
//! integration tests, never in CI.
#![cfg_attr(coverage, feature(coverage_attribute))]

use body_core::{
    AudioControl, AudioError, CaptureError, CaptureRequest, CapturedFrame, Hotkey, HotkeyCallback,
    HotkeyChord, HotkeyError, Notification, Notify, NotifyError, ScreenCapture, VolumeChange,
    VolumeState,
};

/// The Linux [`Hotkey`] backend is not implemented (this crate is Windows-first).
pub struct LinuxHotkey;

impl Hotkey for LinuxHotkey {
    #[cfg_attr(coverage, coverage(off))]
    fn register(
        &self,
        _chord: &HotkeyChord,
        _on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        unimplemented!("the Linux Hotkey backend is not implemented (this crate is Windows-first)")
    }
}

/// The Linux [`AudioControl`] backend is not implemented (this crate is Windows-first).
pub struct LinuxAudioControl;

impl AudioControl for LinuxAudioControl {
    #[cfg_attr(coverage, coverage(off))]
    fn get_volume(&self) -> Result<VolumeState, AudioError> {
        unimplemented!(
            "the Linux AudioControl backend is not implemented (this crate is Windows-first)"
        )
    }

    #[cfg_attr(coverage, coverage(off))]
    fn set_volume(&self, _change: VolumeChange) -> Result<VolumeState, AudioError> {
        unimplemented!(
            "the Linux AudioControl backend is not implemented (this crate is Windows-first)"
        )
    }
}

/// The Linux [`Notify`] backend is not implemented (this crate is Windows-first).
pub struct LinuxNotify;

impl Notify for LinuxNotify {
    #[cfg_attr(coverage, coverage(off))]
    fn show(&self, _notification: &Notification) -> Result<bool, NotifyError> {
        unimplemented!("the Linux Notify backend is not implemented (this crate is Windows-first)")
    }
}

/// The Linux [`ScreenCapture`] backend is not implemented (this crate is Windows-first).
pub struct LinuxScreenCapture;

impl ScreenCapture for LinuxScreenCapture {
    #[cfg_attr(coverage, coverage(off))]
    fn capture(&self, _request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        unimplemented!(
            "the Linux ScreenCapture backend is not implemented (this crate is Windows-first)"
        )
    }
}
