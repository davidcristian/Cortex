//! `RetryingTransport`: bounded-retry resilience over the `BrainTransport` port (ADR-0024).
//!
//! Slice 2's deferred refinement. The brain is a supervised local process that occasionally
//! blinks out (restarting after a model swap, a momentary loopback drop) and a read the
//! overlay makes fails hard when a retry a beat later would succeed. This module adds that
//! retry as a **decorator over the port**, not code in the adapter: `RetryingTransport` *is* a
//! [`BrainTransport`] that wraps an inner one and loops the idempotent calls on a transient
//! failure, so `body_rpc`'s `BrainSeamClient` stays the thin translation it was (AGENTS.md).
//!
//! Three effects are kept out of this pure crate behind seams: the backoff *wait* is a
//! [`Sleeper`] port (a real `TokioSleeper` lives in the ungated shell; a `FakeSleeper` records
//! the schedule in tests, so no wall-clock elapses), the jitter *draw* is a [`Randomness`] port
//! (ADR-0024 addendum; [`FullDelay`] pins it to the deterministic schedule), and
//! dialing/reconnecting is the inner transport's job (composed over a lazy channel).
//! See [body-rpc.md](../../../docs/modules/body-rpc.md).
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

/// A randomness effect: one unit-interval draw per backoff, the seam jitter needs (ADR-0024
/// addendum). Mirrors [`Sleeper`]: the real adapter lives in the ungated shell, tests inject
/// a scripted fake, and [`FullDelay`] (the constant-1 source) turns jitter off structurally.
pub trait Randomness: Send + Sync {
    /// A value in `[0, 1]`. The retry loop sanitizes it defensively (out-of-range clamped, a
    /// non-finite draw treated as the full delay), so a misbehaving source degrades the spread
    /// rather than panicking the `Duration` math.
    fn unit(&self) -> f64;
}

/// The constant-1 [`Randomness`]: equal jitter scales a delay by `0.5 + 0.5 * unit()`, so a
/// permanent 1 yields exactly the deterministic v1 schedule. [`RetryingTransport::new`]
/// composes it by default; a jittered composition opts in via
/// [`RetryingTransport::with_randomness`].
#[derive(Clone, Copy, Debug, Default)]
pub struct FullDelay;

impl Randomness for FullDelay {
    fn unit(&self) -> f64 {
        1.0
    }
}

/// `delay` scaled by equal jitter: half is kept as a floor (this wait exists to give a
/// restarting brain time to come back), the other half is scaled by the sanitized draw. A
/// non-finite draw (`clamp` would propagate a `NaN`, which `mul_f64` rejects) falls back to
/// the full delay, so a misbehaving source cannot panic the `Duration` math.
fn jittered(delay: Duration, randomness: &impl Randomness) -> Duration {
    let draw = randomness.unit();
    let scale = if draw.is_finite() {
        draw.clamp(0.0, 1.0)
    } else {
        1.0
    };
    delay.mul_f64(0.5 + 0.5 * scale)
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

/// Runs `call` and retries it while [`RetryPolicy::backoff`] says so, sleeping the (jittered)
/// delay between tries. The retry loop itself, public so patience can be composed around any
/// fallible async factory, not only a wrapped transport: the shell's turn path wraps its eager
/// dial in it (ADR-0024 addendum), which is safe because the non-idempotent turn has not begun
/// until the dial succeeds. `call` re-issues a fresh future per attempt.
///
/// # Errors
///
/// The last attempt's [`TransportError`], once the policy declines to retry: a non-transient
/// error immediately, a transient one after the attempts are exhausted.
pub async fn retry_with<R, Fut>(
    policy: RetryPolicy,
    sleeper: &impl Sleeper,
    randomness: &impl Randomness,
    mut call: impl FnMut() -> Fut,
) -> Result<R, TransportError>
where
    Fut: Future<Output = Result<R, TransportError>> + Send,
{
    let mut attempt = 0u32;
    loop {
        match call().await {
            Ok(value) => return Ok(value),
            Err(error) => match policy.backoff(attempt, &error) {
                Some(delay) => {
                    sleeper.sleep(jittered(delay, randomness)).await;
                    attempt += 1;
                }
                None => return Err(error),
            },
        }
    }
}

/// A [`BrainTransport`] that wraps an inner one and retries its idempotent calls on a transient
/// failure, backing off per [`RetryPolicy`] (jittered through its [`Randomness`]) and waiting
/// via a [`Sleeper`] (ADR-0024). `converse` is forwarded unchanged. It is non-idempotent, so
/// never retried.
pub struct RetryingTransport<T, S, R = FullDelay> {
    inner: T,
    sleeper: S,
    randomness: R,
    policy: RetryPolicy,
}

impl<T, S> RetryingTransport<T, S, FullDelay> {
    /// Wraps `inner`, waiting via `sleeper` on the `policy`'s deterministic schedule
    /// ([`FullDelay`]: no jitter, the v1 behavior).
    pub fn new(inner: T, sleeper: S, policy: RetryPolicy) -> Self {
        Self::with_randomness(inner, sleeper, FullDelay, policy)
    }
}

impl<T, S, R> RetryingTransport<T, S, R> {
    /// Wraps `inner`, waiting via `sleeper` on the `policy`'s schedule with each delay
    /// equal-jittered through `randomness` (ADR-0024 addendum).
    pub fn with_randomness(inner: T, sleeper: S, randomness: R, policy: RetryPolicy) -> Self {
        Self {
            inner,
            sleeper,
            randomness,
            policy,
        }
    }
}

impl<T: BrainTransport, S: Sleeper, R: Randomness> RetryingTransport<T, S, R> {
    /// The shared per-method loop: [`retry_with`] over this transport's own collaborators.
    async fn retry<Out, Fut>(&self, call: impl FnMut() -> Fut) -> Result<Out, TransportError>
    where
        Fut: Future<Output = Result<Out, TransportError>> + Send,
    {
        retry_with(self.policy, &self.sleeper, &self.randomness, call).await
    }
}

impl<T: BrainTransport, S: Sleeper, R: Randomness> BrainTransport for RetryingTransport<T, S, R> {
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
