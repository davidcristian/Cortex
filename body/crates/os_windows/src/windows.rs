//! The Windows [`Hotkey`] backend: `global-hotkey`-backed global registration.
//!
//! A thin adapter (AGENTS.md gate 3): it resolves a [`HotkeyChord`] to a pure
//! [`Accelerator`] (in `body_core`), maps that to `global-hotkey`'s
//! `Modifiers`/`Code`, registers it, and forwards each press to the callback.
//!
//! On Windows, `global-hotkey` owns a hidden message-only window on its own
//! thread and delivers presses on a process-global channel, so the backend reads
//! that channel from a listener thread and never couples to Tauri's event loop,
//! which is the ADR-0011 risk the `Hotkey` port was designed to absorb.
//! `global-hotkey` keeps `unsafe` out of this crate's own code.

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
    ///
    /// # Errors
    ///
    /// [`HotkeyError::Registration`] if the OS manager cannot be created.
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
/// key, the Windows key. If it ever fails to bind on the host, `Modifiers::META`
/// is the alternative, which only a Windows host can confirm.
fn to_modifiers(modifier: Modifier) -> Modifiers {
    match modifier {
        Modifier::Ctrl => Modifiers::CONTROL,
        Modifier::Alt => Modifiers::ALT,
        Modifier::Shift => Modifiers::SHIFT,
        Modifier::Super => Modifiers::SUPER,
    }
}

/// Spawns the listener that forwards each matching press to `on_activate`.
/// `global-hotkey` publishes every hotkey's events on one process-global channel,
/// so the listener filters to this hotkey's `id` and the pressed edge. The thread
/// ends when the channel closes at process teardown.
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
