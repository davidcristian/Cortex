//! [`SeamMethod`] and [`RetryPlan`]: which seam call may be retried at all, and on what
//! schedule.
//!
//! Retry rests on one property, which is not an error code: repeating the call must be
//! observably the same as making it once. A transient status says the brain could not serve
//! the call; it never says the brain did not already run it. The decision is made in that order
//! here: [`SeamMethod::repeatable`] first, which is a fact about the call, then
//! [`crate::retry::is_transient`], which is a fact about the failure.
//!
//! Before this module the order held only by hand. `RetryingTransport` retried four methods
//! and forwarded two because two `impl` bodies were written that way, and adding a seventh
//! method by copying a retried one would have retried it with nothing to catch the mistake.
//! [`RetryPlan::policy_for`] is now the single place that decides: it answers `None` for a
//! method that may not be repeated, and the decorator makes exactly one attempt on a `None`.
//! Adding a variant to [`SeamMethod`] fails to compile until [`SeamMethod::repeatable`]
//! classifies it.
//!
//! The schedule half is per method because the connection indicator renders a `Health` probe's
//! answer (`crate::link`), so time spent retrying there is time the dot spends claiming a state
//! the seam has stopped proving. [`RetryPlan::probe_budget`] caps it, and the read knobs cannot
//! drag it along: turning `CORTEX_BRAIN_RETRY_ATTEMPTS` up gives a session read more attempts
//! without extending how long the indicator may show a stale state.

use std::time::Duration;

use crate::retry::gap::TurnGaps;
use crate::retry::policy::RetryPolicy;

/// The ceiling a `Health` probe spends by default, backoff and attempts together: with the
/// shipped deadline the probe keeps two of the read schedule's three attempts (250 + 200 + 250
/// fits, adding a third does not), so the indicator's verdict arrives inside 700 ms.
pub const DEFAULT_PROBE_BUDGET: Duration = Duration::from_secs(1);

/// How long a `Health` probe may wait for one answer. Brain-side `Health` is documented
/// synchronous and lock free precisely so a probe cannot queue behind the model swap it reports
/// on, and on loopback it answers in single-digit milliseconds, so this is two orders of
/// magnitude of headroom. Past it, the brain is not answering, and the indicator reports that
/// rather than waiting longer.
pub const DEFAULT_PROBE_DEADLINE: Duration = Duration::from_millis(250);

/// How long every other unary call may wait for one answer. The reads and the catalog writes
/// are store operations over loopback, so this is far beyond a healthy one, and short enough
/// that a switcher opened against a wedged brain reports the failure while the user is still
/// watching rather than spinning forever.
pub const DEFAULT_CALL_DEADLINE: Duration = Duration::from_secs(5);

/// How much longer the deadline the body announces to the brain is than the one it enforces, in
/// milliseconds ([`RetryPlan::announced_deadline_for`], ADR-0024 courtesy-header addendum). It is
/// a count of milliseconds rather than a [`Duration`] because this is the one duration here that
/// a module contract quotes as a number, and `scripts/crosscheck.py` ties the two by reading this
/// declaration, which it can do for an integer and cannot for a constructor call.
///
/// There is a margin because announcing and arming are one act on this client. The announcement
/// is `grpc-timeout`: `Request::set_timeout` writes the header and nothing else, but the
/// channel's own `GrpcTimeout` layer parses that header back off the outgoing request and starts
/// a clock from it. An expiry tonic enforces arrives as a `Status::cancelled` carrying its
/// `transport::Error`, which the adapter classifies as
/// [`crate::transport::TransportError::Connection`], and that is in the retryable set, so a tonic
/// timer that expired first would turn one abandoned call into three, which is the load
/// amplification a timeout is classified terminal to avoid. The margin makes the core's own bound
/// expire first, leaving tonic's timer armed but never first.
///
/// A quarter second pays for three things, in ascending order of size. A loopback round trip plus
/// the brain's own header parse costs about a millisecond, read at the handler entry of a real
/// `grpc.aio` brain told these very announcements. The header's encoding truncates to whole units
/// of whichever unit tonic picks, and tonic picks the most precise unit that fits in eight
/// digits, so that costs under a microsecond for any announcement below 100 s and exactly nothing
/// for the two this plan ships, which reach the brain as `500000u` and `5250000u` and are
/// enforced there as 500 ms and 5250 ms. Only an announcement past about 27.8 hours, where the
/// ladder's next unit is whole seconds, loses more than this margin covers, and the adapter
/// announces nothing at all past that rung rather than spend a margin that would not cover it
/// (ADR-0024 unit-ladder addendum). Third, the two clocks are ordered by their deadlines only
/// while the runtime is scheduling: were the body's runtime to stall past both, one poll would
/// find both due and tonic's would answer first, since a `bounded` call polls the call before the
/// clock. The margin is therefore sized by the longest stall the ordering must survive, and a
/// quarter second is far beyond any this runtime should have. It is bounded above by its own
/// purpose, since the brain works at most this long past the moment the body stopped waiting,
/// which is the waste the header exists to cut.
pub const ANNOUNCED_DEADLINE_GRACE_MS: u64 = 250;

