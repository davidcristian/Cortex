//! [`within_gaps`]: a turn's stream, bounded by its **silence** (ADR-0024 idle-gap addendum).
//!
//! [`crate::retry::within_deadline`] bounds a call by how long the whole thing takes, which is the
//! wrong instrument for a turn: a model thinks, tools run, tokens stream, and a working turn is
//! long by design. So [`crate::retry::RetryPlan::deadline_for`] answers `None` for `Converse` and
//! always will. That decision is right about a working turn and says nothing about a stalled one,
//! and a brain that accepts the turn and then emits nothing leaves the overlay's reply streaming
//! for as long as the process lives: nothing on the body's side of the seam ends a turn that
//! neither completes, fails, nor closes.
//!
//! What bounds a stall without bounding a turn is the **gap between events**. Every delta, tool
//! activity, outcome, status and confirm resets it, so an answer may take an hour as long as it
//! keeps arriving, and only silence is spent. [`TurnGaps`] carries two of them, because the
//! silence before a turn's first event and the silence between two of its events are different
//! quantities on this deployment; the derivation of both is in the ADR addendum, and the short
//! version is that a delegated subtask, which can only happen after an event, is quiet for far
//! longer than any first token.
//!
//! **The clock is the [`Sleeper`] port, unchanged.** `bounded` already runs a future against a
//! duration and reports which won, and one poll of the stream is such a future, so the decorator
//! composes what the deadline path composes rather than asking the port for anything new.
//!
//! **Every branch that decides anything lives in [`GapClock`], which is not generic.** The stream
//! wrapper is compiled once per sleeper and stream type, and a branch inside it is a fresh pair of
//! coverage regions in every copy (ADR-0002); the two the wrapper keeps are the two any drained
//! stream takes both sides of. The clock beneath it holds the rest and is one type, tested
//! directly.

use std::future::poll_fn;
use std::pin::pin;
use std::time::Duration;

use async_stream::stream;
use futures_core::Stream;

use crate::retry::effects::Sleeper;
use crate::retry::plan::{RetryPlan, SeamMethod};
use crate::transport::{TransportError, TurnEvent};

/// How long a turn may be silent **before its first event**, in milliseconds.
///
/// Ten minutes, and it is the sum of the brain's own bounds on that stretch rather than a guess at
/// a first token. Before the first event the brain may drain the subagent pool
/// (`DEFAULT_SWAP_DRAIN_TIMEOUT_S`, 60 s), load a model
/// (`DEFAULT_SWAP_LOAD_TIMEOUT_S`, 300 s), and then wait on the first token under its own stall
/// ceiling (`CORTEX_INFERENCE_STALL_TIMEOUT_S`, 120 s): 480 s of waiting that the brain itself
/// ends with a reported failure. The rest is margin for the stretches no brain-side budget covers,
/// namely recall, prefill, and a first round the brain streams nothing visible for.
///
/// The measured worst case is far below it, which is the point of the margin rather than an
/// argument against it: the deep tier loads in 99.6 s and the worst time to first token measured
/// on this card is 17.5 s on a contended cortex, derived at 45.5 s for the deep tier
/// (ADR-0005 stall-ceiling addendum), so the shipped gap is about four times the slowest first
/// event anyone here has timed. A bound that fires on a legitimately slow turn would be worse than
/// the hang it replaces, so what this removes is "forever", not "slow".
pub const DEFAULT_TURN_FIRST_GAP_MS: u64 = 600_000;

/// How long a turn may be silent **between two of its events**, in milliseconds.
///
/// Two hours, and it is longer than the first gap rather than shorter, which is the surprise this
/// bound holds. The long silences on this deployment can only happen once a turn is under way, and
/// the longest of them is a delegated subtask: it waits up to `DEFAULT_ADMISSION_WAIT_S` (3600 s)
/// for the CPU budget to admit it and then runs up to `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` (2400 s),
/// and the seam sees nothing through either stretch unless the subagent happens to call a tool.
/// 6000 s of legitimate silence, plus a fifth of it as margin.
///
/// **It cannot be tightened by listening for the delegation that announces itself.** A delegating
/// turn does emit a status naming the batch, and the temptation is to widen the gap on that event
/// alone and hold every other turn to something tight. That progress rides a best-effort sink
/// which drops an event on a saturated buffer by design, so an announcement may never arrive, and
/// a turn-ending decision must not rest on having received one. The bound that would let this
/// number come down is a heartbeat the brain owes rather than a guess the body makes.
pub const DEFAULT_TURN_IDLE_GAP_MS: u64 = 7_200_000;

/// The two silences one streamed turn runs under: the wait for its first event, and the wait
/// between the events after it.
///
/// Two durations rather than one because they bound different things, exactly as the plan's probe
/// deadline and call deadline do. See the constants above for what each is sized by.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TurnGaps {
    /// The longest silence allowed before the turn's first event.
    pub first: Duration,
    /// The longest silence allowed between two events, reset by every one of them.
    pub idle: Duration,
}

impl TurnGaps {
    /// The gaps that never fire, which is what "no bound" means to a clock.
    ///
    /// [`Duration::MAX`] rather than an absent value, for the reason
    /// [`crate::retry::within_deadline`] spells its own exemption the same way: the timer is armed
    /// and simply never wins, so the exemption costs no branch in code that is compiled once per
    /// stream type. It is what a caller composing this around a stream the plan has no opinion
    /// about gets.
    pub const UNBOUNDED: Self = Self {
        first: Duration::MAX,
        idle: Duration::MAX,
    };
}

