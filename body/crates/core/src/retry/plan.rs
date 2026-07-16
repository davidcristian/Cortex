//! [`SeamMethod`] and [`RetryPlan`]: which seam call may be retried at all, and on what
//! schedule.
//!
//! Retry rests on one property, and it is not an error code: **repeating the call must be
//! observably the same as making it once**. A transient status says the brain could not serve
//! the call; it never says the brain did not already run it. So the decision is made in that
//! order here: [`SeamMethod::repeatable`] first (a fact about the call), then
//! [`crate::retry::is_transient`] (a fact about the failure).
//!
//! Before this module the order held only by hand. `RetryingTransport` retried four methods
//! and forwarded two because two `impl` bodies were written that way, and adding a seventh
//! method by copying a retried one would have silently retried it with nothing to catch it.
//! [`RetryPlan::policy_for`] is now the single door: it answers `None` for a method that may
//! not be repeated, and the decorator makes exactly one attempt on a `None`. Adding a variant
//! to [`SeamMethod`] fails to compile until [`SeamMethod::repeatable`] classifies it.
//!
//! The schedule half is per method for one live reason. The connection indicator renders a
//! `Health` probe's answer (`crate::link`), so patience there is time the dot spends claiming
//! a state the seam has stopped proving. [`RetryPlan::probe_budget`] caps it, and the read
//! knobs cannot drag it along: turning `CORTEX_BRAIN_RETRY_ATTEMPTS` up buys a session read
//! more patience without ever buying the indicator a longer lie.

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
}

impl SeamMethod {
    /// Whether repeating this call is observably the same as making it once. **This is the
    /// safety property every retry rests on**, and the one decision no policy, budget, or
    /// error code may override.
    ///
    /// The four reads qualify: each is a view of a store the call does not touch, so a repeat
    /// returns a fresh answer to the same question and nothing else. The two that do not:
    ///
    /// - `Converse` runs a turn. It may append messages, invoke tools, and stream partial
    ///   output before it fails, and its `decisions` stream is one-shot and unreplayable
    ///   (ADR-0024 decision 2). A repeat is a second turn, not the same turn again.
    /// - `AckReminder` is a write. The brain's own `ack` is idempotent, so a repeat does no
    ///   damage there, but the *answer* is not repeatable: an ack whose reply was lost has
    ///   already cleared the reminder, so the retry returns `false`, which reads at the caller
    ///   as "there was nothing to ack" about a reminder this very call dismissed. Surfacing
    ///   the transient failure keeps that ambiguity out of the answer (ADR-0025); the
    ///   overlay's next open re-lists whatever is still due.
    ///
    /// A method is repeatable when a repeat cannot duplicate an effect *and* cannot change the
    /// answer. `AckReminder` is the case that shows those are two different tests, and
    /// `RenameSession` is a plainer write: it relabels a chat, so a repeat over a lost reply
    /// could re-apply a stale label the user has since changed. One attempt, no retry.
    ///
    /// `DeleteSession` is the most conservative of all: a **destructive** write. In isolation it is
    /// idempotent (a second delete of an absent chat removes nothing and returns a bare ack), but a
    /// repeat can still duplicate an effect where it matters most: deleting the currently-open chat
    /// while its turn still streams is a concurrent `append` that can re-materialize the id between
    /// a lost reply and a retry, so a silent retry could destroy a transcript the user never
    /// confirmed removing. A destroy is the last call to re-issue automatically, so one attempt.
    #[must_use]
    pub const fn repeatable(self) -> bool {
        match self {
            Self::Health | Self::ListSessions | Self::SessionMessages | Self::ListDueReminders => {
                true
            }
            Self::Converse | Self::AckReminder | Self::RenameSession | Self::DeleteSession => false,
        }
    }
}

/// The retry schedule each seam method runs under, resolved through the repeatability gate.
///
/// One schedule for the reads a user waits on, plus a ceiling for the `Health` probe, because
/// those two have different consumers: a read that arrives late is still the right answer,
/// while a probe that arrives late has already let the indicator show the wrong dot.
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
    ///
    /// The `None` is the load-bearing half. A caller that gets one must make exactly one
    /// attempt and surface whatever comes back, however transient it looks: the gate refuses
    /// on what the call *does*, and no error code can argue with that.
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
