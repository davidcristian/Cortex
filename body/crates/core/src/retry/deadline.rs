//! [`within_deadline`]: one attempt, bounded by the clock.
//!
//! The bound is enforced here rather than by the gRPC transport, whose own expiry arrives as a
//! connection failure, which is retryable and would turn one abandoned call into three.

use std::future::Future;
use std::time::Duration;

use crate::retry::effects::Sleeper;
use crate::transport::TransportError;

/// Runs `call` under `deadline`. A `None` becomes [`Duration::MAX`], so the timer never wins.
///
/// # Errors
///
/// The call's own [`TransportError`], or [`TransportError::Timeout`] when the clock won first.
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
