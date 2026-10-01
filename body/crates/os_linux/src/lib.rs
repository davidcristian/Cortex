//! Linux OS backends for the Cortex body.
//!
//! `Notify`, `AudioControl`, `ScreenCapture` and the X11 `Hotkey` are real.
#![cfg(target_os = "linux")]

mod audio;
mod compose;
mod dbus;
mod exclude;
mod hotkey;
mod keys;
mod notify;
mod pactl;
mod screen;
mod x11;

pub use audio::{LinuxAudioControl, PactlFailure, PactlRunner};
pub use compose::{Piece, pieces};
pub use dbus::DbusNotifications;
pub use hotkey::{KeyError, KeyEvent, KeyGrab, Keyboard, LinuxHotkey, keysym};
pub use keys::X11Keys;
pub use notify::{BusError, BusMessage, LinuxNotify, NotificationBus};
pub use pactl::{PACTL_PROGRAM, PactlCommand};
pub use screen::{
    Area, GrabError, Layer, Layout, LinuxScreenCapture, Monitor, RootGrab, RootImage, Snapshot,
    TreeWindow,
};
pub use x11::X11Root;
/// The X11 client the capture and hotkey backends are built on. A host opens the display with it.
pub use x11rb;
/// The D-Bus client the notification backend is built on. A host opens the session bus with it.
pub use zbus;
