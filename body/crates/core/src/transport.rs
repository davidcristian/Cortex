//! The `BrainTransport` port: the body's typed async client to the brain.

use std::future::Future;

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
}

/// The body's typed async client port to the brain (`docs/ARCHITECTURE.md`,
/// "Ports and traits").
pub trait BrainTransport: Send + Sync {
    /// Probes `BrainService.Health` and returns the brain's readiness.
    fn health(&self) -> impl Future<Output = Result<SeamHealth, TransportError>> + Send;
}
