//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).

pub mod hotkey;
pub mod os;
pub mod transport;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
pub use os::{Accelerator, Hotkey, HotkeyCallback, HotkeyError};
pub use transport::{
    BrainTransport, ConfirmDecision, SeamHealth, SessionMessage, SessionSummary, TransportError,
    TurnEvent,
};
