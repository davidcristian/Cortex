//! Typed, validated global-hotkey chords.

use std::fmt;

/// A keyboard modifier in a hotkey chord.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Modifier {
    /// The Control key (accepted alias: `control`).
    Ctrl,
    /// The Alt key.
    Alt,
    /// The Shift key.
    Shift,
    /// The OS key (accepted aliases: `win`, `cmd`, `meta`).
    Super,
}

impl Modifier {
    /// Canonical lowercase name, as used in a chord's `Display` form.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Ctrl => "ctrl",
            Self::Alt => "alt",
            Self::Shift => "shift",
            Self::Super => "super",
        }
    }

    /// Maps a lowercase, trimmed segment (canonical name or alias) to a modifier; `None` if the
    /// segment does not name a modifier.
    fn from_alias(segment: &str) -> Option<Self> {
        match segment {
            "ctrl" | "control" => Some(Self::Ctrl),
            "alt" => Some(Self::Alt),
            "shift" => Some(Self::Shift),
            "super" | "win" | "cmd" | "meta" => Some(Self::Super),
            _ => None,
        }
    }
}

impl fmt::Display for Modifier {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Why a chord string failed to parse.
#[derive(Debug, PartialEq, Eq, thiserror::Error)]
pub enum HotkeyParseError {
    /// The input was empty or only whitespace.
    #[error("hotkey chord is empty")]
    Empty,
    /// A `+`-separated segment was empty, e.g. `ctrl++space` or `ctrl+`.
    #[error("hotkey chord has an empty segment (stray `+`?)")]
    EmptySegment,
    /// A segment before the key does not name a modifier.
    #[error("`{0}` is not a modifier (expected ctrl, alt, shift, or super)")]
    UnknownModifier(String),
    /// The same modifier appears more than once, possibly via an alias.
    #[error("modifier `{0}` appears more than once in the chord")]
    DuplicateModifier(String),
    /// The chord ends in a modifier, so there is no key.
    #[error("chord ends in modifier `{0}` but must end in a key, e.g. `ctrl+alt+space`")]
    MissingKey(String),
}

/// A validated global-hotkey chord: zero or more modifiers plus one key.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HotkeyChord {
    modifiers: Vec<Modifier>,
    key: String,
}

impl HotkeyChord {
    /// Parses a chord such as `Ctrl+Alt+Space`.
    ///
    /// # Errors
    ///
    /// [`HotkeyParseError`] for an empty or unknown segment, a repeated modifier, or a trailing one.
    pub fn parse(input: &str) -> Result<Self, HotkeyParseError> {
        let trimmed = input.trim();
        if trimmed.is_empty() {
            return Err(HotkeyParseError::Empty);
        }
        let (modifier_part, key_part) = match trimmed.rsplit_once('+') {
            Some((modifiers, key)) => (Some(modifiers), key),
            None => (None, trimmed),
        };
        let mut modifiers = Vec::new();
        if let Some(part) = modifier_part {
            for segment in part.split('+') {
                let segment = segment.trim().to_lowercase();
                if segment.is_empty() {
                    return Err(HotkeyParseError::EmptySegment);
                }
                let Some(modifier) = Modifier::from_alias(&segment) else {
                    return Err(HotkeyParseError::UnknownModifier(segment));
                };
                if modifiers.contains(&modifier) {
                    return Err(HotkeyParseError::DuplicateModifier(segment));
                }
                modifiers.push(modifier);
            }
        }
        let key = key_part.trim().to_lowercase();
        if key.is_empty() {
            return Err(HotkeyParseError::EmptySegment);
        }
        if Modifier::from_alias(&key).is_some() {
            return Err(HotkeyParseError::MissingKey(key));
        }
        modifiers.sort_unstable();
        Ok(Self { modifiers, key })
    }

    /// The modifiers, deduplicated and in canonical order.
    #[must_use]
    pub fn modifiers(&self) -> &[Modifier] {
        &self.modifiers
    }

    /// The lowercase key name (the last segment of the chord).
    #[must_use]
    pub fn key(&self) -> &str {
        &self.key
    }
}

impl Default for HotkeyChord {
    /// The default chord, `ctrl+alt+space` (`docs/ROADMAP.md` assumption 7).
    fn default() -> Self {
        Self {
            modifiers: vec![Modifier::Ctrl, Modifier::Alt],
            key: String::from("space"),
        }
    }
}

impl fmt::Display for HotkeyChord {
    /// Canonical lowercase form, e.g. `ctrl+alt+space`.
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut out = String::new();
        for modifier in &self.modifiers {
            out.push_str(modifier.as_str());
            out.push('+');
        }
        out.push_str(&self.key);
        f.write_str(&out)
    }
}
