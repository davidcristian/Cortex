//! `RetryingTransport`: bounded-retry resilience over the `BrainTransport` port (ADR-0024).

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
    /// Runs `call` under the plan's verdict for `method`: [`retry_with`] on the resolved schedule
    /// when the method is repeatable, and on [`RetryPolicy::ONCE`] when the plan refuses it, which
    /// makes exactly one attempt and never waits.
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
