//! `RetryingTransport`: bounded-retry resilience over the `BrainTransport` port.

pub mod deadline;
pub mod effects;
pub mod gap;
pub mod plan;
pub mod policy;

pub use deadline::within_deadline;
pub use effects::{FullDelay, Randomness, Sleeper};
pub use gap::{
    DEFAULT_TURN_FIRST_GAP_MS, DEFAULT_TURN_HEARTBEAT_GAP_MS, DEFAULT_TURN_IDLE_GAP_MS,
    HEARTBEAT_PERIOD_MS, TurnGaps, within_gaps,
};
pub use plan::{
    ANNOUNCED_DEADLINE_GRACE_MS, DEFAULT_CALL_DEADLINE, DEFAULT_PROBE_BUDGET,
    DEFAULT_PROBE_DEADLINE, RetryPlan, RpcMethod,
};
pub use policy::{RetryPolicy, is_transient};

use std::future::Future;

use futures_core::Stream;

use crate::retry::effects::jittered;
use crate::session_types::{DueReminder, SessionMessage, SessionSummary};
use crate::transport::{BrainTransport, ConfirmDecision, RpcHealth, TransportError, TurnEvent};

/// Runs `call`, retrying while the policy allows and sleeping the jittered delay between tries.
///
/// # Errors
///
/// The last attempt's [`TransportError`], once the policy stops retrying.
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
/// [`Randomness`]) and waiting via a [`Sleeper`].
pub struct RetryingTransport<T, S, R = FullDelay> {
    inner: T,
    sleeper: S,
    randomness: R,
    plan: RetryPlan,
}

impl<T, S> RetryingTransport<T, S, FullDelay> {
    /// Wraps `inner`, waiting via `sleeper` on the `plan`'s deterministic schedule ([`FullDelay`]:
    /// no jitter, the v1 behavior).
    pub fn new(inner: T, sleeper: S, plan: impl Into<RetryPlan>) -> Self {
        Self::with_randomness(inner, sleeper, FullDelay, plan)
    }
}

impl<T, S, R> RetryingTransport<T, S, R> {
    /// Wraps `inner`, waiting via `sleeper` on the `plan`'s schedule with each delay equal-jittered
    /// through `randomness`.
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
    /// Runs `call` under the plan's answer for `method`: the resolved schedule when the method is
    /// repeatable, and [`RetryPolicy::ONCE`] when it is not, which makes one attempt and never
    /// waits. Each attempt is bounded by the plan's deadline for that method.
    async fn guarded<Out, Fut>(
        &self,
        method: RpcMethod,
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
    async fn health(&self) -> Result<RpcHealth, TransportError> {
        self.guarded(RpcMethod::Health, || self.inner.health())
            .await
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        within_gaps(
            self.plan.gaps_for(RpcMethod::Converse),
            &self.sleeper,
            self.inner.converse(session_id, text, decisions),
        )
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        self.guarded(RpcMethod::ListSessions, || self.inner.list_sessions(limit))
            .await
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        self.guarded(RpcMethod::SessionMessages, || {
            self.inner.session_messages(session_id)
        })
        .await
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        self.guarded(RpcMethod::ListDueReminders, || {
            self.inner.list_due_reminders()
        })
        .await
    }

    async fn ack_reminder(
        &self,
        reminder_id: &str,
        fired_at_unix_ms: i64,
    ) -> Result<bool, TransportError> {
        self.guarded(RpcMethod::AckReminder, || {
            self.inner.ack_reminder(reminder_id, fired_at_unix_ms)
        })
        .await
    }

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        self.guarded(RpcMethod::RenameSession, || {
            self.inner.rename_session(session_id, title)
        })
        .await
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        self.guarded(RpcMethod::DeleteSession, || {
            self.inner.delete_session(session_id)
        })
        .await
    }

    async fn set_session_hoisted(
        &self,
        session_id: &str,
        hoisted: bool,
    ) -> Result<(), TransportError> {
        self.guarded(RpcMethod::SetSessionHoisted, || {
            self.inner.set_session_hoisted(session_id, hoisted)
        })
        .await
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        self.guarded(RpcMethod::GetPreferences, || self.inner.get_preferences())
            .await
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        self.guarded(RpcMethod::SetPreference, || {
            self.inner.set_preference(key, value)
        })
        .await
    }
}
