//! `RetryingTransport`: bounded-retry resilience over the `BrainTransport` port (ADR-0024).
//!
//! A deferred refinement of the health check. The brain is a supervised local process that occasionally
//! goes away for a moment (restarting after a model swap, a momentary loopback drop), and a
//! read the overlay makes fails hard when a retry a beat later would succeed. This module adds
//! that retry as a decorator over the port rather than as code in the adapter:
//! `RetryingTransport` is itself a [`BrainTransport`] that wraps an inner one and loops the
//! repeatable calls on a transient failure, so `body_rpc`'s `BrainSeamClient` stays the thin
//! translation it was (AGENTS.md).
//!
//! Three effects are kept out of this pure crate behind seams ([`effects`]): the backoff wait
//! and the deadline on one attempt are both the [`Sleeper`] port (a real `TokioSleeper` lives
//! in the ungated shell; a `FakeSleeper` records the schedule in tests, so no wall-clock time
//! elapses), the jitter draw is a [`Randomness`] port (ADR-0024 addendum; [`FullDelay`] pins
//! it to the deterministic schedule), and dialing or reconnecting is the inner transport's job
//! (composed over a lazy channel). See [body-rpc.md](../../../docs/modules/body-rpc.md).
//!
//! Every retry decision passes through [`RetryPlan::policy_for`], which is asked about the
//! method before anything is asked about the error ([`plan`]): `health`, `list_sessions`,
//! `session_messages` and `list_due_reminders` are repeatable and get a schedule; `converse`
//! and `ack_reminder` get `None`, which runs the same loop on [`RetryPolicy::ONCE`], so a
//! refused call makes exactly one attempt without taking a path a permitted one does not.
//! [`RetryPolicy`] and [`is_transient`] ([`policy`]) then decide whether this particular
//! failure earns one of the attempts the plan allowed. `converse` never reaches that decision
//! at runtime, since a stream cannot be re-issued the way a future can, but it is classified
//! all the same so the port's methods are covered exhaustively.
//!
//! Every attempt is also bounded ([`deadline`]). The plan carries a per-method deadline beside
//! the schedule, and the decorator wraps each attempt in [`within_deadline`], so a brain that
//! accepts the connection and never answers fails as [`TransportError::Timeout`] instead of
//! hanging the caller. That failure is terminal by decision: retrying a deadline amplifies
//! load, and a timeout records that this side stopped waiting rather than that the brain
//! reported a repeat might go better (ADR-0024 deadline addendum). The plan answers a second
//! question about the same clock, [`RetryPlan::announced_deadline_for`], which is the deadline
//! the adapter tells the brain the call will be waited on. It is longer than the bound
//! enforced here by [`ANNOUNCED_DEADLINE_GRACE_MS`], because announcing a deadline also starts
//! a clock in the transport, and the bound enforced here has to expire first (ADR-0024
//! courtesy-header addendum).
//!
//! A turn is bounded by its silence rather than by its length ([`gap`]). `Converse` has no
//! deadline and will not get one, a working turn being long by design, so the plan gives it a
//! pair of gaps instead: the longest quiet allowed before its first event, and the longest
//! allowed between two of them. Every delta, tool step and status resets the clock, so the
//! bound never fires on a turn that keeps producing events and ends one that has stopped
//! (ADR-0024 idle-gap addendum). Between [`RetryPlan::deadline_for`] and
//! [`RetryPlan::gaps_for`] every call on the port is bounded, by one of the two and never by
//! both.

pub mod deadline;
pub mod effects;
pub mod gap;
pub mod plan;
pub mod policy;

pub use deadline::within_deadline;
pub use effects::{FullDelay, Randomness, Sleeper};
pub use gap::{DEFAULT_TURN_FIRST_GAP_MS, DEFAULT_TURN_IDLE_GAP_MS, TurnGaps, within_gaps};
pub use plan::{
    ANNOUNCED_DEADLINE_GRACE_MS, DEFAULT_CALL_DEADLINE, DEFAULT_PROBE_BUDGET,
    DEFAULT_PROBE_DEADLINE, RetryPlan, SeamMethod,
};
pub use policy::{RetryPolicy, is_transient};

