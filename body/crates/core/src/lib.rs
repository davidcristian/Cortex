//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).

pub mod hotkey;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
