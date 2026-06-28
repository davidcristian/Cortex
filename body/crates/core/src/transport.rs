//! The `BrainTransport` port: the body's typed async client to the brain.
//!
//! The body talks to the dockerized brain only over the gRPC seam declared in
//! `proto/body.proto` (AGENTS.md). This module is the pure side of that seam:
//! the port trait plus its result and error types. No tonic, no network. That is the
//! concrete gRPC adapter lives in `body/crates/rpc` and must pass the same
//! contract shape as any fake implementing this trait.

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
}
