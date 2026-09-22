//! The `BrainTransport` port: the body's typed async client to the brain.

pub mod turn;

pub use turn::{ConfirmDecision, TurnEvent};

use std::future::Future;
use std::time::Duration;

use futures_core::Stream;

use crate::session_types::{DueReminder, SessionMessage, SessionSummary};

/// The result of a `BrainService.Health` probe.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SeamHealth {
    /// Whether the brain reports itself ready to serve conversation turns.
    pub ready: bool,
    /// Human-readable status detail for the overlay (e.g. which model is up).
    pub detail: String,
}

/// Why a call to the brain failed.
#[derive(Debug, PartialEq, Eq, thiserror::Error)]
pub enum TransportError {
    /// The brain could not be reached at all: bad address, refused connection, or transport-level
    /// failure before any RPC completed.
    #[error("cannot reach the brain: {0}")]
    Connection(String),
    /// The brain was reached but answered an RPC with a non-OK gRPC status.
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
    /// (`after`), so the call was dropped.
    #[error("no reply from the brain within {after:?}")]
    Timeout {
        /// The deadline that expired, as the caller set it.
        after: Duration,
    },
}

/// The body's typed async client port to the brain (`docs/ARCHITECTURE.md`, "Ports and traits").
pub trait BrainTransport: Send + Sync {
    /// Probes `BrainService.Health` and returns the brain's readiness.
    ///
    /// # Errors
    ///
    /// `Connection` when the brain is unreachable, `Rpc` when it answers a non-OK gRPC status.
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

    /// Lists recent chats, most-recently-active first, for the overlay's chat list and switcher.
    ///
    /// # Errors
    ///
    /// `Connection` when the brain is unreachable, `Rpc` for a non-OK gRPC status.
    fn list_sessions(
        &self,
        limit: i32,
    ) -> impl Future<Output = Result<Vec<SessionSummary>, TransportError>> + Send;

    /// Loads one session's stored history in append order.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn session_messages(
        &self,
        session_id: &str,
    ) -> impl Future<Output = Result<Vec<SessionMessage>, TransportError>> + Send;

    /// Lists every reminder that has fired and is still undelivered, for the overlay to show.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn list_due_reminders(
        &self,
    ) -> impl Future<Output = Result<Vec<DueReminder>, TransportError>> + Send;

    /// Marks one fire of a reminder delivered, which the overlay calls when its card is dismissed.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn ack_reminder(
        &self,
        reminder_id: &str,
        fired_at_unix_ms: i64,
    ) -> impl Future<Output = Result<bool, TransportError>> + Send;

    /// Renames one chat, the overlay's user-driven relabel in its chat list.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn rename_session(
        &self,
        session_id: &str,
        title: &str,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;

    /// Deletes one chat and the memories derived from it.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn delete_session(
        &self,
        session_id: &str,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;

    /// Hoists or lowers one chat, from the overlay's toggle.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn set_session_hoisted(
        &self,
        session_id: &str,
        hoisted: bool,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;

    /// Reads the settings whole: every stored key, as `(key, value)` pairs sorted by key.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn get_preferences(
        &self,
    ) -> impl Future<Output = Result<Vec<(String, String)>, TransportError>> + Send;

    /// Writes one setting. An empty value clears the key, so the reader's default applies again.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn set_preference(
        &self,
        key: &str,
        value: &str,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;
}
