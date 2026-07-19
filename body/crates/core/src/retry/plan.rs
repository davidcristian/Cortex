//! [`SeamMethod`] and [`RetryPlan`]: which seam call may be retried at all, and on what
//! schedule.

use std::time::Duration;

use crate::retry::policy::RetryPolicy;

/// The ceiling a `Health` probe's backoff is trimmed to by default, chosen so the shipped
/// defaults are unaffected: the default schedule's worst case is 600 ms, well inside this, so
/// the budget binds only once someone turns the read knobs up.
pub const DEFAULT_PROBE_BUDGET: Duration = Duration::from_secs(1);

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

/// The retry schedule each seam method runs under, resolved through the repeatability gate.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetryPlan {
    /// The schedule for the repeatable reads (`ListSessions`, `GetSessionMessages`,
    /// `ListDueReminders`) and the starting point the probe's is trimmed from.
    pub reads: RetryPolicy,
    /// The most backoff a `Health` probe may spend before answering. See
    /// [`RetryPolicy::within`] for what "trimmed to fit" means and
    /// [`DEFAULT_PROBE_BUDGET`] for why the default changes nothing.
    pub probe_budget: Duration,
}

impl Default for RetryPlan {
    /// The [`RetryPolicy`] default for reads, with the probe budget that does not bind it.
    fn default() -> Self {
        Self {
            reads: RetryPolicy::default(),
            probe_budget: DEFAULT_PROBE_BUDGET,
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
            SeamMethod::Health => self.reads.within(self.probe_budget),
            _ => self.reads,
        })
    }
}