use std::future::Future;

use futures_core::Stream;

use crate::retry::effects::jittered;
use crate::session_types::{DueReminder, SessionMessage, SessionSummary};
use crate::transport::{BrainTransport, ConfirmDecision, SeamHealth, TransportError, TurnEvent};

/// Runs `call` and retries it while [`RetryPolicy::backoff`] says so, sleeping the jittered
/// delay between tries. It is public so retrying can be composed around any fallible async
/// factory rather than only a wrapped transport: the shell's turn path wraps its eager dial in
/// it (ADR-0024 addendum), which is safe because the non-idempotent turn has not begun until
/// the dial succeeds. `call` re-issues a fresh future per attempt.
///
/// This function executes the schedule and does not decide whether repeating is allowed. It
/// assumes the caller has established that repeating `call` is safe, which is why every seam
/// method reaches it only through [`RetryPlan::policy_for`], and a direct caller such as the
/// dial takes that responsibility itself.
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
/// exactly one attempt, and `converse` streams its items through untouched under the plan's
/// gaps, which bound its silence rather than its length.
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
    /// A refused method is one the decorator must not turn into two calls carrying the same
    /// effect, however transient the failure looks. It still runs through the same loop as a
    /// permitted one, so a refused call takes no code path a permitted call does not. The
    /// deadline applies to refused calls too, since bounding a write does not repeat it.
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
        // A stream is not a future the loop could re-issue, so this is the one method that
        // cannot run through `guarded`. `SeamMethod::Converse` is refused all the same, which
        // keeps the classification exhaustive over the port (ADR-0024 decision 2).
        //
        // Not being retried does not leave it unbounded: the items pass through untouched and
        // the silence between them is bounded by the plan's gaps, so a turn that keeps
        // producing events is never cut off and one that stops is ended and reported
        // (ADR-0024 idle-gap addendum).
        within_gaps(
            self.plan.gaps_for(SeamMethod::Converse),
            &self.sleeper,
            self.inner.converse(session_id, text, decisions),
        )
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
        // The one write on the port. It runs through `guarded` like the reads and the plan
        // refuses it, so the single attempt comes from the plan rather than from a bypass.
        self.guarded(SeamMethod::AckReminder, || {
            self.inner.ack_reminder(reminder_id)
        })
        .await
    }

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        // A user-driven catalog write (ADR-0021). Like `ack_reminder` it carries an effect, so
        // the plan refuses it and exactly one attempt is made: a lost reply must not become a
        // second relabel.
        self.guarded(SeamMethod::RenameSession, || {
            self.inner.rename_session(session_id, title)
        })
        .await
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        // A user-driven destructive write (ADR-0021). The plan refuses it too, so exactly one
        // attempt is made: a silent retry could remove a chat that a still-streaming turn
        // re-materialized.
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
        // effect, so the plan refuses it and exactly one attempt is made: a lost reply must not
        // re-assert a pinned value the user's next toggle reversed.
        self.guarded(SeamMethod::SetSessionPinned, || {
            self.inner.set_session_pinned(session_id, pinned)
        })
        .await
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        // A read of the settings record, repeatable with the other reads: a retry returns a
        // fresh answer to the same question and changes nothing.
        self.guarded(SeamMethod::GetPreferences, || self.inner.get_preferences())
            .await
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        // A user-driven write. Last write wins in the store, so a repeat cannot duplicate an
        // effect, but the catalog-write convention still allows exactly one attempt: a lost
        // reply must not re-assert a value the user's next change reversed.
        self.guarded(SeamMethod::SetPreference, || {
            self.inner.set_preference(key, value)
        })
        .await
    }
}
