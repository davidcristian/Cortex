//! [`SeamMethod`] and [`RetryPlan`]: which brain call may be retried, and on what schedule.
//!
//! Repeatability is checked first, because it is a fact about the call, and only then the failure.

use std::time::Duration;

use crate::retry::gap::TurnGaps;
use crate::retry::policy::RetryPolicy;

/// The most a `Health` probe may take by default, backoff and attempts together. With the shipped
/// deadline it keeps two of the read schedule's three attempts (250 + 200 + 250 fits, a third
/// does not), so the indicator's answer arrives inside 700 ms.
pub const DEFAULT_PROBE_BUDGET: Duration = Duration::from_secs(1);

/// How long a `Health` probe may wait for one answer. Brain-side `Health` is synchronous and
/// lock free, and on loopback it answers in single-digit milliseconds.
pub const DEFAULT_PROBE_DEADLINE: Duration = Duration::from_millis(250);

/// How long every other unary call may wait for one answer.
pub const DEFAULT_CALL_DEADLINE: Duration = Duration::from_secs(5);

/// How much longer the deadline the body announces to the brain is than the one it enforces, in
/// milliseconds. There is a margin because the transport starts a clock of its own from the
/// announcement, and the body's own bound has to expire first.
pub const ANNOUNCED_DEADLINE_GRACE_MS: u64 = 250;

/// Every call on the [`crate::transport::BrainTransport`] port, named so a retry decision can be
/// made about it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SeamMethod {
    /// `BrainService.Health`: a readiness probe.
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
    /// `BrainService.SetSessionHoisted`: the overlay's user-driven hoist toggle on a chat.
    SetSessionHoisted,
    /// `BrainService.GetPreferences`: the user's settings record, read whole.
    GetPreferences,
    /// `BrainService.SetPreference`: one setting written by the user.
    SetPreference,
}

impl SeamMethod {
    /// Whether repeating this call is observably the same as making it once. The five reads are;
    /// a turn and every write are not, so each of those gets exactly one attempt.
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
            | Self::SetSessionHoisted
            | Self::SetPreference => false,
        }
    }
}

/// The retry schedule and the deadline each call runs under, once repeatability has been
/// checked.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetryPlan {
    /// The schedule for the repeatable reads (`ListSessions`, `GetSessionMessages`,
    /// `ListDueReminders`) and the starting point the probe's is trimmed from.
    pub reads: RetryPolicy,
    /// The most a `Health` probe may spend before answering, attempts and backoff together.
    pub probe_budget: Duration,
    /// How long one `Health` attempt may wait for an answer ([`DEFAULT_PROBE_DEADLINE`]).
    pub probe_deadline: Duration,
    /// How long every other unary attempt may wait for an answer ([`DEFAULT_CALL_DEADLINE`]).
    pub call_deadline: Duration,
    /// The two silences a `Converse` stream runs under ([`RetryPlan::gaps_for`], which lives in
    /// [`crate::retry::gap`] with everything else that defines what a gap means).
    pub turn_gaps: TurnGaps,
}

impl Default for RetryPlan {
    /// The [`RetryPolicy`] default for reads, with the shipped budget and deadlines.
    fn default() -> Self {
        Self {
            reads: RetryPolicy::default(),
            probe_budget: DEFAULT_PROBE_BUDGET,
            probe_deadline: DEFAULT_PROBE_DEADLINE,
            call_deadline: DEFAULT_CALL_DEADLINE,
            turn_gaps: TurnGaps::default(),
        }
    }
}

impl From<RetryPolicy> for RetryPlan {
    /// A bare schedule read as a plan: it governs the reads, and the probe is trimmed to the
    /// default budget.
    fn from(reads: RetryPolicy) -> Self {
        Self {
            reads,
            ..Self::default()
        }
    }
}

impl RetryPlan {
    /// The schedule `method` retries on, or `None` when it may not be retried at all.
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

    /// How long one attempt at `method` may wait for an answer, or `None` when no clock bounds it.
    #[must_use]
    pub fn deadline_for(&self, method: SeamMethod) -> Option<Duration> {
        match method {
            SeamMethod::Health => Some(self.probe_deadline),
            SeamMethod::Converse => None,
            SeamMethod::ListSessions
            | SeamMethod::SessionMessages
            | SeamMethod::ListDueReminders
            | SeamMethod::AckReminder
            | SeamMethod::RenameSession
            | SeamMethod::DeleteSession
            | SeamMethod::SetSessionHoisted
            | SeamMethod::GetPreferences
            | SeamMethod::SetPreference => Some(self.call_deadline),
        }
    }

    /// How long one attempt at `method` tells the brain it will be waited on, or `None` when it
    /// announces nothing.
    #[must_use]
    pub fn announced_deadline_for(&self, method: SeamMethod) -> Option<Duration> {
        let grace = Duration::from_millis(ANNOUNCED_DEADLINE_GRACE_MS);
        self.deadline_for(method)
            .map(|deadline| deadline.saturating_add(grace))
    }
}
