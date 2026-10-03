//! `FakeHotkey`, the one stand-in `Hotkey` backend every body test uses.

use std::cell::RefCell;

use body_core::{Accelerator, Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};

/// A `Hotkey` that keeps each registered callback until [`FakeHotkey::press`], or refuses all.
#[derive(Default)]
pub struct FakeHotkey {
    refusal: Option<HotkeyError>,
    bindings: RefCell<Vec<(HotkeyChord, HotkeyCallback)>>,
}

impl FakeHotkey {
    /// A backend that refuses every chord it can resolve with `error`.
    #[must_use]
    pub fn failing(error: HotkeyError) -> Self {
        Self {
            refusal: Some(error),
            ..Self::default()
        }
    }

    /// Presses `chord` once, running every callback registered for it.
    pub fn press(&self, chord: &HotkeyChord) {
        for (bound, on_activate) in self.bindings.borrow().iter() {
            if bound == chord {
                on_activate();
            }
        }
    }
}

impl Hotkey for FakeHotkey {
    fn register(
        &self,
        chord: &HotkeyChord,
        on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        Accelerator::from_chord(chord)?;
        if let Some(error) = &self.refusal {
            return Err(error.clone());
        }
        self.bindings
            .borrow_mut()
            .push((chord.clone(), on_activate));
        Ok(())
    }
}
