//! [`within_deadline`]: one attempt, bounded by the clock (ADR-0024 deadline addendum).
//!
//! Every other duration in this module tree bounds the wait *between* attempts, which cannot
//! bound an attempt that never returns. A brain that accepts the connection and then goes quiet
//! is the case that has no answer without this: the probe would wait forever, and the overlay's
//! indicator latches one probe at a time, so the first hang would end the indicator for the
//! session rather than delay one answer.
//!
//! **Why the bound is here and not in the gRPC adapter.** The obvious implementation is tonic's
//! own request timeout, and it is a trap, though not the trap this comment first named. tonic
//! attaches its `transport::Error` to the `Status::cancelled` it raises on expiry, so the
//! adapter classifies it `TransportError::Connection` and the indicator draws `Down`, which is
//! honest. `Connection` is *retryable*, though, so a transport-armed deadline would be
//! **retried**, which is the load amplifier a timeout is classified terminal to avoid. Enforcing
//! it here, over the [`Sleeper`] port, keeps the failure typed as what it is
//! ([`TransportError::Timeout`]) and outside the transient set, no matter which transport is
//! underneath. The measurement is pinned by `body/crates/rpc/tests/client.rs`.

use std::future::Future;
use std::time::Duration;

use crate::retry::effects::Sleeper;
use crate::transport::TransportError;

/// Runs `call` under `deadline`, or unbounded when it is `None`.
///
/// `None` is a real answer rather than a default: `Converse` is the method that has one, since a
/// turn is long by design and a clock is the wrong thing to end one
/// ([`crate::retry::RetryPlan::deadline_for`]). Every other call on the port gets a duration,
/// **including the writes the plan refuses to retry**: bounding is not repeating, so the two
/// questions are independent and an unrepeatable call still deserves an answer or a failure.
///
/// A `None` becomes [`Duration::MAX`], which is what "no deadline" means to a clock: the timer
/// is still armed and simply never wins (the real adapter's `tokio::time::timeout` saturates it
/// to the far future rather than overflowing). Spelling the exemption as a duration instead of
/// a branch is deliberate. This is generic code, so a branch here is compiled once per call
/// type, and no instantiation the decorator makes could ever take the unbounded side of it: the
/// arm would be dead in every copy, which is a worse thing to ship than an arithmetic ceiling.
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
