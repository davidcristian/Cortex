//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).

pub mod hotkey;
pub mod link;
pub mod os;
pub mod retry;
pub mod session_types;
pub mod transport;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
pub use link::{LinkState, LinkStatus, probe_link};
pub use os::{
    Accelerator, AudioControl, AudioError, Capture, CaptureError, CaptureRequest, CaptureTarget,
    CapturedFrame, DeniedScreenCapture, Hotkey, HotkeyCallback, HotkeyError, Notification, Notify,
    NotifyError, RawFrame, ScreenCapture, TargetRect, VolumeChange, VolumeState,
};
pub use retry::{
    ANNOUNCED_DEADLINE_GRACE_MS, DEFAULT_CALL_DEADLINE, DEFAULT_PROBE_BUDGET,
    DEFAULT_PROBE_DEADLINE, DEFAULT_TURN_FIRST_GAP_MS, DEFAULT_TURN_IDLE_GAP_MS, FullDelay,
    Randomness, RetryPlan, RetryPolicy, RetryingTransport, SeamMethod, Sleeper, TurnGaps,
    is_transient, retry_with, within_deadline, within_gaps,
};
pub use session_types::{DueReminder, SessionMessage, SessionSummary};
pub use transport::{BrainTransport, ConfirmDecision, SeamHealth, TransportError, TurnEvent};