impl Default for TurnGaps {
    /// The shipped gaps: [`DEFAULT_TURN_FIRST_GAP_MS`] and [`DEFAULT_TURN_IDLE_GAP_MS`].
    fn default() -> Self {
        Self {
            first: Duration::from_millis(DEFAULT_TURN_FIRST_GAP_MS),
            idle: Duration::from_millis(DEFAULT_TURN_IDLE_GAP_MS),
        }
    }
}

impl RetryPlan {
    /// The silences `method`'s stream runs under, or **`None` when it is not a stream**.
    ///
    /// The complement of [`RetryPlan::deadline_for`], and deliberately its mirror image: that one
    /// answers `Some` for every method except `Converse`, this one for `Converse` alone. Together
    /// they say that **every call on the port is bounded, by a clock on the call or a clock on its
    /// silence, and never by both**, which `retry_plan.rs` asserts over every variant rather than
    /// leaving to this sentence.
    ///
    /// It lives here rather than beside `deadline_for` because this file owns what a gap means and
    /// `plan.rs` is at the line cap, the same split `effects.rs` and `deadline.rs` already took
    /// off `retry.rs`.
    #[must_use]
    pub fn gaps_for(&self, method: SeamMethod) -> Option<TurnGaps> {
        match method {
            SeamMethod::Converse => Some(self.turn_gaps),
            SeamMethod::Health
            | SeamMethod::ListSessions
            | SeamMethod::SessionMessages
            | SeamMethod::ListDueReminders
            | SeamMethod::AckReminder
            | SeamMethod::RenameSession
            | SeamMethod::DeleteSession
            | SeamMethod::SetSessionPinned
            | SeamMethod::GetPreferences
            | SeamMethod::SetPreference => None,
        }
    }
}

/// Which silence a turn is spending, and what its stream does next. Pure state, no clock, no
/// stream: the decorator hands it what the clock saw and it answers with the item to yield or
/// nothing at all.
///
/// Not generic, and that is its job. Every decision the gap bound makes is here, so the wrapper
/// around it carries two branches instead of five and a coverage region cannot go dark in one
/// instantiation while another covers it.
struct GapClock {
    gaps: TurnGaps,
    /// Whether an event has arrived, which is what separates the two gaps.
    seen: bool,
    /// Whether the stream is over, by its own end or by an expired gap.
    done: bool,
}

/// What one bounded poll of the inner stream saw: `None` when the gap won, `Some(None)` when the
/// stream ended, `Some(Some(item))` when an item arrived in time.
type Polled = Option<Option<Result<TurnEvent, TransportError>>>;

impl GapClock {
    /// A clock over `gaps`, or over [`TurnGaps::UNBOUNDED`] when the caller has none.
    fn new(gaps: Option<TurnGaps>) -> Self {
        Self {
            gaps: gaps.unwrap_or(TurnGaps::UNBOUNDED),
            seen: false,
            done: false,
        }
    }

    /// The silence the stream may spend next, or `None` once it is over.
    fn next_gap(&self) -> Option<Duration> {
        if self.done {
            return None;
        }
        Some(if self.seen {
            self.gaps.idle
        } else {
            self.gaps.first
        })
    }

    /// Folds what the clock saw into the item to yield, or `None` to stop.
    ///
    /// An expired gap yields [`TransportError::Timeout`] carrying the gap that expired and ends
    /// the stream, which is the same shape a per-attempt deadline reports and lands on the same
    /// classification: nothing answered, so the indicator reads `Down` and the reply settles
    /// carrying why. Ending silently would be the other candidate and is not available: the
    /// overlay leaves a reply streaming until a terminal event or an error reaches it, so a stream
    /// that merely stopped would leave the indicator exactly where the stall did.
    fn step(&mut self, polled: Polled, gap: Duration) -> Option<Result<TurnEvent, TransportError>> {
        match polled {
            Some(Some(item)) => {
                self.seen = true;
                Some(item)
            }
            Some(None) => {
                self.done = true;
                None
            }
            None => {
                self.done = true;
                Some(Err(TransportError::Timeout { after: gap }))
            }
        }
    }
}

/// `stream` bounded by `gaps`: the same items, until one silence runs past its gap.
///
/// Every item resets the clock, so a turn that keeps talking is never cut off, and the first item
/// is measured against [`TurnGaps::first`] while every later one is measured against
/// [`TurnGaps::idle`]. A `None` for `gaps` means no bound at all, spelled as
/// [`TurnGaps::UNBOUNDED`].
///
/// When a gap expires the abandoned poll is dropped and one final
/// `Err(`[`TransportError::Timeout`]`)` is yielded, carrying the gap that expired; the inner
/// stream is then dropped, which for the gRPC adapter resets the turn so a stall nobody is waiting
/// for stops costing the brain. Dropping the poll loses nothing on its own (it holds no state
/// between polls), so the stream ends because this decided to, not because the poll was abandoned.
pub fn within_gaps<S, St>(
    gaps: Option<TurnGaps>,
    sleeper: &S,
    stream: St,
) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send
where
    S: Sleeper,
    St: Stream<Item = Result<TurnEvent, TransportError>> + Send,
{
    stream! {
        let mut clock = GapClock::new(gaps);
        let mut inner = pin!(stream);
        while let Some(gap) = clock.next_gap() {
            let polled = sleeper
                .bounded(gap, poll_fn(|cx| inner.as_mut().poll_next(cx)))
                .await;
            if let Some(item) = clock.step(polled, gap) {
                yield item;
            }
        }
    }
}
