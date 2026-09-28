//! Linux OS backends for the Cortex body.
//!
//! `Notify` and `AudioControl` are real. `Hotkey` and `ScreenCapture` are `unimplemented!()`
//! stubs, which panic when called, so each is `#[coverage(off)]`.
#![cfg(target_os = "linux")]
#![cfg_attr(coverage, feature(coverage_attribute))]

mod audio;
mod dbus;
mod notify;
mod pactl;

pub use audio::{LinuxAudioControl, PactlFailure, PactlRunner};
pub use dbus::DbusNotifications;
pub use notify::{BusError, BusMessage, LinuxNotify, NotificationBus};
pub use pactl::{PACTL_PROGRAM, PactlCommand};
/// The D-Bus client the notification backend is built on. A host opens the session bus with it.
pub use zbus;

use body_core::{
    CaptureError, CaptureRequest, CapturedFrame, Hotkey, HotkeyCallback, HotkeyChord, HotkeyError,
    ScreenCapture,
};

/// The Linux `Hotkey` backend, not implemented.
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

/// The Linux `ScreenCapture` backend, not implemented.
pub struct LinuxScreenCapture;

impl ScreenCapture for LinuxScreenCapture {
    #[cfg_attr(coverage, coverage(off))]
    fn capture(&self, _request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        unimplemented!(
            "the Linux ScreenCapture backend is not implemented (this crate is Windows-first)"
        )
    }
}
