//! `RetryingTransport`: bounded-retry resilience over the `BrainTransport` port (ADR-0024).
//!
//! Slice 2's deferred refinement. The brain is a supervised local process that occasionally
//! blinks out (restarting after a model swap, a momentary loopback drop) and a read the
//! overlay makes fails hard when a retry a beat later would succeed. This module adds that
//! retry as a **decorator over the port**, not code in the adapter: `RetryingTransport` *is* a
//! [`BrainTransport`] that wraps an inner one and loops the repeatable calls on a transient
//! failure, so `body_rpc`'s `BrainSeamClient` stays the thin translation it was (AGENTS.md).
//!
//! Three effects are kept out of this pure crate behind seams: the backoff *wait* is a
//! [`Sleeper`] port (a real `TokioSleeper` lives in the ungated shell; a `FakeSleeper` records
//! the schedule in tests, so no wall-clock elapses), the jitter *draw* is a [`Randomness`] port
//! (ADR-0024 addendum; [`FullDelay`] pins it to the deterministic schedule), and
//! dialing/reconnecting is the inner transport's job (composed over a lazy channel).
//! See [body-rpc.md](../../../docs/modules/body-rpc.md).
//!
//! **Every retry decision goes through one door**, [`RetryPlan::policy_for`], and it is asked
//! about the *method* before anything is asked about the error ([`plan`]): `health`,
//! `list_sessions`, `session_messages` and `list_due_reminders` are repeatable and get a
//! schedule; `converse` and `ack_reminder` get `None`, which runs the same loop on
//! [`RetryPolicy::ONCE`], so a refused call makes exactly one attempt without taking a path a
//! permitted one does not.
//! [`RetryPolicy`] and [`is_transient`] ([`policy`]) then decide whether *this* failure earns
//! one of the attempts the gate allowed. `converse` never reaches the gate at runtime, since a
//! stream cannot be re-issued the way a future can, but it is classified all the same so the
//! port's methods are covered exhaustively.

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

/// Runs `call` and retries it while [`RetryPolicy::backoff`] says so, sleeping the (jittered)
/// delay between tries. The retry loop itself, public so patience can be composed around any
/// fallible async factory, not only a wrapped transport: the shell's turn path wraps its eager
/// dial in it (ADR-0024 addendum), which is safe because the non-idempotent turn has not begun
/// until the dial succeeds. `call` re-issues a fresh future per attempt.
///
/// This is the schedule executor, not the gate. It takes the caller's word that repeating
/// `call` is safe, which is why every *seam method* reaches it only through
/// [`RetryPlan::policy_for`]; a direct caller (the dial) is asserting that safety itself.
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

/// A [`BrainTransport`] that wraps an inner one and retries its repeatable calls on a transient
/// failure, backing off per the [`RetryPlan`]'s schedule for that method (jittered through its
/// [`Randomness`]) and waiting via a [`Sleeper`] (ADR-0024). A method the plan refuses gets
/// exactly one attempt, and `converse` is forwarded as the stream it is.
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
    ///
    /// The refusal is not an optimization. It is where the decorator declines to turn a call
    /// with an effect into two of them, no matter how transient the failure looks. It runs
    /// through the same loop as a permission on purpose: a refused call must not take a code
    /// path that only a refused call can reach.
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
