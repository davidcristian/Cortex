//! Windows OS backends for the Cortex body.
//!
//! This crate holds the real OS backends, where `os_linux` and `os_macos` hold stubs: the
//! [`Hotkey`] backend over `global-hotkey`, the [`AudioControl`] volume backend
//! over Core Audio (ADR-0023), the [`Notify`] toast backend over `WinRT`
//! (ADR-0025), and the [`ScreenCapture`] backend over GDI (ADR-0029).
//! They are host and integration validated on Windows and are never built or measured in CI
//! (AGENTS.md gate 3). The whole crate is `#[cfg(windows)]`:
//! on Linux it compiles to nothing, keeping the workspace green and the coverage gate blind to
//! it. Raw OS calls need `unsafe`, narrowly authorized for this crate (see `Cargo.toml`) and
//! used in exactly four modules, each with its own scoped allow and its own authorization:
//! the `audio` module's Core Audio calls (ADR-0023), the `notify` module's one apartment
//! initialization (ADR-0025), the `screen` module's GDI blit plus the overlay's
//! capture self-exclusion, and the `focus` module's Z-order walk, which is how a targeted
//! capture finds the window the user is looking at (both ADR-0029). Every other crate keeps
//! `unsafe_code = "forbid"`.
//!
//! [`Hotkey`]: body_core::Hotkey
//! [`AudioControl`]: body_core::AudioControl
//! [`Notify`]: body_core::Notify
//! [`ScreenCapture`]: body_core::ScreenCapture

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
