//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).
//!
//! No OS APIs, no network, no concrete backends. Those live in adapter
//! crates behind traits. This crate hosts the typed global-hotkey chord used
//! to summon the overlay (`docs/ROADMAP.md`, Slice 1); the `BrainTransport`
//! port to the brain seam with `health` (Slice 2) plus a streaming `converse`
//! turn yielding typed [`TurnEvent`]s (Slice 8, ADR-0011), along with the
//! [`RetryingTransport`] decorator + [`Sleeper`] port that add bounded-retry
//! resilience over it (ADR-0024), gated by the per-method [`RetryPlan`] that decides
//! which calls may be repeated at all, the [`LinkStatus`] classification the overlay's
//! connection indicator shows (`link`, ADR-0011 addendum), plus the reminder pull reads
//! the overlay surfaces when it opens (Slice 9.5, ADR-0025); and the OS-capability ports (`os`): the
//! [`Hotkey`] backend seam (Slice 8), the [`AudioControl`] volume seam the
//! brain drives over `BodyService` (Slice 9, ADR-0023), the [`Notify`] seam that
//! delivers a fired reminder as a native notification (Slice 9.5, ADR-0025), and the
//! [`ScreenCapture`] seam that gives the cortex eyes (Slice 10, ADR-0029) along with the
//! whole downscale, encode, and byte-ceiling policy that bounds what it may send.
//!
//! No coverage escape is declared in this crate: every line of it is reachable from a test, which
//! is the whole point of putting the capture's size policy here rather than in the `cfg(windows)`
//! backend CI never compiles.

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
