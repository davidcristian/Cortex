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
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send;
}
