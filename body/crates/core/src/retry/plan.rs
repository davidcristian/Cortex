//! [`SeamMethod`] and [`RetryPlan`]: which seam call may be retried at all, and on what
//! schedule.

use std::time::Duration;

use crate::retry::policy::RetryPolicy;

/// The ceiling a `Health` probe spends by default, backoff **and** attempts together: with the
/// shipped deadline the probe keeps two of the read schedule's three attempts (250 + 200 + 250
/// fits, adding a third does not), so the indicator's verdict arrives inside 700 ms.
pub const DEFAULT_PROBE_BUDGET: Duration = Duration::from_secs(1);

/// How long a `Health` probe may wait for one answer.
pub const DEFAULT_PROBE_DEADLINE: Duration = Duration::from_millis(250);

/// How long every other unary call may wait for one answer.
pub const DEFAULT_CALL_DEADLINE: Duration = Duration::from_secs(5);

/// How much longer the deadline the body **announces** to the brain is than the one it
/// **enforces**, in milliseconds ([`RetryPlan::announced_deadline_for`], ADR-0024 courtesy-header
/// addendum).
pub const ANNOUNCED_DEADLINE_GRACE_MS: u64 = 250;

/// Every call on the [`crate::transport::BrainTransport`] port, named so a retry decision can
/// be made about it. Exhaustive by construction: a new port method that wants resilience has
/// to appear here and be classified, which is the whole point (see the module docs).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SeamMethod {
    /// `BrainService.Health`: a readiness probe. Reads nothing, writes nothing.
    Health,
    /// `BrainService.Converse`: one conversational turn.
    Converse,
    /// `BrainService.ListSessions`: the chat switcher's view of the store.
    ListSessions,
    /// `BrainService.GetSessionMessages`: one chat's persisted history.
    SessionMessages,
    /// `BrainService.ListDueReminders`: fired-but-undelivered reminders.
    ListDueReminders,
    /// `BrainService.AckReminder`: marks one reminder delivered.
    AckReminder,
    /// `BrainService.RenameSession`: the overlay's user-driven relabel of a chat.
    RenameSession,
    /// `BrainService.DeleteSession`: the overlay's user-driven destructive removal of a chat.
    DeleteSession,
    /// `BrainService.SetSessionPinned`: the overlay's user-driven pin toggle on a chat.
    SetSessionPinned,
    /// `BrainService.GetPreferences`: the user's settings record, read whole.
    GetPreferences,
    /// `BrainService.SetPreference`: one setting written by the user.
    SetPreference,
}

impl SeamMethod {
    /// Whether repeating this call is observably the same as making it once. **This is the
    /// safety property every retry rests on**, and the one decision no policy, budget, or
    /// error code may override.
    #[must_use]
    pub const fn repeatable(self) -> bool {
        match self {
            Self::Health
            | Self::ListSessions
            | Self::SessionMessages
            | Self::ListDueReminders
            | Self::GetPreferences => true,
            Self::Converse
            | Self::AckReminder
            | Self::RenameSession
            | Self::DeleteSession
            | Self::SetSessionPinned
            | Self::SetPreference => false,
        }
    }
}

/// The retry schedule and the deadline each seam method runs under, resolved through the
/// repeatability gate.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetryPlan {
    /// The schedule for the repeatable reads (`ListSessions`, `GetSessionMessages`,
    /// `ListDueReminders`) and the starting point the probe's is trimmed from.
    pub reads: RetryPolicy,
    /// The most a `Health` probe may spend before answering, attempts and backoff together.
    /// See [`RetryPolicy::within`] for what "trimmed to fit" means and
    /// [`DEFAULT_PROBE_BUDGET`] for what the default leaves the probe.
    pub probe_budget: Duration,
    /// How long one `Health` attempt may wait for an answer ([`DEFAULT_PROBE_DEADLINE`]).
    pub probe_deadline: Duration,
    /// How long every other unary attempt may wait for an answer ([`DEFAULT_CALL_DEADLINE`]).
    pub call_deadline: Duration,
}

impl Default for RetryPlan {
    /// The [`RetryPolicy`] default for reads, with the shipped budget and deadlines.
    fn default() -> Self {
        Self {
            reads: RetryPolicy::default(),
            probe_budget: DEFAULT_PROBE_BUDGET,
            probe_deadline: DEFAULT_PROBE_DEADLINE,
            call_deadline: DEFAULT_CALL_DEADLINE,
        }
    }
}

impl From<RetryPolicy> for RetryPlan {
    /// A bare schedule read as a plan: it governs the reads, and the probe is trimmed to the
    /// default budget. This is what lets a caller that has no opinion about the probe keep
    /// passing one policy.
    fn from(reads: RetryPolicy) -> Self {
        Self {
            reads,
            ..Self::default()
        }
    }
}

impl RetryPlan {
    /// The schedule `method` retries on, or **`None` when it may not be retried at all**.
    #[must_use]
    pub fn policy_for(&self, method: SeamMethod) -> Option<RetryPolicy> {
        if !method.repeatable() {
            return None;
        }
        Some(match method {
            SeamMethod::Health => self.reads.within(self.probe_budget, self.probe_deadline),
            _ => self.reads,
        })
    }

    /// How long one attempt at `method` may wait for an answer, or **`None` when it is not the
    /// clock's business**.
    #[must_use]
    pub fn deadline_for(&self, method: SeamMethod) -> Option<Duration> {
        match method {
            SeamMethod::Health => Some(self.probe_deadline),
            // The one call a clock must not end: see above.
            SeamMethod::Converse => None,
            SeamMethod::ListSessions
            | SeamMethod::SessionMessages
            | SeamMethod::ListDueReminders
            | SeamMethod::AckReminder
            | SeamMethod::RenameSession
            | SeamMethod::DeleteSession
            | SeamMethod::SetSessionPinned
            | SeamMethod::GetPreferences
            | SeamMethod::SetPreference => Some(self.call_deadline),
        }
    }

    /// How long one attempt at `method` **tells the brain** it will be waited on, or `None` when
    /// it tells it nothing (ADR-0024 courtesy-header addendum).
    #[must_use]
    pub fn announced_deadline_for(&self, method: SeamMethod) -> Option<Duration> {
        let grace = Duration::from_millis(ANNOUNCED_DEADLINE_GRACE_MS);
        self.deadline_for(method)
            .map(|deadline| deadline.saturating_add(grace))
    }
}
