//! `RetryingTransport`: bounded-retry resilience over the `BrainTransport` port (ADR-0024).
//!
//! Slice 2's deferred refinement. The brain is a supervised local process that occasionally
//! blinks out (restarting after a model swap, a momentary loopback drop) and a read the
//! overlay makes fails hard when a retry a beat later would succeed. This module adds that
//! retry as a **decorator over the port**, not code in the adapter: `RetryingTransport` *is* a
//! [`BrainTransport`] that wraps an inner one and loops the repeatable calls on a transient
//! failure, so `body_rpc`'s `BrainSeamClient` stays the thin translation it was (AGENTS.md).
//!
//! Three effects are kept out of this pure crate behind seams ([`effects`]): the backoff *wait*
//! and the *deadline* on one attempt are both the [`Sleeper`] port (a real `TokioSleeper` lives
//! in the ungated shell; a `FakeSleeper` records the schedule in tests, so no wall-clock
//! elapses), the jitter *draw* is a [`Randomness`] port
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
//!
//! **Every attempt is also bounded** ([`deadline`]). The plan carries a per-method deadline
//! beside the schedule, and the decorator wraps each attempt in [`within_deadline`], so a brain
//! that accepts the connection and never answers fails as [`TransportError::Timeout`] instead
//! of hanging the caller. That failure is terminal by decision, not by omission: a retried
//! deadline is the classic load amplifier, and a timeout is our own decision to stop waiting
//! rather than the brain's report that a repeat might go better (ADR-0024 deadline addendum).

pub mod deadline;
pub mod effects;
pub mod plan;
pub mod policy;

pub use deadline::within_deadline;
pub use effects::{FullDelay, Randomness, Sleeper};
pub use plan::{
    DEFAULT_CALL_DEADLINE, DEFAULT_PROBE_BUDGET, DEFAULT_PROBE_DEADLINE, RetryPlan, SeamMethod,
};
pub use policy::{RetryPolicy, is_transient};

use std::future::Future;

use futures_core::Stream;

use crate::retry::effects::jittered;
use crate::session_types::{DueReminder, SessionMessage, SessionSummary};
use crate::transport::{BrainTransport, ConfirmDecision, SeamHealth, TransportError, TurnEvent};

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
    /// refuses it, which makes exactly one attempt and never waits. Each attempt is bounded by
    /// the plan's deadline for that method ([`within_deadline`]), so no attempt can outlive the
    /// answer's usefulness however the loop above it is configured.
    ///
    /// The refusal is not an optimization. It is where the decorator declines to turn a call
    /// with an effect into two of them, no matter how transient the failure looks. It runs
    /// through the same loop as a permission on purpose: a refused call must not take a code
    /// path that only a refused call can reach. The deadline is applied on the same terms, to
    /// the refused calls too: bounding a write is not repeating it.
    async fn guarded<Out, Fut>(
        &self,
        method: SeamMethod,
        mut call: impl FnMut() -> Fut,
    ) -> Result<Out, TransportError>
    where
        Fut: Future<Output = Result<Out, TransportError>> + Send,
        Out: Send,
    {
        let policy = self.plan.policy_for(method).unwrap_or(RetryPolicy::ONCE);
        let deadline = self.plan.deadline_for(method);
        retry_with(policy, &self.sleeper, &self.randomness, || {
            within_deadline(deadline, &self.sleeper, call())
        })
        .await
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

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        // A user-driven catalog write (ADR-0021). Like `ack_reminder` it carries an effect, so
        // the plan refuses it and the same door grants exactly one attempt: a lost reply must
        // not become a silent second relabel.
        self.guarded(SeamMethod::RenameSession, || {
            self.inner.rename_session(session_id, title)
        })
        .await
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        // A user-driven DESTRUCTIVE write (ADR-0021). The plan refuses it too, so the same door
        // grants exactly one attempt: a destroy is the last call to re-issue automatically, and a
        // silent retry could remove a chat re-materialized by a still-streaming turn.
        self.guarded(SeamMethod::DeleteSession, || {
            self.inner.delete_session(session_id)
        })
        .await
    }

    async fn set_session_pinned(
        &self,
        session_id: &str,
        pinned: bool,
    ) -> Result<(), TransportError> {
        // A user-driven catalog write (ADR-0021 pinning addendum). Like rename it carries an
        // effect, so the plan refuses it and the same door grants exactly one attempt: a lost
        // reply must not silently re-assert a pinned value the user's next toggle reversed.
        self.guarded(SeamMethod::SetSessionPinned, || {
            self.inner.set_session_pinned(session_id, pinned)
        })
        .await
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        // A read of the settings record, repeatable with the other reads: the retry returns a
        // fresh answer to the same question and touches nothing.
        self.guarded(SeamMethod::GetPreferences, || self.inner.get_preferences())
            .await
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        // A user-driven write. Last write wins in the store, so a repeat cannot duplicate an
        // effect, but the catalog-write convention still grants exactly one attempt: a lost reply
        // must not re-assert a value the user's next change reversed.
        self.guarded(SeamMethod::SetPreference, || {
            self.inner.set_preference(key, value)
        })
        .await
    }
}
