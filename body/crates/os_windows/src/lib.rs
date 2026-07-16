//! Windows OS backends for the Cortex body.
//!
//! This crate holds the **real** OS backends (unlike the `os_linux`/`os_macos` stubs): the
//! [`Hotkey`] backend over `global-hotkey` (Slice 8), the [`AudioControl`] volume backend
//! over Core Audio (Slice 9, ADR-0023), and the [`Notify`] toast backend over `WinRT`
//! (Slice 9.5, ADR-0025). They are host/integration-validated on Windows and
//! **never built or measured in CI** (AGENTS.md gate 3). The whole crate is `#[cfg(windows)]`:
//! on Linux it compiles to nothing, keeping the workspace green and the coverage gate blind to
//! it. COM needs `unsafe`, narrowly authorized for this crate by ADR-0023 (see `Cargo.toml`),
//! and used in exactly two places: the `audio` module's Core Audio calls, and the `notify`
//! module's one apartment initialization. Every other crate keeps `unsafe_code = "forbid"`.
//!
//! [`Hotkey`]: body_core::Hotkey
//! [`AudioControl`]: body_core::AudioControl
//! [`Notify`]: body_core::Notify

#[cfg(windows)]
mod audio;
#[cfg(windows)]
mod notify;
#[cfg(windows)]
mod windows;

#[cfg(windows)]
pub use audio::WindowsAudioControl;
#[cfg(windows)]
pub use notify::WindowsNotify;
#[cfg(windows)]
pub use windows::WindowsHotkey;
