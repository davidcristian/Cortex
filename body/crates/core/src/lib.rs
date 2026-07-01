//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).
//!
//! No OS APIs, no network, no concrete backends. Those live in adapter
//! crates behind traits. This crate hosts the typed global-hotkey chord used
//! to summon the overlay (`docs/ROADMAP.md`, Slice 1) and the `BrainTransport`
//! port to the brain seam with `health` (Slice 2) plus a streaming `converse`
//! turn yielding typed [`TurnEvent`]s (Slice 8, ADR-0011).

pub mod hotkey;
pub mod transport;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
pub use transport::{BrainTransport, SeamHealth, TransportError, TurnEvent};
