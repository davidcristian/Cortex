//! Linux OS backends for the Cortex body.
//!
//! Slice 8 is Windows-first (ADR-0011, ROADMAP): this crate provides the
//! trait-satisfying `unimplemented!()` stub that lets the workspace build and
//! establishes the **coverage escape-hatch policy** (AGENTS.md gate 2). The stub
//! body is genuinely unreachable. Calling it panics; a real Linux backend is a
//! later slice, so it is `#[coverage(off)]` under `cargo llvm-cov`. Real OS
//! backends, when they land, are thin adapters validated by host/integration
//! tests, never in CI.
#![cfg_attr(coverage, feature(coverage_attribute))]

use body_core::{Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};

/// The Linux [`Hotkey`] backend is not implemented (Slice 8 is Windows-first).
pub struct LinuxHotkey;

impl Hotkey for LinuxHotkey {
    #[cfg_attr(coverage, coverage(off))]
    fn register(
        &self,
        _chord: &HotkeyChord,
        _on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        unimplemented!("the Linux Hotkey backend is not implemented (Slice 8 is Windows-first)")
    }
}
