//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).
#![cfg_attr(coverage, feature(coverage_attribute))]

pub mod hotkey;
pub mod link;
pub mod os;
pub mod retry;
pub mod session_types;
pub mod transport;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
pub use link::{LinkState, LinkStatus, probe_link};
pub use os::{
    Accelerator, AudioControl, AudioError, Capture, CaptureError, CaptureRequest,
    DeniedScreenCapture, Hotkey, HotkeyCallback, HotkeyError, Notification, Notify, NotifyError,
    RawFrame, ScreenCapture, VolumeChange, VolumeState,
};
pub use retry::{
    DEFAULT_PROBE_BUDGET, FullDelay, Randomness, RetryPlan, RetryPolicy, RetryingTransport,
    SeamMethod, Sleeper, is_transient, retry_with,
};
pub use session_types::{DueReminder, SessionMessage, SessionSummary};
pub use transport::{BrainTransport, ConfirmDecision, SeamHealth, TransportError, TurnEvent};
