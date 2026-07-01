//! Windows OS backends for the Cortex body.
//!
//! Slice 8 is Windows-first (ADR-0011, ROADMAP): this crate holds the **real**
//! [`Hotkey`] backend (unlike the `os_linux`/`os_macos` stubs). It is a thin
//! adapter over the maintained `global-hotkey` crate with real OS calls, so it is
//! host/integration-validated on Windows and **never built or measured in CI**
//! (AGENTS.md gate 3). The whole crate is `#[cfg(windows)]`: on Linux it compiles
//! to nothing, keeping the workspace green and the coverage gate blind to it.
//!
//! [`Hotkey`]: body_core::Hotkey

#[cfg(windows)]
mod windows;

#[cfg(windows)]
pub use windows::WindowsHotkey;
