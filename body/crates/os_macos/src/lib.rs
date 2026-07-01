//! macOS OS backends for the Cortex body.
#![cfg_attr(coverage, feature(coverage_attribute))]

use body_core::{Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};

/// The macOS [`Hotkey`] backend is not implemented (Slice 8 is Windows-first).
pub struct MacosHotkey;

impl Hotkey for MacosHotkey {
    #[cfg_attr(coverage, coverage(off))]
    fn register(
        &self,
        _chord: &HotkeyChord,
        _on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        unimplemented!("the macOS Hotkey backend is not implemented (Slice 8 is Windows-first)")
    }
}
