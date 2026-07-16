//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).

pub mod hotkey;
pub mod link;
pub mod os;
pub mod retry;
pub mod transport;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
pub use link::{LinkState, LinkStatus, probe_link};
pub use os::{
    Accelerator, AudioControl, AudioError, Hotkey, HotkeyCallback, HotkeyError, Notification,
    Notify, NotifyError, VolumeChange, VolumeState,
};
pub use retry::{
    DEFAULT_PROBE_BUDGET, FullDelay, Randomness, RetryPlan, RetryPolicy, RetryingTransport,
    SeamMethod, Sleeper, is_transient, retry_with,
};
pub use transport::{
    BrainTransport, ConfirmDecision, DueReminder, SeamHealth, SessionMessage, SessionSummary,
    TransportError, TurnEvent,
};
