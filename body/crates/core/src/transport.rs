//! The `BrainTransport` port: the body's typed async client to the brain.

use std::future::Future;

use futures_core::Stream;

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
}

/// The user's answer to a [`TurnEvent::ConfirmRequest`] (ADR-0022): fed into
/// [`BrainTransport::converse`]'s `decisions` stream and delivered to the brain
/// as a `ConfirmResponse` client event on the open `Converse` stream.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConfirmDecision {
    /// Echoes the `confirm_id` of the request being answered.
    pub confirm_id: String,
    /// `true` approves the gated call; `false` denies it.
    pub approved: bool,
}

/// One event from the brain during a `Converse` turn. This is the typed core mirror
/// of the proto `ServerEvent`, decoupling the overlay from the wire types.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TurnEvent {
    /// A chunk of streamed assistant text (proto `TextDelta`).
    Delta(String),
    /// Audit-visible tool use, for the overlay to surface (proto `ToolActivity`).
    ToolActivity {
        /// The tool being invoked, e.g. `read_email`.
        tool_name: String,
        /// Human-readable summary of the activity.
        summary: String,
    },
    /// Progress for the overlay to show, e.g. a model swap (proto `StatusUpdate`).
    Status {
        /// Machine-readable state name, e.g. `model_loading`.
        state: String,
        /// Human-readable detail.
        detail: String,
    },
    /// A gated (outbound/irreversible) tool call awaits the user's approval
    /// (proto `ConfirmRequest`, ADR-0022); **non-terminal**, because the turn is
    /// suspended brain-side until a matching [`ConfirmDecision`] arrives on
    ConfirmRequest {
        /// Correlation id minted by the brain; echo it in the decision.
        confirm_id: String,
        /// What would run, e.g. `send_email`.
        tool_name: String,
        /// The exact draft being approved, one JSON object that is the executed
        /// contract (what you approve is what runs).
        arguments_json: String,
        /// Why confirmation is required; shown to the user verbatim.
        reason: String,
    },
    /// The turn finished successfully (proto `TurnComplete`); terminal.
    Complete {
        /// Server-assigned turn id.
        turn_id: String,
    },
    /// The brain reported an error for this turn (proto `SeamError`); terminal.
    /// The connection is healthy. Contrast [`TransportError`].
    Failed {
        /// Application error code reported by the brain.
        code: String,
        /// Human-readable error message.
        message: String,
    },
}

/// One recent chat as the overlay's switcher shows it. This is the typed core mirror
/// of the proto `SessionSummary` (ADR-0021).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionSummary {
    /// The chat's session id (its identity for loading history / cycling).
    pub session_id: String,
    /// Derived title: the first user message, one line, truncated.
    pub title: String,
    /// Derived one-line preview: the last message's text, truncated.
    pub preview: String,
    /// Last-activity time as unix-milliseconds, for a relative timestamp.
    pub last_activity_unix_ms: i64,
}

/// One persisted message in a session's history. This is the typed core mirror of the
/// proto `SessionMessage` (ADR-0021).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionMessage {
    /// `"user"` or `"assistant"` are the only persisted roles.
    pub role: String,
    /// The message text.
    pub text: String,
    /// The turn this message belongs to (user turn + its assistant reply share it).
    pub turn_id: String,
    /// Authoring time as unix-milliseconds.
    pub at_unix_ms: i64,
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
}
