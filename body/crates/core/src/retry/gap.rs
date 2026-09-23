//! [`within_gaps`]: a turn's stream, bounded by its silence.
//!
//! A turn has no deadline, because a working turn is long by design. What is bounded is its
//! silence: every event resets the clock, and the brain's heartbeat bounds a dead brain sooner.

use std::future::poll_fn;
use std::pin::pin;
use std::time::Duration;

use async_stream::stream;
use futures_core::Stream;

use crate::retry::effects::Sleeper;
use crate::retry::plan::{RetryPlan, RpcMethod};
use crate::transport::{TransportError, TurnEvent};

/// How long a turn may be silent before its first event, in milliseconds.
///
/// Ten minutes. The brain's own bounds on that stretch add up to 480 s (60 s pool drain, 300 s
/// model load, 120 s first-token stall); the rest is margin for recall and prefill.
pub const DEFAULT_TURN_FIRST_GAP_MS: u64 = 600_000;

/// How long a turn may be silent between two of its events, in milliseconds.
///
/// A delegated subtask waits up to `DEFAULT_ADMISSION_WAIT_S` (7200 s) for CPU budget, then holds
/// it for two runs of `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` (2400 s): 12000 s, plus a fifth as margin.
pub const DEFAULT_TURN_IDLE_GAP_MS: u64 = 14_400_000;

/// How often the brain sends a heartbeat while a turn runs, in milliseconds. The brain's
/// `converse_stream.py` declares the same constant.
pub const HEARTBEAT_PERIOD_MS: u64 = 30_000;

/// How long a turn's stream may go without any item at all, a heartbeat included, in milliseconds.
///
/// Four heartbeat periods, so a live brain whose event loop runs late by up to three still passes.
pub const DEFAULT_TURN_HEARTBEAT_GAP_MS: u64 = 120_000;

/// The silences one streamed turn runs under: the turn's own before and between its events, and
/// the stream's between any two items, heartbeats included.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TurnGaps {
    /// The longest silence allowed before the turn's first event.
    pub first: Duration,
    /// The longest silence allowed between two events, reset by every one of them.
    pub idle: Duration,
    /// The longest the stream may go without any item, reset by a heartbeat too.
    pub heartbeat: Duration,
    /// The brain's heartbeat period: the turn silence each heartbeat is counted as.
    pub period: Duration,
}

impl TurnGaps {
    /// The gaps that never expire, which is how an unbounded stream is written here.
    pub const UNBOUNDED: Self = Self {
        first: Duration::MAX,
        idle: Duration::MAX,
        heartbeat: Duration::MAX,
        period: Duration::ZERO,
    };
}

impl Default for TurnGaps {
    /// The shipped gaps, from the four constants above.
    fn default() -> Self {
        Self {
            first: Duration::from_millis(DEFAULT_TURN_FIRST_GAP_MS),
            idle: Duration::from_millis(DEFAULT_TURN_IDLE_GAP_MS),
            heartbeat: Duration::from_millis(DEFAULT_TURN_HEARTBEAT_GAP_MS),
            period: Duration::from_millis(HEARTBEAT_PERIOD_MS),
        }
    }
}

impl RetryPlan {
    /// The silences `method`'s stream runs under, or `None` when the method is not a stream.
    #[must_use]
    pub fn gaps_for(&self, method: RpcMethod) -> Option<TurnGaps> {
        match method {
            RpcMethod::Converse => Some(self.turn_gaps),
            RpcMethod::Health
            | RpcMethod::ListSessions
            | RpcMethod::SessionMessages
            | RpcMethod::ListDueReminders
            | RpcMethod::AckReminder
            | RpcMethod::RenameSession
            | RpcMethod::DeleteSession
            | RpcMethod::SetSessionHoisted
            | RpcMethod::GetPreferences
            | RpcMethod::SetPreference => None,
        }
    }
}

/// Which silence a turn is using, and what its stream does next.
///
/// Not generic, deliberately: a branch in generic code becomes a separate coverage region in
/// every instantiation, so every decision the gap bound makes is kept here.
struct GapClock {
    gaps: TurnGaps,
    /// Whether an event has arrived, which is what separates the two gaps.
    seen: bool,
    /// Whether the stream is over, by its own end or by an expired gap.
    done: bool,
    /// The turn's silence as heartbeats count it: one period per heartbeat since its last event.
    quiet: Duration,
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
            quiet: Duration::ZERO,
        }
    }

    /// The silence the turn itself may spend: `first` before its first event, `idle` after.
    fn allowance(&self) -> Duration {
        if self.seen {
            self.gaps.idle
        } else {
            self.gaps.first
        }
    }

    /// The silence the stream may spend next, or `None` once it is over.
    fn next_gap(&self) -> Option<Duration> {
        if self.done {
            return None;
        }
        let left = self.allowance().saturating_sub(self.quiet);
        Some(self.gaps.heartbeat.min(left))
    }

    /// Folds what the clock saw into the item to yield, or `None` to stop.
    fn step(&mut self, polled: Polled, gap: Duration) -> Option<Result<TurnEvent, TransportError>> {
        match polled {
            Some(Some(Ok(beat @ TurnEvent::Heartbeat { .. }))) => Some(self.beat(beat)),
            Some(Some(item)) => {
                self.seen = true;
                self.quiet = Duration::ZERO;
                Some(item)
            }
            Some(None) => {
                self.done = true;
                None
            }
            None => {
                self.done = true;
                Some(Err(TransportError::Timeout {
                    after: self.broken(gap),
                }))
            }
        }
    }

    /// Counts one heartbeat as a period of the turn's silence and passes it on, ending the
    /// stream instead once that silence reaches the turn's allowance.
    fn beat(&mut self, beat: TurnEvent) -> Result<TurnEvent, TransportError> {
        self.quiet = self.quiet.saturating_add(self.gaps.period);
        if self.quiet < self.allowance() {
            return Ok(beat);
        }
        self.done = true;
        Err(TransportError::Timeout {
            after: self.allowance(),
        })
    }

    /// The gap a poll bounded by `gap` broke when it expired: the heartbeat gap when that was the
    /// bound, otherwise the turn's own allowance.
    fn broken(&self, gap: Duration) -> Duration {
        if gap == self.gaps.heartbeat {
            gap
        } else {
            self.allowance()
        }
    }
}

/// `stream` bounded by `gaps`: the same items, until one silence runs past its gap.
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
