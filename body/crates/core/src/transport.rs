//! The `BrainTransport` port: the body's typed async client to the brain.
//!
//! The body talks to the dockerized brain only over the gRPC seam declared in
//! `proto/body.proto` (AGENTS.md). This module is the pure side of that seam:
//! the port trait plus its result and error types. No tonic, no network. That is the
//! concrete gRPC adapter lives in `body/crates/rpc` and must pass the same
//! contract shape as any fake implementing this trait.
//!
//! The *turn* vocabulary a `converse` call carries ([`TurnEvent`] and [`ConfirmDecision`])
//! lives in [`turn`], split out for the line cap and re-exported here, so this module stays
//! the port and the types its calls resolve to.

pub mod turn;

pub use turn::{ConfirmDecision, TurnEvent};

use std::future::Future;

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
    /// The brain was reached and streamed a reply, but the wire data could
    /// not be interpreted: an empty `ServerEvent` (no event set) or a
    /// `Converse` stream that ended before a `TurnComplete`. Distinct from a
    /// brain-*reported* turn error, which arrives as [`TurnEvent::Failed`].
    #[error("malformed seam message: {0}")]
    Protocol(String),
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
    ///
    /// `decisions` answers mid-turn [`TurnEvent::ConfirmRequest`]s (ADR-0022):
    /// each item is forwarded to the brain on the open request stream, which
    /// half-closes when `decisions` ends. A caller with no confirm surface
    /// passes an empty stream (an immediate half-close, which is the pre-confirm shape).
    /// An unanswered or undeliverable confirm is denied brain-side
    /// (fail-closed), so a decision sent after teardown is a harmless no-op.
    fn converse(
        &self,
        session_id: &str,
        text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
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

    /// Lists every reminder that has fired and is still awaiting delivery
    /// (`BrainService.ListDueReminders`, ADR-0025), for the overlay to surface when
    /// it opens. Read-only, all-sessions (one user has one set of reminders), and
    /// empty rather than an error when the brain runs without a schedule backend:
    /// a schedule-free brain is indistinguishable from one with nothing due.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn list_due_reminders(
        &self,
    ) -> impl Future<Output = Result<Vec<DueReminder>, TransportError>> + Send;

    /// Marks one reminder delivered (`BrainService.AckReminder`, ADR-0025), which is
    /// what the overlay calls when the user dismisses it. `true` means this call
    /// cleared it; `false` means there was nothing to clear (an unknown id, or an
    /// already-acked one), so the answer is a state report, not a failure.
    ///
    /// The one write on this port, and a narrow one: acking twice is a no-op, so a
    /// caller that cannot tell whether its first attempt landed may repeat it.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`].
    fn ack_reminder(
        &self,
        reminder_id: &str,
    ) -> impl Future<Output = Result<bool, TransportError>> + Send;

    /// Renames one chat (`BrainService.RenameSession`, ADR-0021 management addendum): the
    /// overlay's user-driven relabel of a chat in its list. `title` is the new display label;
    /// `""` clears any custom/brain-generated title so the switcher falls back to the
    /// first-message derivation. The brain re-bounds the label when listing.
    ///
    /// A **write**, and a user-only one. Unlike a gated `Converse` tool call (whose gate is the
    /// mid-turn confirm card), this is reachable only from the overlay's own controls, never
    /// from a model, tool, or tainted turn, so no injected content can drive it. It carries an
    /// effect, so the resilient transport refuses to retry it (`SeamMethod::RenameSession` is
    /// not repeatable): one attempt, and a transient failure surfaces rather than risking a
    /// second write. Setting the same title twice is harmless, but a lost reply must not become
    /// a silent second relabel of whatever the row holds by then.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`] (a store failure surfaces as `Unavailable`).
    fn rename_session(
        &self,
        session_id: &str,
        title: &str,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;

    /// Deletes one chat (`BrainService.DeleteSession`, ADR-0021 management addendum): the
    /// overlay's user-driven destructive removal of a chat and its derived memories. The brain
    /// hard-deletes the transcript and catalog entry and cascades to the session's private
    /// memories; the reply is a bare acknowledgement (the overlay drops the row and re-lists).
    ///
    /// A **destructive, irreversible write**, and a user-only one. Its gate is the same structural
    /// user-only reachability `rename_session` has (never a model, tool, or tainted turn), and the
    /// user's intent is secured OUT of band by an overlay-local confirm before this is ever called.
    /// Because it carries a destructive effect, the resilient transport refuses to retry it
    /// (`SeamMethod::DeleteSession` is not repeatable): one attempt, and a transient failure
    /// surfaces rather than silently re-issuing a destroy. The delete is idempotent, so a repeat is
    /// a no-op ONLY while nothing re-creates the id; but deleting the currently-open chat while its
    /// turn still streams is exactly a concurrent `append` that can re-materialize it between a lost
    /// reply and a retry, so a silent retry could destroy a transcript the user never confirmed
    /// removing. The user, who confirmed once, retries deliberately instead.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`] (a store or memory failure surfaces as `Unavailable`).
    fn delete_session(
        &self,
        session_id: &str,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;

    /// Pins or unpins one chat (`BrainService.SetSessionPinned`, ADR-0021 pinning addendum): the
    /// overlay's user-driven pin toggle. `pinned` is the target state; a pinned chat is unioned
    /// into `list_sessions` regardless of recency and sorts above the recency group, so pinning
    /// keeps an important chat reachable after it ages out of the recency window.
    ///
    /// A **write**, and a user-only one. Its gate is the same structural user-only reachability
    /// `rename_session`/`delete_session` have (never a model, tool, or tainted turn). Setting the
    /// same state twice is a no-op (idempotent by value), yet the resilient transport still refuses
    /// to retry it (`SeamMethod::SetSessionPinned` is not repeatable), the catalog-write convention:
    /// one attempt, so a lost reply never silently re-asserts a pinned value the user's next toggle
    /// reversed. The overlay re-lists after it resolves to reflect the change.
    ///
    /// # Errors
    ///
    /// As [`BrainTransport::list_sessions`] (a store failure surfaces as `Unavailable`).
    fn set_session_pinned(
        &self,
        session_id: &str,
        pinned: bool,
    ) -> impl Future<Output = Result<(), TransportError>> + Send;
}
