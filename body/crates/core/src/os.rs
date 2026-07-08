//! OS-capability ports for the body, forming the first portability seam (AGENTS.md,
//! ADR-0011). Pure traits and value types here; per-platform adapters live in
//! the `os_windows` / `os_linux` / `os_macos` crates behind them.
//!
//! Slice 8 introduces [`Hotkey`] (the global-hotkey backend); Slice 9 adds
//! [`AudioControl`] (the first OS action the brain drives over `BodyService`);
//! the screen and input traits join in Slice 10 and later. The overlay is summoned by a global
//! hotkey whose chord is a [`HotkeyChord`]; a backend registers that chord with
//! the OS and calls back on each press. Mapping a chord to the OS key identifier
//! is pure and lives here ([`Accelerator`]); touching the OS is the adapter's job.

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
///
/// The body registers exactly one chord for its lifetime; the backend owns the
/// OS registration and unregisters when dropped. `register` resolves the chord
/// to an [`Accelerator`], asks the OS to bind it, and arranges for `on_activate`
/// to run on each press.
pub trait Hotkey {
    /// Registers `chord` as a global hotkey, invoking `on_activate` on each
    /// press.
    ///
    /// # Errors
    ///
    /// [`HotkeyError::UnsupportedKey`] if the chord's key has no accelerator
    /// mapping; [`HotkeyError::Registration`] if the OS refuses the binding.
    fn register(&self, chord: &HotkeyChord, on_activate: HotkeyCallback)
    -> Result<(), HotkeyError>;
}

/// A hotkey chord resolved to the OS-neutral form a backend needs: the
/// canonical modifiers plus the key's [`KeyboardEvent.code`] name (e.g.
/// `"Space"`, `"KeyA"`, `"F5"`). Backends map these to their own types
/// (`global-hotkey` `Modifiers`/`Code`, etc.).
///
/// [`KeyboardEvent.code`]: https://www.w3.org/TR/uievents-code/
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

/// Why reading or changing the host audio volume failed. See [`AudioControl`].
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
pub enum AudioError {
    /// No usable audio output endpoint (no default device, or it was removed).
    /// `0` is a backend detail.
    #[error("no audio output endpoint is available: {0}")]
    NoEndpoint(String),
    /// The OS audio backend refused or failed the operation. `0` is a backend detail.
    #[error("the audio backend failed: {0}")]
    Backend(String),
}

/// The host's audio output state: `level` in `[0.0, 1.0]` and whether it is `muted`.
/// The OS-neutral value both directions of the seam speak (mirrors the proto `VolumeState`).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct VolumeState {
    /// Output volume as a fraction, `0.0` (silent) to `1.0` (max).
    pub level: f32,
    /// Whether the output is muted.
    pub muted: bool,
}

/// A requested change to the host volume: set the `level`, the `mute` flag, or both.
/// A `None` field is left untouched (proto explicit presence, resolved to the core here).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct VolumeChange {
    /// The target level, already clamped to `[0.0, 1.0]`, or `None` to leave it.
    pub level: Option<f32>,
    /// The target mute state, or `None` to leave it.
    pub mute: Option<bool>,
}

impl VolumeChange {
    /// Builds a change from a raw request, clamping a present `level` to `[0.0, 1.0]` (a
    /// `NaN` level clamps to the silent floor `0.0`). The clamp lives here (pure, gated)
    /// so no OS backend ever receives an out-of-range scalar (the proto documents the clamp
    /// but the wire message does not enforce it).
    #[must_use]
    pub fn new(level: Option<f32>, mute: Option<bool>) -> Self {
        Self {
            level: level.map(clamp_level),
            mute,
        }
    }
}

/// Clamps a raw volume level to `[0.0, 1.0]`; `NaN` becomes the silent floor `0.0`.
fn clamp_level(level: f32) -> f32 {
    if level.is_nan() {
        0.0
    } else {
        level.clamp(0.0, 1.0)
    }
}

/// The port an audio-control backend implements (`os_windows` real via Core Audio; other
/// platforms are stubs until built, per ADR-0023). It is the sibling of [`Hotkey`] and the first
/// OS capability the brain drives over `BodyService`.
///
/// `Send + Sync` (unlike the single-threaded [`Hotkey`]) because the body's `BodyService`
/// server holds the backend across async tasks. The body server is stateless (volume is read
/// from the OS on demand), so nothing here violates the one hard rule.
pub trait AudioControl: Send + Sync {
    /// Reads the host's current output volume state.
    ///
    /// # Errors
    ///
    /// [`AudioError`] if no output endpoint is available or the backend fails.
    fn get_volume(&self) -> Result<VolumeState, AudioError>;

    /// Applies `change` (level and/or mute) and reports the resulting state.
    ///
    /// # Errors
    ///
    /// [`AudioError`] if no output endpoint is available or the backend fails.
    fn set_volume(&self, change: VolumeChange) -> Result<VolumeState, AudioError>;
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
