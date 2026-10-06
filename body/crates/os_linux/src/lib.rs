//! Linux OS backends for the Cortex body: `Notify`, `AudioControl`, `ScreenCapture` (X11 and the
//! screenshot and screencast portals), `Hotkey` (X11, `kglobalaccel` and the global shortcuts
//! portal) and `ClipboardPicture` (X11).
#![cfg(target_os = "linux")]

mod accel;
mod accel_dbus;
mod audio;
mod chooser;
mod clipboard;
mod compose;
mod dbus;
mod decode;
mod exclude;
mod focus;
mod gst;
mod hotkey;
mod keys;
mod notify;
mod overlay;
mod pactl;
mod portal;
mod portal_dbus;
mod request;
mod router;
mod screen;
mod screencast;
mod screencast_dbus;
mod selection;
mod shortcuts;
mod shortcuts_dbus;
mod trigger;
mod x11;

pub use accel::{AccelError, COMPONENT, GlobalAccel, LinuxKdeHotkey, Press, qt_code, qt_key};
pub use accel_dbus::{DbusGlobalAccel, kglobalaccel_running};
pub use audio::{LinuxAudioControl, PactlFailure, PactlRunner};
pub use chooser::{CHOOSER_LIMIT, HideSignal, WatchedWindowCapture};
pub use clipboard::{LinuxClipboardPicture, SelectionError, SelectionRead};
pub use compose::{Piece, pieces};
pub use dbus::DbusNotifications;
pub use decode::{MAX_DECODED_BYTES, decode_png};
pub use gst::{FRAME_LIMIT, GST_LAUNCH_PROGRAM, GstLaunch};
pub use hotkey::{KeyError, KeyEvent, KeyGrab, Keyboard, LinuxHotkey, keysym};
pub use keys::X11Keys;
pub use notify::{BusError, BusMessage, LinuxNotify, NotificationBus};
pub use overlay::{HiddenOverlayCapture, OVERLAY_SETTLE, OverlayWatch};
pub use pactl::{PACTL_PROGRAM, PactlCommand};
pub use portal::{
    LinuxPortalCapture, PortalError, PortalReply, ScreenshotPortal, file_path, request_path,
};
pub use portal_dbus::{DbusPortal, RESPONSE_LIMIT};
pub use router::TargetRouter;
pub use screen::{
    Area, GrabError, Layer, Layout, LinuxScreenCapture, Monitor, Pixels, RootGrab, RootImage,
    Snapshot, TreeWindow,
};
pub use screencast::{
    CANCELLED, CastSession, FrameError, FrameReader, LinuxWindowCapture, NO_WINDOW, RESTORE_LIMIT,
    ScreenCastPortal, Started, WINDOW_SOURCE, WindowStream, offers_window,
};
pub use screencast_dbus::DbusScreenCast;
pub use selection::{SELECTION_LIMIT, X11Selection};
pub use shortcuts::{
    Activation, Hold, LinuxPortalHotkey, REPEAT_GAP, Shortcut, ShortcutsPortal, ShortcutsReply,
};
pub use shortcuts_dbus::{DbusShortcuts, SHORTCUTS_LIMIT};
pub use trigger::{keysym_name, trigger};
pub use x11::X11Root;
/// The X11 client the capture and hotkey backends are built on. A host opens the display with it.
pub use x11rb;
/// The D-Bus client the notification and portal backends are built on. A host opens the session
/// bus with it.
pub use zbus;
