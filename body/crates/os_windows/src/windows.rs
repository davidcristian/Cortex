//! The Windows [`Hotkey`] backend: `global-hotkey`-backed global registration.

use std::str::FromStr;
use std::thread;

use body_core::{Accelerator, Hotkey, HotkeyCallback, HotkeyChord, HotkeyError, Modifier};
use global_hotkey::hotkey::{Code, HotKey, Modifiers};
use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};

/// The Windows global-hotkey backend. Owns the OS registration for its lifetime;
/// dropping it unregisters every hotkey it holds.
pub struct WindowsHotkey {
    manager: GlobalHotKeyManager,
}

impl WindowsHotkey {
    /// Creates the backend, initializing the OS hotkey manager (which starts
    /// `global-hotkey`'s message loop).
    pub fn new() -> Result<Self, HotkeyError> {
        let manager =
            GlobalHotKeyManager::new().map_err(|e| HotkeyError::Registration(e.to_string()))?;
        Ok(Self { manager })
    }
}

impl Hotkey for WindowsHotkey {
    fn register(
        &self,
        chord: &HotkeyChord,
        on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        let accelerator = Accelerator::from_chord(chord)?;
        let hotkey = to_hotkey(&accelerator)?;
        let id = hotkey.id();
        self.manager
            .register(hotkey)
            .map_err(|e| HotkeyError::Registration(e.to_string()))?;
        spawn_listener(id, on_activate);
        Ok(())
    }
}

/// Maps a pure [`Accelerator`] to a `global-hotkey` [`HotKey`]. The accelerator's
/// `code` is a `KeyboardEvent.code` name, which [`Code`] parses directly.
fn to_hotkey(accelerator: &Accelerator) -> Result<HotKey, HotkeyError> {
    let mut modifiers = Modifiers::empty();
    for modifier in &accelerator.modifiers {
        modifiers |= to_modifiers(*modifier);
    }
    let code = Code::from_str(&accelerator.code)
        .map_err(|_| HotkeyError::UnsupportedKey(accelerator.code.clone()))?;
    Ok(HotKey::new(Some(modifiers), code))
}

/// Maps one canonical [`Modifier`] to its `global-hotkey` flag. `Super` is the OS
/// key (Windows key); if it ever fails to bind on the host, `Modifiers::META` is
/// the alternative (validated on Windows, not here).
fn to_modifiers(modifier: Modifier) -> Modifiers {
    match modifier {
        Modifier::Ctrl => Modifiers::CONTROL,
        Modifier::Alt => Modifiers::ALT,
        Modifier::Shift => Modifiers::SHIFT,
        Modifier::Super => Modifiers::SUPER,
    }
}

/// Spawns the listener that forwards each matching press to `on_activate`.
fn spawn_listener(id: u32, on_activate: HotkeyCallback) {
    thread::spawn(move || {
        let receiver = GlobalHotKeyEvent::receiver();
        while let Ok(event) = receiver.recv() {
            if event.id == id && event.state == HotKeyState::Pressed {
                on_activate();
            }
        }
    });
}
