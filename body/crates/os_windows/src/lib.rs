//! Windows OS backends for the Cortex body.

#[cfg(windows)]
mod audio;
#[cfg(windows)]
mod focus;
#[cfg(windows)]
mod notify;
#[cfg(windows)]
mod screen;
#[cfg(windows)]
mod windows;

#[cfg(windows)]
pub use audio::WindowsAudioControl;
#[cfg(windows)]
pub use notify::WindowsNotify;
#[cfg(windows)]
pub use screen::{WindowsScreenCapture, exclude_from_capture};
#[cfg(windows)]
pub use windows::WindowsHotkey;
