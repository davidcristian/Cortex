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

use crate::retry::gap::TurnGaps;
use crate::retry::policy::RetryPolicy;

/// The ceiling a `Health` probe spends by default, backoff **and** attempts together: with the
/// shipped deadline the probe keeps two of the read schedule's three attempts (250 + 200 + 250
/// fits, adding a third does not), so the indicator's verdict arrives inside 700 ms.
pub const DEFAULT_PROBE_BUDGET: Duration = Duration::from_secs(1);

/// How long a `Health` probe may wait for one answer. Brain-side `Health` is documented
/// synchronous and lock free precisely so a probe cannot queue behind the model swap it reports
/// on, and on loopback it answers in single-digit milliseconds, so this is two orders of
/// magnitude of headroom: past it, the honest reading is a brain the indicator should stop
/// vouching for rather than one worth waiting on.
pub const DEFAULT_PROBE_DEADLINE: Duration = Duration::from_millis(250);

/// How long every other unary call may wait for one answer. The reads and the catalog writes
/// are store operations over loopback, so this is far beyond a healthy one, and short enough
/// that a switcher opened against a wedged brain admits failure while the user is still
/// watching rather than spinning forever.
pub const DEFAULT_CALL_DEADLINE: Duration = Duration::from_secs(5);

/// How much longer the deadline the body **announces** to the brain is than the one it
/// **enforces**, in milliseconds ([`RetryPlan::announced_deadline_for`], ADR-0024 courtesy-header
/// addendum). A count of milliseconds rather than a [`Duration`] because this is the one duration
/// here that a module contract quotes as a number, and `scripts/crosscheck.py` ties the two by
/// reading this declaration, which it can do for an integer and cannot for a constructor call.
///
/// **Why there is a margin at all.** The announcement is `grpc-timeout`, and on this client it
/// cannot be made without also arming a local timer: `Request::set_timeout` writes the header and
/// nothing else, but the channel's own `GrpcTimeout` layer parses that header back off the
/// outgoing request and starts a clock from it. Announcing and arming are therefore one act. An
/// expiry tonic enforces arrives as a `Status::cancelled` carrying its `transport::Error`, which
/// the adapter classifies [`crate::transport::TransportError::Connection`], and that is in the
/// **retryable** set, so a tonic timer that won the race would turn one abandoned call into three:
/// the load amplifier a timeout is classified terminal to avoid. The margin makes the core's own
/// bound win deterministically instead, leaving tonic's timer armed but never first.
///
/// **Why a quarter second.** It pays for three things, in ascending order of size. A loopback
/// round trip plus the brain's own header parse costs tens of microseconds. The header's encoding
/// truncates to whole units of whichever unit it picks, which costs at most a millisecond and
/// costs exactly nothing for every value the shipped plan produces. And the two clocks are
/// ordered by their deadlines only while the runtime is scheduling: were the body's runtime to
/// stall past both, one poll would find both due and tonic's would answer first, since a
/// `bounded` call polls the call before the clock. So the margin is sized by the longest stall
/// the ordering must survive, and a quarter second is far beyond any this runtime should have.
/// It is bounded above by its own purpose: the brain works at most this long past the moment the
/// body stopped waiting, which is the waste the header exists to cut.
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
    ///
    /// The five reads qualify: each is a view of a store the call does not touch, so a repeat
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
    /// `SetSessionPinned` is the same write convention as `RenameSession`, and the one where the
    /// "idempotent by value" temptation is strongest: setting the same pinned state twice truly is
    /// a no-op, so a repeat cannot duplicate an effect. It is still not repeatable, because the
    /// *catalog-write convention* is uniform: a lost reply must not silently re-assert a pinned
    /// value the user's next toggle already reversed (the retry loop cannot see that later toggle).
    /// The reads are repeatable; every management write is one attempt, and pinning follows rename.
    ///
    /// `DeleteSession` is the most conservative of all: a **destructive** write. In isolation it is
    /// idempotent (a second delete of an absent chat removes nothing and returns a bare ack), but a
    /// repeat can still duplicate an effect where it matters most: deleting the currently-open chat
    /// while its turn still streams is a concurrent `append` that can re-materialize the id between
    /// a lost reply and a retry, so a silent retry could destroy a transcript the user never
    /// confirmed removing. A destroy is the last call to re-issue automatically, so one attempt.
    ///
    /// `GetPreferences` is a plain read of the settings record and repeatable with the others.
    /// `SetPreference` follows the same catalog-write convention as `RenameSession`: last write
    /// wins in the store, so a repeat cannot duplicate an effect, but a lost reply must not
    /// silently re-assert a value the user's next change already reversed. One attempt.
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
///
/// One schedule for the reads a user waits on, plus a ceiling for the `Health` probe, because
/// those two have different consumers: a read that arrives late is still the right answer,
/// while a probe that arrives late has already let the indicator show the wrong dot. The
/// deadlines split for the same reason and are asked separately ([`RetryPlan::deadline_for`]),
/// because they answer a different question: the schedule bounds the waiting *between*
/// attempts, the deadline bounds an attempt, and only the second one can say anything about a
/// brain that accepts the connection and then goes quiet.
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
    /// The two silences a `Converse` stream runs under ([`RetryPlan::gaps_for`], which lives in
    /// [`crate::retry::gap`] with everything else that knows what a gap means).
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
            SeamMethod::Health => self.reads.within(self.probe_budget, self.probe_deadline),
            _ => self.reads,
        })
    }

    /// How long one attempt at `method` may wait for an answer, or **`None` when it is not the
    /// clock's business**.
    ///
    /// The `None` belongs to `Converse` alone, and it is a decision rather than a gap: a turn
    /// is long by design (a model thinks, tools run, tokens stream), so ending one on a clock
    /// would be a different feature with a different consumer. That feature now exists, on the
    /// turn's own stream where it belongs, and it bounds the silence rather than the turn
    /// ([`RetryPlan::gaps_for`]). Everything else gets a duration, the writes included. Nothing
    /// here consults [`SeamMethod::repeatable`], and deliberately: bounding a call is not
    /// repeating it, so a write the plan refuses to retry still gets an answer or a
    /// [`crate::transport::TransportError::Timeout`] rather than an open-ended wait.
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
    ///
    /// The courtesy half of [`RetryPlan::deadline_for`]: the body enforces that one itself, and
    /// this is what it puts on the wire so the brain can stop working on a call nobody is waiting
    /// for. It is the enforced deadline plus [`ANNOUNCED_DEADLINE_GRACE_MS`], never equal to it,
    /// because the transport arms a clock of its own from the announcement and the body's own
    /// bound has to win that race by construction rather than by luck. `Converse` announces
    /// nothing, having no enforced deadline to announce; nothing else is exempt.
    ///
    /// The addition saturates, which changes the answer only for a deadline within the margin of
    /// [`Duration::MAX`]. Such a plan is unreachable from the millisecond knobs the shell parses
    /// and would announce a deadline no wire can spell in any case, which the adapter refuses
    /// separately.
    #[must_use]
    pub fn announced_deadline_for(&self, method: SeamMethod) -> Option<Duration> {
        let grace = Duration::from_millis(ANNOUNCED_DEADLINE_GRACE_MS);
        self.deadline_for(method)
            .map(|deadline| deadline.saturating_add(grace))
    }
}
