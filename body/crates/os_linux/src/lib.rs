//! Linux OS backends for the Cortex body.
//!
//! `Notify`, `AudioControl` and `ScreenCapture` are real. `Hotkey` is an `unimplemented!()` stub,
//! which panics when called, so it is `#[coverage(off)]`.
#![cfg(target_os = "linux")]
#![cfg_attr(coverage, feature(coverage_attribute))]

mod audio;
mod dbus;
mod notify;
mod pactl;
mod screen;
mod x11;

pub use audio::{LinuxAudioControl, PactlFailure, PactlRunner};
pub use dbus::DbusNotifications;
pub use notify::{BusError, BusMessage, LinuxNotify, NotificationBus};
pub use pactl::{PACTL_PROGRAM, PactlCommand};
pub use screen::{GrabError, LinuxScreenCapture, RootGrab, RootImage};
pub use x11::X11Root;
/// The X11 client the capture backend is built on. A host opens the display with it.
pub use x11rb;
/// The D-Bus client the notification backend is built on. A host opens the session bus with it.
pub use zbus;

use body_core::{Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};

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
