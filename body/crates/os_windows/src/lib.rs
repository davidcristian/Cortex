//! Windows OS backends for the Cortex body.
//!
//! This crate holds the **real** OS backends (unlike the `os_linux`/`os_macos` stubs): the
//! [`Hotkey`] backend over `global-hotkey` (Slice 8) and the [`AudioControl`] volume backend
//! over Core Audio (Slice 9, ADR-0023). They are host/integration-validated on Windows and
//! **never built or measured in CI** (AGENTS.md gate 3). The whole crate is `#[cfg(windows)]`:
//! on Linux it compiles to nothing, keeping the workspace green and the coverage gate blind to
//! it. Core Audio is COM, so the `audio` module uses `unsafe`, narrowly authorized for this
//! crate by ADR-0023 (see `Cargo.toml`); every other crate keeps `unsafe_code = "forbid"`.
//!
//! [`Hotkey`]: body_core::Hotkey
//! [`AudioControl`]: body_core::AudioControl

#[cfg(windows)]
mod audio;
#[cfg(windows)]
mod windows;

#[cfg(windows)]
pub use audio::WindowsAudioControl;
#[cfg(windows)]
pub use windows::WindowsHotkey;
