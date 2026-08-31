//! [`within_gaps`]: a turn's stream, bounded by its silence (ADR-0024 idle-gap addendum).

use std::future::poll_fn;
use std::pin::pin;
use std::time::Duration;

use async_stream::stream;
use futures_core::Stream;

use crate::retry::effects::Sleeper;
use crate::retry::plan::{RetryPlan, SeamMethod};
use crate::transport::{TransportError, TurnEvent};

/// How long a turn may be silent before its first event, in milliseconds.
pub const DEFAULT_TURN_FIRST_GAP_MS: u64 = 600_000;

/// How long a turn may be silent between two of its events, in milliseconds.
pub const DEFAULT_TURN_IDLE_GAP_MS: u64 = 7_200_000;

/// The two silences one streamed turn runs under: the wait for its first event, and the wait
/// between the events after it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TurnGaps {
    /// The longest silence allowed before the turn's first event.
    pub first: Duration,
    /// The longest silence allowed between two events, reset by every one of them.
    pub idle: Duration,
}

impl TurnGaps {
    /// The gaps that never expire, which is how an unbounded stream is spelled here.
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
    /// The silences `method`'s stream runs under, or `None` when the method is not a stream.
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

/// Which silence a turn is spending, and what its stream does next. It holds pure state and
/// touches no clock and no stream: the decorator hands it what the clock saw, and it returns the
/// item to yield or nothing.
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
