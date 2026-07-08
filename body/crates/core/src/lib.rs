//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).

pub mod hotkey;
pub mod os;
pub mod retry;
pub mod transport;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
pub use os::{
    Accelerator, AudioControl, AudioError, Hotkey, HotkeyCallback, HotkeyError, VolumeChange,
    VolumeState,
};
pub use retry::{RetryPolicy, RetryingTransport, Sleeper, is_transient};
pub use transport::{
    BrainTransport, ConfirmDecision, SeamHealth, SessionMessage, SessionSummary, TransportError,
    TurnEvent,
};
