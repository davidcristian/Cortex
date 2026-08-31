//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).
//!
//! No OS APIs, no network, no concrete backends; those live in adapter crates behind traits.
//! Slice numbers below refer to `docs/ROADMAP.md`. The crate holds:
//!
//! - The typed global-hotkey chord that summons the overlay (`hotkey`).
//! - The `BrainTransport` port to the brain seam (`transport`): `health` and a
//!   streaming `converse` turn yielding typed [`TurnEvent`]s (ADR-0011), plus the
//!   reminder pull reads the overlay surfaces when it opens (ADR-0025).
//! - The [`RetryingTransport`] decorator and [`Sleeper`] port that add bounded-retry
//!   resilience over that port (`retry`, ADR-0024), driven by the per-method [`RetryPlan`]:
//!   which calls may be repeated at all, and which clock bounds each, either a deadline on a
//!   unary call or a pair of [`TurnGaps`] on a turn's silence.
//! - The [`LinkStatus`] classification behind the overlay's connection indicator (`link`,
//!   ADR-0011 addendum).
//! - The OS-capability ports (`os`): [`Hotkey`], the [`AudioControl`] volume seam the
//!   brain drives over `BodyService` (ADR-0023), the [`Notify`] seam that delivers a
//!   fired reminder as a native notification (ADR-0025), and [`ScreenCapture`]
//!   (ADR-0029) with the crop, downscale, encode, and byte-ceiling policy that
//!   bounds what it may send.
//!
//! This crate declares no coverage escape, because every line of it is reachable from a test.
//! That is why the capture's size policy lives here rather than in the `cfg(windows)` backend,
//! which CI never compiles.

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
