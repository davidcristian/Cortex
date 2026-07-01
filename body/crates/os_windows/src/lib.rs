//! Windows OS backends for the Cortex body.

#[cfg(windows)]
mod windows;

#[cfg(windows)]
pub use windows::WindowsHotkey;
