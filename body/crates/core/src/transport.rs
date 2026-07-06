//! The `BrainTransport` port: the body's typed async client to the brain.
//!
//! The body talks to the dockerized brain only over the gRPC seam declared in
//! `proto/body.proto` (AGENTS.md). This module is the pure side of that seam:
//! the port trait plus its result and error types. No tonic, no network. That is the
//! concrete gRPC adapter lives in `body/crates/rpc` and must pass the same
//! contract shape as any fake implementing this trait.

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
    /// The brain was reached and streamed a reply, but the wire data could
    /// not be interpreted: an empty `ServerEvent` (no event set) or a
    /// `Converse` stream that ended before a `TurnComplete`. Distinct from a
    /// brain-*reported* turn error, which arrives as [`TurnEvent::Failed`].
    #[error("malformed seam message: {0}")]
    Protocol(String),
}

/// One event from the brain during a `Converse` turn. This is the typed core mirror
/// of the proto `ServerEvent`, decoupling the overlay from the wire types.
///
/// Streamed by [`BrainTransport::converse`] as the `Ok` side of each item;
/// transport failures are the `Err` side ([`TransportError`]). A brain-reported
/// mid-turn error is [`TurnEvent::Failed`] (the connection is healthy, *this
/// turn* failed), kept distinct from an `Err`, which means the brain could not
/// be reached or streamed data the adapter could not interpret.
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
///
/// Implementations own the connection lifecycle behind this surface; callers
/// see only typed calls. `async fn`-style methods are declared as
/// `impl Future + Send` so the returned futures are guaranteed `Send` and can
/// be awaited from multi-threaded runtimes; implementors must also be
/// `Send + Sync` (supertrait bounds) so one transport can be shared across
/// tasks.
pub trait BrainTransport: Send + Sync {
    /// Probes `BrainService.Health` and returns the brain's readiness.
    ///
    /// # Errors
    ///
    /// The returned future resolves to [`TransportError::Connection`] when
    /// the brain is unreachable and [`TransportError::Rpc`] when it answers
    /// with a non-OK gRPC status.
    fn health(&self) -> impl Future<Output = Result<SeamHealth, TransportError>> + Send;

    /// Runs one conversational turn: sends `text` as a user turn on a fresh
    /// `Converse` stream tagged with `session_id`, and streams the reply as
    /// [`TurnEvent`]s until the turn is terminal ([`TurnEvent::Complete`] or
    /// [`TurnEvent::Failed`]).
    ///
    /// Session continuity is external (the brain persists session state), so
    /// each call is independent and a caller reuses one `session_id` across
    /// turns. Dropping the returned stream cancels the turn (the RPC aborts and
    /// the brain sees the client half-close). Each item is `Ok(TurnEvent)` for
    /// a brain event, or `Err(TransportError)` for a transport failure: an
    /// unreachable brain or non-OK gRPC status ([`TransportError::Connection`]
    /// / [`TransportError::Rpc`]), or a malformed stream
    /// ([`TransportError::Protocol`]).
    fn converse(
        &self,
        session_id: &str,
        text: &str,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send;

    /// Lists recent chats, most-recently-active first, for the overlay's chat
    /// list / switcher / cycling (`BrainService.ListSessions`, ADR-0021). At most
    /// `limit`; `0` means the brain's default. Read-only (a view of the store).
    ///
    /// # Errors
    ///
    /// [`TransportError::Connection`] when the brain is unreachable, or
    /// [`TransportError::Rpc`] for a non-OK gRPC status (a store failure surfaces
    /// as `Unavailable`).
    fn list_sessions(
        &self,
        limit: i32,
    ) -> impl Future<Output = Result<Vec<SessionSummary>, TransportError>> + Send;

    /// Loads one session's persisted history in append order
    /// (`BrainService.GetSessionMessages`, ADR-0021). Read-only; an unknown
    /// session is an empty history, not an error.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn session_messages(
        &self,
        session_id: &str,
    ) -> impl Future<Output = Result<Vec<SessionMessage>, TransportError>> + Send;
}
