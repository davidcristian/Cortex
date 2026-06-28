//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).
//!
//! No OS APIs, no network, no concrete backends. Those live in adapter
//! crates behind traits. This crate currently hosts the typed global-hotkey
//! chord used to summon the overlay (`docs/ROADMAP.md`, Slice 1).

pub mod hotkey;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
