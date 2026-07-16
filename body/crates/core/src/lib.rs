//! Pure, I/O-free core logic for the Cortex body (the hexagonal core).
//!
//! No OS APIs, no network, no concrete backends. Those live in adapter
//! crates behind traits. This crate hosts the typed global-hotkey chord used
//! to summon the overlay (`docs/ROADMAP.md`, Slice 1); the `BrainTransport`
//! port to the brain seam with `health` (Slice 2) plus a streaming `converse`
//! turn yielding typed [`TurnEvent`]s (Slice 8, ADR-0011), along with the
//! [`RetryingTransport`] decorator + [`Sleeper`] port that add bounded-retry
//! resilience over it (ADR-0024), plus the reminder pull reads the overlay
//! surfaces when it opens (Slice 9.5, ADR-0025); and the OS-capability ports (`os`): the
//! [`Hotkey`] backend seam (Slice 8), the [`AudioControl`] volume seam the
//! brain drives over `BodyService` (Slice 9, ADR-0023), and the [`Notify`] seam that
//! delivers a fired reminder as a native notification (Slice 9.5, ADR-0025).

pub mod hotkey;
pub mod os;
pub mod retry;
pub mod transport;

pub use hotkey::{HotkeyChord, HotkeyParseError, Modifier};
pub use os::{
    Accelerator, AudioControl, AudioError, Hotkey, HotkeyCallback, HotkeyError, Notification,
    Notify, NotifyError, VolumeChange, VolumeState,
};
pub use retry::{
    FullDelay, Randomness, RetryPolicy, RetryingTransport, Sleeper, is_transient, retry_with,
};
pub use transport::{
    BrainTransport, ConfirmDecision, DueReminder, SeamHealth, SessionMessage, SessionSummary,
    TransportError, TurnEvent,
};
