//! Contract tests for the turn stream's idle-gap bound (ADR-0024 idle-gap addendum).
//!
//! What is asserted here is a *policy over a clock*, so no wall clock runs: `GapSleeper` records
//! every gap it is handed and scripts which side of each race wins, exactly as `retry.rs`'s
//! `FakeSleeper` does for the per-attempt deadline. A timing test that waited on a real duration
//! would assert on the box it ran on rather than on the decision, and an exact elapsed reading
//! taken on an idle machine proves nothing about a loaded one.
//!
//! Two properties carry the whole design and both are asserted rather than described: a stream
//! that keeps producing is **never** cut off however long it runs, and a stream that stops is
//! ended with the gap that expired. The third is the ordering: the first event is measured against
//! one gap and every later one against the other.
//!
//! Every stream here is boxed to one type on purpose. `within_gaps` is generic, so each stream
//! type it is handed is a separate copy with its own coverage regions (ADR-0002), and pinning the
//! shape keeps the suite's copies to the two that mean something: this file's, and the one
//! `RetryingTransport::converse` composes.

use std::future::Future;
use std::pin::Pin;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use body_core::{
    BrainTransport, ConfirmDecision, DEFAULT_TURN_FIRST_GAP_MS, DEFAULT_TURN_IDLE_GAP_MS,
    DueReminder, RetryPlan, RetryingTransport, SeamHealth, SeamMethod, SessionMessage,
    SessionSummary, Sleeper, TransportError, TurnEvent, TurnGaps, within_gaps,
};
use futures_core::Stream;
use tokio_stream::StreamExt;

/// The one stream shape this file hands the decorator, so the generic wrapper is compiled once
/// here however many scenarios run through it.
type TurnStream = Pin<Box<dyn Stream<Item = TurnItem> + Send>>;

/// One item off such a stream. Named because every helper below carries it.
type TurnItem = Result<TurnEvent, TransportError>;

/// A [`Sleeper`] that records every gap it is asked to bound and expires the `expire_at`-th of
/// them (0-based), granting the rest.
///
/// Granting runs the poll, so an item that is there arrives; expiring drops the poll unpolled,
/// which is what `tokio::time::timeout` does to the loser and therefore what an abandoned wait
/// looks like from inside the decorator. `usize::MAX` is the sleeper that never expires.
#[derive(Clone)]
struct GapSleeper {
    gaps: Arc<Mutex<Vec<Duration>>>,
    expire_at: usize,
    seen: Arc<AtomicUsize>,
}

impl GapSleeper {
    /// A sleeper that grants every wait: the stream is bounded and the bound never wins.
    fn granting() -> Self {
        Self {
            gaps: Arc::new(Mutex::new(Vec::new())),
            expire_at: usize::MAX,
            seen: Arc::new(AtomicUsize::new(0)),
        }
    }

    /// A sleeper whose `index`-th wait (0-based) expires, so a scripted stall lands exactly where
    /// the scenario wants it rather than wherever the schedule happens to reach.
    fn expiring_at(index: usize) -> Self {
        Self {
            expire_at: index,
            ..Self::granting()
        }
    }

