//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).

pub mod hotkey;
pub mod transport;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
pub use transport::{BrainTransport, SeamHealth, TransportError};
