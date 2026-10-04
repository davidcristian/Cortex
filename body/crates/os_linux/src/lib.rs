//! Linux OS backends for the Cortex body.
//!
//! `Notify`, `AudioControl`, `ScreenCapture` (X11 and the screenshot portal) and the X11 `Hotkey`
//! are real.
#![cfg(target_os = "linux")]

mod audio;
mod compose;
mod dbus;
mod decode;
mod exclude;
mod focus;
mod hotkey;
mod keys;
mod notify;
mod overlay;
mod pactl;
mod portal;
mod portal_dbus;
mod request;
mod screen;
mod x11;

pub use audio::{LinuxAudioControl, PactlFailure, PactlRunner};
pub use compose::{Piece, pieces};
pub use dbus::DbusNotifications;
pub use decode::{MAX_DECODED_BYTES, decode_png};
pub use hotkey::{KeyError, KeyEvent, KeyGrab, Keyboard, LinuxHotkey, keysym};
pub use keys::X11Keys;
pub use notify::{BusError, BusMessage, LinuxNotify, NotificationBus};
pub use overlay::{HiddenOverlayCapture, OVERLAY_SETTLE, OverlayWatch};
pub use pactl::{PACTL_PROGRAM, PactlCommand};
pub use portal::{
    LinuxPortalCapture, PortalError, PortalReply, ScreenshotPortal, file_path, request_path,
};
pub use portal_dbus::{DbusPortal, RESPONSE_LIMIT};
pub use screen::{
    Area, GrabError, Layer, Layout, LinuxScreenCapture, Monitor, Pixels, RootGrab, RootImage,
    Snapshot, TreeWindow,
};
pub use x11::X11Root;
/// The X11 client the capture and hotkey backends are built on. A host opens the display with it.
pub use x11rb;
/// The D-Bus client the notification and portal backends are built on. A host opens the session
/// bus with it.
pub use zbus;
