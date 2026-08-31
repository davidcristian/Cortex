//! [`within_deadline`]: one attempt, bounded by the clock (ADR-0024 deadline addendum).
//!
//! Every other duration in this module tree bounds the wait between attempts, which cannot
//! bound an attempt that never returns. A brain that accepts the connection and then goes quiet
//! has no other answer: the probe would wait forever, and the overlay's indicator latches one
//! probe at a time, so the first hang would end the indicator for the session rather than delay
//! one answer.
//!
//! The bound is enforced here rather than in the gRPC adapter. tonic's own request timeout
//! attaches its `transport::Error` to the `Status::cancelled` it raises on expiry, so the
//! adapter classifies it as `TransportError::Connection` and the indicator draws `Down`, which
//! is accurate. `Connection` is retryable, though, so a transport-armed deadline would be
//! retried, which is the load amplification a timeout is classified terminal to avoid.
//! Enforcing it here, over the [`Sleeper`] port, keeps the failure typed as
//! [`TransportError::Timeout`] and outside the transient set whichever transport is underneath.
//! The measurement is pinned by `body/crates/rpc/tests/client.rs`.

use std::future::Future;
use std::time::Duration;

use crate::retry::effects::Sleeper;
use crate::transport::TransportError;

/// Runs `call` under `deadline`, or unbounded when it is `None`.
///
/// `None` is a deliberate value rather than a missing one: `Converse` is the only method that
/// carries it, since a turn is long by design and a clock cannot tell a working turn from a
/// stalled one ([`crate::retry::RetryPlan::deadline_for`]). Every other call on the port gets a
/// duration, including the writes the plan refuses to retry, because bounding a call does not
/// repeat it and an unrepeatable call still has to end in an answer or a failure.
///
/// A `None` becomes [`Duration::MAX`], so the timer is still armed and never wins (the real
/// adapter's `tokio::time::timeout` saturates it to the far future rather than overflowing).
/// The exemption is spelled as a duration rather than as a branch because this is generic code:
/// a branch here is compiled once per call type, and no instantiation the decorator makes takes
/// the unbounded side, so the arm would be dead in every copy.
///
/// # Errors
///
/// The call's own [`TransportError`] when it finished in time, or
/// [`TransportError::Timeout`] carrying `deadline` when the clock won. The abandoned call is
/// dropped, which is what cancels it.
pub async fn within_deadline<T>(
    deadline: Option<Duration>,
    sleeper: &impl Sleeper,
    call: impl Future<Output = Result<T, TransportError>> + Send,
) -> Result<T, TransportError>
where
    T: Send,
{
    let after = deadline.unwrap_or(Duration::MAX);
    sleeper
        .bounded(after, call)
        .await
        .unwrap_or(Err(TransportError::Timeout { after }))
}
