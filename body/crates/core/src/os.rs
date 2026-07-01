//! OS-capability ports for the body, forming the first portability seam (AGENTS.md,
//! ADR-0011). Pure traits and value types here; per-platform adapters live in
//! the `os_windows` / `os_linux` / `os_macos` crates behind them.

use crate::hotkey::{HotkeyChord, Modifier};

/// A callback a [`Hotkey`] backend invokes each time the chord is pressed. It
/// fires on an OS/event-loop thread, so it is `Send` and outlives the call.
pub type HotkeyCallback = Box<dyn Fn() + Send + 'static>;

/// Why registering or resolving a global hotkey failed. See [`Hotkey`] and
/// [`Accelerator::from_chord`].
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
pub enum HotkeyError {
    /// The chord's key has no known [`KeyboardEvent.code`] mapping, so no
    /// backend can register it. `0` is the offending key (e.g. `"f99"`).
    ///
    /// [`KeyboardEvent.code`]: https://www.w3.org/TR/uievents-code/
    #[error("hotkey key `{0}` is not supported")]
    UnsupportedKey(String),
    /// The OS backend refused the registration (already taken, OS error, …).
    #[error("registering the hotkey failed: {0}")]
    Registration(String),
}

/// The port a global-hotkey backend implements (`os_windows` real; other
/// platforms are stubs until built, per ADR-0011).
pub trait Hotkey {
    /// Registers `chord` as a global hotkey, invoking `on_activate` on each
    /// press.
    fn register(&self, chord: &HotkeyChord, on_activate: HotkeyCallback)
    -> Result<(), HotkeyError>;
}

/// A hotkey chord resolved to the OS-neutral form a backend needs: the canonical modifiers plus the
/// key's [`KeyboardEvent.code`] name (e.g. `"Space"`, `"KeyA"`, `"F5"`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Accelerator {
    /// The chord's modifiers, in canonical [`Modifier`] order.
    pub modifiers: Vec<Modifier>,
    /// The `KeyboardEvent.code` name of the key.
    pub code: String,
}

impl Accelerator {
    /// Resolves a [`HotkeyChord`] to an accelerator.
    ///
    /// # Errors
    ///
    /// [`HotkeyError::UnsupportedKey`] if the chord's key has no `code` mapping.
    pub fn from_chord(chord: &HotkeyChord) -> Result<Self, HotkeyError> {
        let code = key_to_code(chord.key())
            .ok_or_else(|| HotkeyError::UnsupportedKey(chord.key().to_owned()))?;
        Ok(Self {
            modifiers: chord.modifiers().to_vec(),
            code,
        })
    }
}

/// Maps a chord's lowercase key to its `KeyboardEvent.code` name, or `None` if
/// unsupported. Letters → `KeyA`…`KeyZ`, digits → `Digit0`…`Digit9`,
/// `f1`…`f24` → `F1`…`F24`, plus a small set of named keys.
fn key_to_code(key: &str) -> Option<String> {
    if let Some(single) = single_char_code(key) {
        return Some(single);
    }
    if let Some(rest) = key.strip_prefix('f')
        && let Ok(number) = rest.parse::<u8>()
        && (1..=24).contains(&number)
    {
        return Some(format!("F{number}"));
    }
    named_code(key)
}

/// The `code` for a single-character key: a letter or a digit. The slice
/// pattern keeps both arms reachable. A single ASCII char is one byte; empty
/// or multi-byte keys take `_`. That leaves no dead branch to exclude.
fn single_char_code(key: &str) -> Option<String> {
    let ch = match key.as_bytes() {
        [byte] => *byte as char,
        _ => return None,
    };
    if ch.is_ascii_alphabetic() {
        return Some(format!("Key{}", ch.to_ascii_uppercase()));
    }
    if ch.is_ascii_digit() {
        return Some(format!("Digit{ch}"));
    }
    None
}

/// The `code` for a named key (space, enter, arrows, …), or `None`.
fn named_code(key: &str) -> Option<String> {
    let code = match key {
        "space" => "Space",
        "enter" | "return" => "Enter",
        "escape" | "esc" => "Escape",
        "tab" => "Tab",
        "backspace" => "Backspace",
        "up" => "ArrowUp",
        "down" => "ArrowDown",
        "left" => "ArrowLeft",
        "right" => "ArrowRight",
        _ => return None,
    };
    Some(String::from(code))
}
