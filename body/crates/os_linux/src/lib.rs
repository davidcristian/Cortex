//! Linux OS backends for the Cortex body.
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