    /// Every gap this sleeper was asked to bound, in order.
    fn gaps(&self) -> Vec<Duration> {
        self.gaps
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

impl Sleeper for GapSleeper {
    fn sleep(&self, _duration: Duration) -> impl Future<Output = ()> + Send {
        // The gap bound never backs off: it waits on the stream, never between attempts. A wait
        // recorded here would mean the decorator took the retry path with a turn.
        std::future::ready(())
    }

    fn bounded<F>(
        &self,
        deadline: Duration,
        call: F,
    ) -> impl Future<Output = Option<F::Output>> + Send
    where
        F: Future + Send,
        F::Output: Send,
    {
        self.gaps
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(deadline);
        let expires = self.seen.fetch_add(1, Ordering::SeqCst) == self.expire_at;
        async move {
            if expires {
                drop(call);
                return None;
            }
            Some(call.await)
        }
    }
}

/// The gaps every scenario here runs under: two values far apart, so which one bounded a given
/// wait is legible in the recording rather than inferred.
const GAPS: TurnGaps = TurnGaps {
    first: Duration::from_secs(30),
    idle: Duration::from_secs(90),
};

/// One streamed delta, in the `Result` shape a turn's items have. The wrap is the shape rather
/// than an artefact, so the lint about a function that always succeeds is answered here instead
/// of obeyed: an item is a `Result` and a helper that returned a bare event would be wrapped by
/// every one of its callers.
#[allow(clippy::unnecessary_wraps)]
fn delta(text: &str) -> TurnItem {
    Ok(TurnEvent::Delta(String::from(text)))
}

/// A turn that streams `events` and then goes silent forever: the shape of a brain that stops
/// serving without closing the stream, which is the failure this bound exists for.
fn stalling(events: Vec<TurnItem>) -> TurnStream {
    Box::pin(tokio_stream::iter(events).chain(tokio_stream::pending()))
}

/// A turn that streams `events` and ends the way a real one does.
fn finished(events: Vec<TurnItem>) -> TurnStream {
    Box::pin(tokio_stream::iter(events))
}

async fn drain(gaps: Option<TurnGaps>, sleeper: &GapSleeper, stream: TurnStream) -> Vec<TurnItem> {
    let bounded = within_gaps(gaps, sleeper, stream);
    tokio::pin!(bounded);
    let mut items = Vec::new();
    while let Some(item) = bounded.next().await {
        items.push(item);
    }
    items
}

#[tokio::test]
async fn a_turn_that_keeps_talking_is_never_cut_off() {
    // The property the whole design rests on: the bound is on the silence, not on the turn, so
    // however many events arrive the stream passes through verbatim and nothing is added.
    // `TransportError` is not `Clone`, so the expected turn is built twice from one factory
    // rather than compared against a copy of the input.
    let turn = || {
        vec![
            delta("one"),
            Ok(TurnEvent::Status {
                state: String::from("thinking"),
                detail: String::from("hmm"),
            }),
            delta("two"),
            Ok(TurnEvent::Complete {
                turn_id: String::from("t-1"),
            }),
        ]
    };
    let sleeper = GapSleeper::granting();
    let items = drain(Some(GAPS), &sleeper, finished(turn())).await;
    assert_eq!(items, turn());
}

#[tokio::test]
async fn the_first_event_is_measured_against_one_gap_and_every_later_one_against_the_other() {
    // The ordering, read off the clock itself. Four waits for three events and the end of the
    // stream: the first spends the first-event gap, and every one after it the idle gap.
    let sleeper = GapSleeper::granting();
    let items = drain(
        Some(GAPS),
        &sleeper,
        finished(vec![delta("a"), delta("b"), delta("c")]),
    )
    .await;
    assert_eq!(items.len(), 3);
    assert_eq!(
        sleeper.gaps(),
        vec![GAPS.first, GAPS.idle, GAPS.idle, GAPS.idle]
    );
}

#[tokio::test]
async fn a_turn_that_never_starts_ends_on_the_first_event_gap() {
    // The failure the entry that opened this was written about: the brain accepted the turn and
    // sent nothing. One item comes back, and it is the timeout carrying the gap that expired, so
    // the overlay has something to settle a streaming reply with instead of a thinking indicator
    // that never resolves.
    let sleeper = GapSleeper::expiring_at(0);
    let items = drain(Some(GAPS), &sleeper, stalling(Vec::new())).await;
    assert_eq!(
        items,
        vec![Err(TransportError::Timeout { after: GAPS.first })]
    );
    assert_eq!(sleeper.gaps(), vec![GAPS.first]);
}

#[tokio::test]
async fn a_turn_that_stops_mid_reply_keeps_what_arrived_and_ends_on_the_idle_gap() {
    // The other half: everything that did arrive is delivered, then the timeout, and the gap it
    // carries is the mid-stream one rather than the first-event one. The partial reply survives,
    // which is what lets the overlay settle the bubble on the words it already has.
    let sleeper = GapSleeper::expiring_at(2);
    let items = drain(
        Some(GAPS),
        &sleeper,
        stalling(vec![delta("half "), delta("a")]),
    )
    .await;
    assert_eq!(
        items,
        vec![
            delta("half "),
            delta("a"),
            Err(TransportError::Timeout { after: GAPS.idle }),
        ]
    );
    assert_eq!(sleeper.gaps(), vec![GAPS.first, GAPS.idle, GAPS.idle]);
}

#[tokio::test]
async fn an_expired_gap_ends_the_stream_rather_than_waiting_again() {
    // A timeout is terminal here for the same reason it is terminal on a unary call: it is this
    // side's decision to stop waiting, so waiting again is the one thing it cannot justify. The
    // recording is the proof, since a decorator that polled once more would have asked for a
    // fourth gap after the third expired.
    let sleeper = GapSleeper::expiring_at(1);
    let items = drain(Some(GAPS), &sleeper, stalling(vec![delta("x")])).await;
    assert_eq!(items.len(), 2);
    assert_eq!(sleeper.gaps().len(), 2);
}

#[tokio::test]
async fn a_stream_with_no_gaps_at_all_is_bounded_by_a_clock_that_never_wins() {
    // The exemption is spelled as a duration rather than branched on (the `within_deadline`
    // precedent), so a caller with no policy still runs one code path and the timer is simply
    // never first. `Duration::MAX` is what reaches the clock, which is what proves it.
    let sleeper = GapSleeper::granting();
    let items = drain(None, &sleeper, finished(vec![delta("only")])).await;
    assert_eq!(items, vec![delta("only")]);
    assert_eq!(sleeper.gaps(), vec![Duration::MAX, Duration::MAX]);
    assert_eq!(
        TurnGaps::UNBOUNDED,
        TurnGaps {
            first: Duration::MAX,
            idle: Duration::MAX,
        }
    );
}

#[test]
fn the_shipped_gaps_are_the_two_constants_and_the_idle_one_is_the_longer() {
    // The ordering is the surprising half and the one a retune could invert by accident: the
    // long silences on this deployment (a delegated subtask waiting for admission and then
    // running) can only happen once a turn is under way, so the mid-stream gap is the loose one
    // and the first-event gap the tight one. The derivation of both is in the ADR addendum.
    let gaps = TurnGaps::default();
    assert_eq!(gaps.first, Duration::from_millis(DEFAULT_TURN_FIRST_GAP_MS));
    assert_eq!(gaps.idle, Duration::from_millis(DEFAULT_TURN_IDLE_GAP_MS));
    assert!(gaps.idle > gaps.first);
    assert_eq!(RetryPlan::default().turn_gaps, gaps);
}

/// A transport whose turn stalls after one event, so the decorator can be driven through the port
/// rather than through `within_gaps` directly. Every unary method is unreachable here and says so.
struct StallingTransport;

impl BrainTransport for StallingTransport {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    fn converse(
        &self,
        _session_id: &str,
        _text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = TurnItem> + Send {
        drop(decisions);
        stalling(vec![delta("started")])
    }

    async fn list_sessions(&self, _limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn session_messages(
        &self,
        _session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn ack_reminder(&self, _reminder_id: &str) -> Result<bool, TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn rename_session(&self, _session_id: &str, _title: &str) -> Result<(), TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn delete_session(&self, _session_id: &str) -> Result<(), TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn set_session_pinned(
        &self,
        _session_id: &str,
        _pinned: bool,
    ) -> Result<(), TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn set_preference(&self, _key: &str, _value: &str) -> Result<(), TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }
}

#[tokio::test]
async fn the_decorator_hands_the_turn_the_plan_s_own_gaps() {
    // End to end through the port: the plan is the single door for this clock exactly as it is
    // for the retry schedule and the per-attempt deadline, so what bounds the turn is what
    // `gaps_for` answered and nothing composed at the call site.
    let sleeper = GapSleeper::expiring_at(1);
    let plan = RetryPlan {
        turn_gaps: GAPS,
        ..RetryPlan::default()
    };
    let transport = RetryingTransport::new(StallingTransport, sleeper.clone(), plan);
    let items: Vec<_> = transport
        .converse("s1", "hi", tokio_stream::empty())
        .collect()
        .await;
    assert_eq!(
        items,
        vec![
            delta("started"),
            Err(TransportError::Timeout { after: GAPS.idle })
        ]
    );
    assert_eq!(sleeper.gaps(), vec![GAPS.first, GAPS.idle]);
    assert_eq!(plan.gaps_for(SeamMethod::Converse), Some(GAPS));
}
