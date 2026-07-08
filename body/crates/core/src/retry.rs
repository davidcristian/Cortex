//! `RetryingTransport`: bounded-retry resilience over the `BrainTransport` port (ADR-0024).
//!
//! Slice 2's deferred refinement. The brain is a supervised local process that occasionally
//! blinks out (restarting after a model swap, a momentary loopback drop) and a read the
//! overlay makes fails hard when a retry a beat later would succeed. This module adds that
//! retry as a **decorator over the port**, not code in the adapter: `RetryingTransport` *is* a
//! [`BrainTransport`] that wraps an inner one and loops the idempotent calls on a transient
//! failure, so `body_rpc`'s `BrainSeamClient` stays the thin translation it was (AGENTS.md).
//!
//! Two effects are kept out of this pure crate behind seams: the backoff *wait* is a
//! [`Sleeper`] port (a real `TokioSleeper` lives in the ungated shell; a `FakeSleeper` records
//! the schedule in tests, so no wall-clock elapses), and dialing/reconnecting is the inner
//! transport's job (composed over a lazy channel). See [body-rpc.md](../../../docs/modules/body-rpc.md).
//!
//! What is retried: `health`, `list_sessions`, `session_messages`. All read-only, safe to repeat.
//! What is not: `converse` is forwarded unchanged (non-idempotent, a one-shot `decisions`
//! stream that cannot be replayed, and a failed turn is terminal by the overlay's contract).

use std::future::Future;
use std::time::Duration;

use futures_core::Stream;

use crate::transport::{
    BrainTransport, ConfirmDecision, SeamHealth, SessionMessage, SessionSummary, TransportError,
    TurnEvent,
};

/// A timer effect: wait `duration` before resolving. The one seam the retry loop uses to
/// back off, so the *schedule* is testable with a fake that returns immediately (no real
/// time), and the real `tokio::time::sleep` stays in the ungated composition root (ADR-0024).
pub trait Sleeper: Send + Sync {
    /// Resolves after `duration` has elapsed.
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send;
}

/// Whether a failed seam call is worth retrying: transient reachability/backend conditions
/// (`Connection`, and the gRPC-conventional `Rpc{Unavailable}`) are; a genuine application
/// answer (any other `Rpc` status) or uninterpretable wire data (`Protocol`) is not. A repeat
/// would return the same thing (ADR-0024 decision 3).
#[must_use]
pub fn is_transient(error: &TransportError) -> bool {
    match error {
        TransportError::Connection(_) => true,
        TransportError::Rpc { code, .. } => code == "Unavailable",
        TransportError::Protocol(_) => false,
    }
}

/// A bounded exponential-backoff schedule (pure, `Copy`): the number of tries and the growing,
/// capped delay between them (ADR-0024 decision 4). No jitter in v1. A single supervised local
/// peer has no thundering herd to spread.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetryPolicy {
    /// Total attempts including the first; `0` or `1` disables retry (one try only).
    pub max_attempts: u32,
    /// The wait before the first retry; each subsequent wait multiplies it.
    pub base_delay: Duration,
    /// The exponential growth factor applied per retry.
    pub multiplier: u32,
    /// The ceiling every computed delay is clamped to.
    pub max_delay: Duration,
}

impl Default for RetryPolicy {
    /// 3 attempts (2 retries), 200 ms base, ×2 growth, capped at 2 s. This is the shell default.
    fn default() -> Self {
        Self {
            max_attempts: 3,
            base_delay: Duration::from_millis(200),
            multiplier: 2,
            max_delay: Duration::from_secs(2),
        }
    }
}

impl RetryPolicy {
    /// The wait before retry `index` (0-based): `min(base · multiplierⁱⁿᵈᵉˣ, max_delay)`,
    /// grown by saturating multiply and clamped every step so no overflow escapes the cap.
    #[must_use]
    pub fn delay(&self, index: u32) -> Duration {
        let mut delay = self.base_delay.min(self.max_delay);
        for _ in 0..index {
            delay = delay.saturating_mul(self.multiplier).min(self.max_delay);
        }
        delay
    }

    /// The backoff to apply after `attempt` failures (0-based), or `None` to give up: retry
    /// only while an attempt remains *and* the error is [`is_transient`].
    #[must_use]
    pub fn backoff(&self, attempt: u32, error: &TransportError) -> Option<Duration> {
        if attempt + 1 < self.max_attempts && is_transient(error) {
            Some(self.delay(attempt))
        } else {
            None
        }
    }
}

/// A [`BrainTransport`] that wraps an inner one and retries its idempotent calls on a transient
/// failure, backing off per [`RetryPolicy`] and waiting via a [`Sleeper`] (ADR-0024). `converse`
/// is forwarded unchanged. It is non-idempotent, so never retried.
pub struct RetryingTransport<T, S> {
    inner: T,
    sleeper: S,
    policy: RetryPolicy,
}

impl<T, S> RetryingTransport<T, S> {
    /// Wraps `inner`, waiting via `sleeper` on the `policy`'s schedule.
    pub fn new(inner: T, sleeper: S, policy: RetryPolicy) -> Self {
        Self {
            inner,
            sleeper,
            policy,
        }
    }
}

impl<T: BrainTransport, S: Sleeper> RetryingTransport<T, S> {
    /// Runs `call` and retries it while [`RetryPolicy::backoff`] says so, sleeping the returned
    /// delay between tries. Shared by every idempotent method; `call` re-issues the inner call
    /// each attempt (a fresh future over the same reconnecting channel), so it is generic over
    /// that method's own future type `Fut`.
    async fn retry<R, Fut>(&self, mut call: impl FnMut() -> Fut) -> Result<R, TransportError>
    where
        Fut: Future<Output = Result<R, TransportError>> + Send,
    {
        let mut attempt = 0u32;
        loop {
            match call().await {
                Ok(value) => return Ok(value),
                Err(error) => match self.policy.backoff(attempt, &error) {
                    Some(delay) => {
                        self.sleeper.sleep(delay).await;
                        attempt += 1;
                    }
                    None => return Err(error),
                },
            }
        }
    }
}

impl<T: BrainTransport, S: Sleeper> BrainTransport for RetryingTransport<T, S> {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        self.retry(|| self.inner.health()).await
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        // Pass-through: a turn is non-idempotent and its decisions stream is one-shot, so the
        // decorator never retries it. A failed turn is terminal (ADR-0024 decision 2).
        self.inner.converse(session_id, text, decisions)
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        self.retry(|| self.inner.list_sessions(limit)).await
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        self.retry(|| self.inner.session_messages(session_id)).await
    }
}
