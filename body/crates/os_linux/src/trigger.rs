//! The XDG shortcuts form of a chord, which the `GlobalShortcuts` portal reads as a trigger.

use body_core::{Accelerator, HotkeyChord, HotkeyError, Modifier};

/// The trigger a chord asks for, in the XDG shortcuts form: modifiers, then the key's keysym name.
///
/// # Errors
///
/// [`HotkeyError::UnsupportedKey`] when the chord's key has no code or no keysym name here.
pub fn trigger(chord: &HotkeyChord) -> Result<String, HotkeyError> {
    let key = key(chord)?;
    let mut parts: Vec<&str> = chord
        .modifiers()
        .iter()
        .map(|&each| modifier(each))
        .collect();
    parts.push(&key);
    Ok(parts.join("+"))
}

/// The keysym name of a chord's key, or [`HotkeyError::UnsupportedKey`].
fn key(chord: &HotkeyChord) -> Result<String, HotkeyError> {
    let code = Accelerator::from_chord(chord)?.code;
    keysym_name(&code).ok_or(HotkeyError::UnsupportedKey(code))
}

/// The modifier's name in the XDG shortcuts form.
const fn modifier(modifier: Modifier) -> &'static str {
    match modifier {
        Modifier::Ctrl => "CTRL",
        Modifier::Alt => "ALT",
        Modifier::Shift => "SHIFT",
        Modifier::Super => "LOGO",
    }
}

/// The xkb keysym name of a `KeyboardEvent.code` name, or `None` for a code with none here.
#[must_use]
pub fn keysym_name(code: &str) -> Option<String> {
    let named = match code {
        "Space" => "space",
        "Enter" => "Return",
        "Escape" => "Escape",
        "Tab" => "Tab",
        "Backspace" => "BackSpace",
        "ArrowUp" => "Up",
        "ArrowDown" => "Down",
        "ArrowLeft" => "Left",
        "ArrowRight" => "Right",
        _ => return printable(code),
    };
    Some(String::from(named))
}

/// The keysym name of a letter, digit or function key code: `KeyA` is `a`, `Digit1` is `1`.
fn printable(code: &str) -> Option<String> {
    match code.as_bytes() {
        [b'K', b'e', b'y', letter @ b'A'..=b'Z'] => {
            Some(char::from(letter.to_ascii_lowercase()).to_string())
        }
        [b'D', b'i', b'g', b'i', b't', digit @ b'0'..=b'9'] => Some(char::from(*digit).to_string()),
        [b'F', ..] => code[1..]
            .parse::<u32>()
            .ok()
            .filter(|number| (1..=35).contains(number))
            .map(|number| format!("F{number}")),
        _ => None,
    }
}