/// Every call on the [`crate::transport::BrainTransport`] port, named so a retry decision can
/// be made about it. Exhaustive by construction: a new port method has to appear here and be
/// classified before it can be retried (see the module docs).
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
    /// Whether repeating this call is observably the same as making it once. This is the safety
    /// property every retry rests on, and no policy, budget, or error code overrides it.
    ///
    /// The five reads qualify: each is a view of a store the call does not change, so a repeat
    /// returns a fresh answer to the same question and nothing else. These two do not:
    ///
    /// - `Converse` runs a turn. It may append messages, invoke tools, and stream partial
    ///   output before it fails, and its `decisions` stream is one-shot and unreplayable
    ///   (ADR-0024 decision 2). A repeat is a second turn rather than the same turn again.
    /// - `AckReminder` is a write. The brain's own `ack` is idempotent, so a repeat does no
    ///   damage there, but the answer is not repeatable: an ack whose reply was lost has
    ///   already cleared the reminder, so the retry returns `false`, which reads at the caller
    ///   as "there was nothing to ack" about a reminder this very call dismissed. Surfacing
    ///   the transient failure keeps that ambiguity out of the answer (ADR-0025), and the
    ///   overlay's next open re-lists whatever is still due.
    ///
    /// A method is repeatable when a repeat cannot duplicate an effect and cannot change the
    /// answer. `AckReminder` shows that those are two different tests. `RenameSession` is a
    /// plainer write: it relabels a chat, so a repeat over a lost reply could re-apply a stale
    /// label the user has since changed. One attempt, no retry.
    ///
    /// `SetSessionPinned` follows the same catalog-write convention. Setting the same pinned
    /// state twice is a no-op, so a repeat cannot duplicate an effect, but it is still not
    /// repeatable: a lost reply must not re-assert a pinned value the user's next toggle already
    /// reversed, and the retry loop cannot see that later toggle. The reads are repeatable and
    /// every management write gets one attempt.
    ///
    /// `DeleteSession` is a destructive write. In isolation it is idempotent, since a second
    /// delete of an absent chat removes nothing and returns a bare ack, but a repeat can still
    /// duplicate an effect where it matters most: deleting the currently-open chat while its
    /// turn still streams is a concurrent `append` that can re-materialize the id between a lost
    /// reply and a retry, so a silent retry could destroy a transcript the user never confirmed
    /// removing. One attempt.
    ///
    /// `GetPreferences` is a plain read of the settings record and repeatable with the others.
    /// `SetPreference` follows the same catalog-write convention as `RenameSession`: last write
    /// wins in the store, so a repeat cannot duplicate an effect, but a lost reply must not
    /// re-assert a value the user's next change already reversed. One attempt.
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
/// because they answer a different question: the schedule bounds the waiting between attempts,
/// the deadline bounds one attempt, and only the deadline says anything about a brain that
/// accepts the connection and then goes quiet.
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
    /// The schedule `method` retries on, or `None` when it may not be retried at all.
    ///
    /// A caller that gets `None` makes exactly one attempt and surfaces whatever comes back,
    /// however transient it looks. The refusal rests on what the call does, which no error code
    /// changes.
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

    /// How long one attempt at `method` may wait for an answer, or `None` when no clock bounds
    /// it.
    ///
    /// The `None` belongs to `Converse` alone, and it is a deliberate value rather than an
    /// omission: a turn is long by design, since a model thinks, tools run and tokens stream, so
    /// a clock on the whole turn would end working turns. A turn is bounded by its silence
    /// instead ([`RetryPlan::gaps_for`]). Everything else gets a duration, the writes included.
    /// Nothing here consults [`SeamMethod::repeatable`], because bounding a call does not repeat
    /// it, so a write the plan refuses to retry still ends in an answer or a
    /// [`crate::transport::TransportError::Timeout`] rather than an open-ended wait.
    #[must_use]
    pub fn deadline_for(&self, method: SeamMethod) -> Option<Duration> {
        match method {
            SeamMethod::Health => Some(self.probe_deadline),
            // A turn is bounded by its silence instead, in `gaps_for`.
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

    /// How long one attempt at `method` tells the brain it will be waited on, or `None` when it
    /// announces nothing (ADR-0024 courtesy-header addendum).
    ///
    /// The body enforces [`RetryPlan::deadline_for`] itself, and this is what it puts on the wire
    /// so the brain can stop working on a call nobody is waiting for. It is the enforced deadline
    /// plus [`ANNOUNCED_DEADLINE_GRACE_MS`], never equal to it, because the transport arms a
    /// clock of its own from the announcement and the body's own bound has to expire first by
    /// construction. `Converse` announces nothing, having no enforced deadline to announce;
    /// nothing else is exempt.
    ///
    /// The addition saturates, which changes the answer only for a deadline within the margin of
    /// [`Duration::MAX`]. Such a plan is unreachable from the millisecond knobs the shell parses
    /// and would announce a deadline no wire can spell in any case, which the adapter rejects
    /// separately.
    #[must_use]
    pub fn announced_deadline_for(&self, method: SeamMethod) -> Option<Duration> {
        let grace = Duration::from_millis(ANNOUNCED_DEADLINE_GRACE_MS);
        self.deadline_for(method)
            .map(|deadline| deadline.saturating_add(grace))
    }
}
