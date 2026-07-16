//! `RetryingTransport`: bounded-retry resilience over the `BrainTransport` port (ADR-0024).

pub mod plan;
pub mod policy;

pub use plan::{DEFAULT_PROBE_BUDGET, RetryPlan, SeamMethod};
pub use policy::{RetryPolicy, is_transient};

use std::future::Future;
use std::time::Duration;

use futures_core::Stream;

use crate::transport::{
    BrainTransport, ConfirmDecision, DueReminder, SeamHealth, SessionMessage, SessionSummary,
    TransportError, TurnEvent,
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
/// permanent 1 yields exactly the deterministic v1 schedule.
#[derive(Clone, Copy, Debug, Default)]
pub struct FullDelay;

impl Randomness for FullDelay {
    fn unit(&self) -> f64 {
        1.0
    }
}

/// `delay` scaled by equal jitter: half is kept as a floor (this wait exists to give a restarting
/// brain time to come back), the other half is scaled by the sanitized draw.
fn jittered(delay: Duration, randomness: &impl Randomness) -> Duration {
    let draw = randomness.unit();
    let scale = if draw.is_finite() {
        draw.clamp(0.0, 1.0)
    } else {
        1.0
    };
    delay.mul_f64(0.5 + 0.5 * scale)
}

/// Runs `call` and retries it while [`RetryPolicy::backoff`] says so, sleeping the (jittered) delay
/// between tries.
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

/// A [`BrainTransport`] that wraps an inner one and retries its repeatable calls on a transient
/// failure, backing off per the [`RetryPlan`]'s schedule for that method (jittered through its
/// [`Randomness`]) and waiting via a [`Sleeper`] (ADR-0024).
pub struct RetryingTransport<T, S, R = FullDelay> {
    inner: T,
    sleeper: S,
    randomness: R,
    plan: RetryPlan,
}

impl<T, S> RetryingTransport<T, S, FullDelay> {
    /// Wraps `inner`, waiting via `sleeper` on the `plan`'s deterministic schedule
    /// ([`FullDelay`]: no jitter, the v1 behavior). A bare [`RetryPolicy`] converts into a
    /// plan that governs the reads and leaves the probe budget at its default.
    pub fn new(inner: T, sleeper: S, plan: impl Into<RetryPlan>) -> Self {
        Self::with_randomness(inner, sleeper, FullDelay, plan)
    }
}

impl<T, S, R> RetryingTransport<T, S, R> {
    /// Wraps `inner`, waiting via `sleeper` on the `plan`'s schedule with each delay
    /// equal-jittered through `randomness` (ADR-0024 addendum).
    pub fn with_randomness(
        inner: T,
        sleeper: S,
        randomness: R,
        plan: impl Into<RetryPlan>,
    ) -> Self {
        Self {
            inner,
            sleeper,
            randomness,
            plan: plan.into(),
        }
    }
}

impl<T: BrainTransport, S: Sleeper, R: Randomness> RetryingTransport<T, S, R> {
    /// Runs `call` under the plan's verdict for `method`: [`retry_with`] on the resolved
    /// schedule when the method is repeatable, and on [`RetryPolicy::ONCE`] when the plan
    /// refuses it, which makes exactly one attempt and never waits.
    async fn guarded<Out, Fut>(
        &self,
        method: SeamMethod,
        call: impl FnMut() -> Fut,
    ) -> Result<Out, TransportError>
    where
        Fut: Future<Output = Result<Out, TransportError>> + Send,
    {
        let policy = self.plan.policy_for(method).unwrap_or(RetryPolicy::ONCE);
        retry_with(policy, &self.sleeper, &self.randomness, call).await
    }
}

impl<T: BrainTransport, S: Sleeper, R: Randomness> BrainTransport for RetryingTransport<T, S, R> {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        self.guarded(SeamMethod::Health, || self.inner.health())
            .await
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        // Pass-through, and the one method that cannot even reach the gate: a stream is not a
        // future the loop could re-issue. `SeamMethod::Converse` is refused all the same, so
        // the classification stays exhaustive over the port (ADR-0024 decision 2).
        self.inner.converse(session_id, text, decisions)
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        self.guarded(SeamMethod::ListSessions, || self.inner.list_sessions(limit))
            .await
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        self.guarded(SeamMethod::SessionMessages, || {
            self.inner.session_messages(session_id)
        })
        .await
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        self.guarded(SeamMethod::ListDueReminders, || {
            self.inner.list_due_reminders()
        })
        .await
    }

    async fn ack_reminder(&self, reminder_id: &str) -> Result<bool, TransportError> {
        // The one write on the port. It goes through the same door as the reads and the plan
        // refuses it, so the single attempt is the gate's answer rather than a bypass.
        self.guarded(SeamMethod::AckReminder, || {
            self.inner.ack_reminder(reminder_id)
        })
        .await
    }
}
