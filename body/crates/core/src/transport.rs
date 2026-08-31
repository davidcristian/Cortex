//! The `BrainTransport` port: the body's typed async client to the brain.

pub mod turn;

pub use turn::{ConfirmDecision, TurnEvent};

use std::future::Future;
use std::time::Duration;

use futures_core::Stream;

use crate::session_types::{DueReminder, SessionMessage, SessionSummary};

/// Result of a `BrainService.Health` probe over the seam.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SeamHealth {
    /// Whether the brain reports itself ready to serve conversation turns.
    pub ready: bool,
    /// Human-readable status detail for the overlay (e.g. which model is up).
    pub detail: String,
}

/// Why a seam call failed. See [`BrainTransport`].
#[derive(Debug, PartialEq, Eq, thiserror::Error)]
pub enum TransportError {
    /// The brain could not be reached at all: bad address, refused
    /// connection, or transport-level failure before any RPC completed.
    #[error("cannot reach the brain: {0}")]
    Connection(String),
    /// The brain was reached but answered an RPC with a non-OK gRPC status.
    /// `code` is the status-code name (e.g. `Internal`, `Unimplemented`).
    #[error("brain rpc failed ({code}): {message}")]
    Rpc {
        /// gRPC status-code name, e.g. `Internal` or `Unimplemented`.
        code: String,
        /// Status message reported by the brain.
        message: String,
    },
    /// The brain was reached and streamed a reply, but the wire data could not be interpreted: an
    /// empty `ServerEvent` (no event set) or a `Converse` stream that ended before a
    /// `TurnComplete`.
    #[error("malformed seam message: {0}")]
    Protocol(String),
    /// The attempt was abandoned: nothing came back within the deadline the caller gave it
    /// (`after`), so the call was dropped (ADR-0024 deadline addendum).
    #[error("no reply from the brain within {after:?}")]
    Timeout {
        /// The deadline that expired, as the caller set it.
        after: Duration,
    },
}

/// The body's typed async client port to the brain (`docs/ARCHITECTURE.md`,
/// "Ports and traits").
pub trait BrainTransport: Send + Sync {
    /// Probes `BrainService.Health` and returns the brain's readiness.
    fn health(&self) -> impl Future<Output = Result<SeamHealth, TransportError>> + Send;

    /// Runs one conversational turn: sends `text` as a user turn on a fresh `Converse` stream
    /// tagged with `session_id`, and streams the reply as [`TurnEvent`]s until the turn is terminal
    /// ([`TurnEvent::Complete`] or [`TurnEvent::Failed`]).
    fn converse(
        &self,
        session_id: &str,
        text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send;

    /// Lists recent chats, most-recently-active first, for the overlay's chat
    /// list / switcher / cycling (`BrainService.ListSessions`, ADR-0021). At most
    /// `limit`; `0` means the brain's default. Read-only (a view of the store).
    fn list_sessions(
        &self,
        limit: i32,
    ) -> impl Future<Output = Result<Vec<SessionSummary>, TransportError>> + Send;

    /// Loads one session's persisted history in append order
    /// (`BrainService.GetSessionMessages`, ADR-0021). Read-only; an unknown
    /// session is an empty history, not an error.
    fn session_messages(
        &self,
        session_id: &str,
    ) -> impl Future<Output = Result<Vec<SessionMessage>, TransportError>> + Send;

    /// Lists every reminder that has fired and is still awaiting delivery
    /// (`BrainService.ListDueReminders`, ADR-0025), for the overlay to surface when it opens.
    fn list_due_reminders(
        &self,
    ) -> impl Future<Output = Result<Vec<DueReminder>, TransportError>> + Send;

    /// Marks one reminder delivered (`BrainService.AckReminder`, ADR-0025), which is what the
    /// overlay calls when the user dismisses it.
    fn ack_reminder(
        &self,
        reminder_id: &str,
    ) -> impl Future<Output = Result<bool, TransportError>> + Send;

    /// Renames one chat (`BrainService.RenameSession`, ADR-0021 management addendum): the overlay's
    /// user-driven relabel of a chat in its list.
    fn rename_session(
        &self,
        session_id: &str,
        title: &str,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;

    /// Deletes one chat (`BrainService.DeleteSession`, ADR-0021 management addendum): the overlay's
    /// user-driven destructive removal of a chat and its derived memories.
    fn delete_session(
        &self,
        session_id: &str,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;

    /// Pins or unpins one chat (`BrainService.SetSessionPinned`, ADR-0021 pinning addendum): the
    /// overlay's user-driven pin toggle.
    fn set_session_pinned(
        &self,
        session_id: &str,
        pinned: bool,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;

    /// Reads the user's settings record whole (`BrainService.GetPreferences`): every key the brain
    /// has stored, as `(key, value)` pairs sorted by key.
    fn get_preferences(
        &self,
    ) -> impl Future<Output = Result<Vec<(String, String)>, TransportError>> + Send;

    /// Writes one setting (`BrainService.SetPreference`): `key` is a namespaced name the caller
    /// owns, `value` an opaque short string, and an empty value clears the key so the reader's
    /// own default applies again, following the `rename_session` empty-title convention.
    fn set_preference(
        &self,
        key: &str,
        value: &str,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;
}
