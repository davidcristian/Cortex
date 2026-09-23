use std::future::Future;
use std::pin::Pin;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use body_core::{
    BrainTransport, ConfirmDecision, DEFAULT_TURN_FIRST_GAP_MS, DEFAULT_TURN_HEARTBEAT_GAP_MS,
    DEFAULT_TURN_IDLE_GAP_MS, DueReminder, HEARTBEAT_PERIOD_MS, RetryPlan, RetryingTransport,
    RpcHealth, RpcMethod, SessionMessage, SessionSummary, Sleeper, TransportError, TurnEvent,
    TurnGaps, within_gaps,
};
use futures_core::Stream;
use tokio_stream::StreamExt;

/// The one stream shape this file hands the decorator, so the generic wrapper is compiled once here
/// however many scenarios run through it.
type TurnStream = Pin<Box<dyn Stream<Item = TurnItem> + Send>>;

/// One item off such a stream.
type TurnItem = Result<TurnEvent, TransportError>;

/// A [`Sleeper`] that records every gap it is asked to bound and expires the `expire_at`-th of them
/// (0-based), granting the rest.
#[derive(Clone)]
struct GapSleeper {
    gaps: Arc<Mutex<Vec<Duration>>>,
    expire_at: usize,
    seen: Arc<AtomicUsize>,
}

impl GapSleeper {
    /// A sleeper that grants every wait, so the stream is bounded and no bound ever expires.
    fn granting() -> Self {
        Self {
            gaps: Arc::new(Mutex::new(Vec::new())),
            expire_at: usize::MAX,
            seen: Arc::new(AtomicUsize::new(0)),
        }
    }

    /// A sleeper whose `index`-th wait (0-based) expires, so a scripted stall happens where the
    /// scenario puts it rather than wherever the schedule reaches.
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

/// The gaps the scenarios without a heartbeat run under: two values far apart, so which one bounded
/// a given wait is legible in the recording rather than inferred.
const GAPS: TurnGaps = TurnGaps {
    first: Duration::from_secs(30),
    idle: Duration::from_secs(90),
    heartbeat: Duration::MAX,
    period: Duration::ZERO,
};

/// The gaps the heartbeat scenarios run under: the stream may be silent 20 s, each heartbeat
/// counts as 10 s of the turn's silence, and the turn may be quiet 30 s before its first event
/// and 50 s after.
const BEATING: TurnGaps = TurnGaps {
    first: Duration::from_secs(30),
    idle: Duration::from_secs(50),
    heartbeat: Duration::from_secs(20),
    period: Duration::from_secs(10),
};

/// One heartbeat, in the `Result` shape a turn's items have.
#[allow(clippy::unnecessary_wraps)]
fn beat() -> TurnItem {
    Ok(TurnEvent::Heartbeat {
        wait: "queued".to_owned(),
        detail: "1 subtask waiting for room to run".to_owned(),
    })
}

/// A number of seconds, so an expected recording reads as the figures in [`BEATING`].
fn secs(values: &[u64]) -> Vec<Duration> {
    values.iter().copied().map(Duration::from_secs).collect()
}

/// One streamed delta, in the `Result` shape a turn's items have.
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
    let sleeper = GapSleeper::expiring_at(1);
    let items = drain(Some(GAPS), &sleeper, stalling(vec![delta("x")])).await;
    assert_eq!(items.len(), 2);
    assert_eq!(sleeper.gaps().len(), 2);
}

#[tokio::test]
async fn a_stream_with_no_gaps_at_all_is_bounded_by_a_clock_that_never_wins() {
    let sleeper = GapSleeper::granting();
    let items = drain(None, &sleeper, finished(vec![beat(), delta("only")])).await;
    assert_eq!(items, vec![beat(), delta("only")]);
    assert_eq!(
        sleeper.gaps(),
        vec![Duration::MAX, Duration::MAX, Duration::MAX]
    );
    assert_eq!(
        TurnGaps::UNBOUNDED,
        TurnGaps {
            first: Duration::MAX,
            idle: Duration::MAX,
            heartbeat: Duration::MAX,
            period: Duration::ZERO,
        }
    );
}

#[test]
fn the_shipped_gaps_are_the_four_constants_and_the_heartbeat_gap_is_four_periods() {
    let gaps = TurnGaps::default();
    assert_eq!(gaps.first, Duration::from_millis(DEFAULT_TURN_FIRST_GAP_MS));
    assert_eq!(gaps.idle, Duration::from_millis(DEFAULT_TURN_IDLE_GAP_MS));
    assert_eq!(
        gaps.heartbeat,
        Duration::from_millis(DEFAULT_TURN_HEARTBEAT_GAP_MS)
    );
    assert_eq!(gaps.period, Duration::from_millis(HEARTBEAT_PERIOD_MS));
    assert_eq!(DEFAULT_TURN_HEARTBEAT_GAP_MS, 4 * HEARTBEAT_PERIOD_MS);
    assert!(gaps.idle > gaps.first);
    assert!(gaps.first > gaps.heartbeat);
    assert_eq!(RetryPlan::default().turn_gaps, gaps);
}

#[tokio::test]
async fn heartbeats_keep_a_quiet_turn_alive_and_are_passed_on_with_their_wait() {
    let sleeper = GapSleeper::granting();
    let items = drain(
        Some(BEATING),
        &sleeper,
        finished(vec![
            delta("a"),
            beat(),
            beat(),
            beat(),
            beat(),
            delta("b"),
            beat(),
        ]),
    )
    .await;
    assert_eq!(
        items,
        vec![
            delta("a"),
            beat(),
            beat(),
            beat(),
            beat(),
            delta("b"),
            beat()
        ]
    );
    assert_eq!(sleeper.gaps(), secs(&[20, 20, 20, 20, 20, 10, 20, 20]));
}

#[tokio::test]
async fn a_brain_that_stops_beating_ends_on_the_heartbeat_gap() {
    let sleeper = GapSleeper::expiring_at(2);
    let items = drain(Some(BEATING), &sleeper, stalling(vec![delta("a"), beat()])).await;
    assert_eq!(
        items,
        vec![
            delta("a"),
            beat(),
            Err(TransportError::Timeout {
                after: BEATING.heartbeat
            }),
        ]
    );
    assert_eq!(sleeper.gaps(), secs(&[20, 20, 20]));
}

#[tokio::test]
async fn heartbeats_alone_end_the_turn_once_they_add_up_to_its_idle_gap() {
    let sleeper = GapSleeper::granting();
    let items = drain(
        Some(BEATING),
        &sleeper,
        finished(vec![
            delta("a"),
            beat(),
            beat(),
            beat(),
            beat(),
            beat(),
            delta("never read"),
        ]),
    )
    .await;
    assert_eq!(
        items,
        vec![
            delta("a"),
            beat(),
            beat(),
            beat(),
            beat(),
            Err(TransportError::Timeout {
                after: BEATING.idle
            }),
        ]
    );
    assert_eq!(sleeper.gaps(), secs(&[20, 20, 20, 20, 20, 10]));
}

#[tokio::test]
async fn heartbeats_before_any_event_count_against_the_first_event_gap() {
    let sleeper = GapSleeper::granting();
    let items = drain(
        Some(BEATING),
        &sleeper,
        finished(vec![beat(), beat(), beat(), delta("never read")]),
    )
    .await;
    assert_eq!(
        items,
        vec![
            beat(),
            beat(),
            Err(TransportError::Timeout {
                after: BEATING.first
            })
        ]
    );
    assert_eq!(sleeper.gaps(), secs(&[20, 20, 10]));
}

#[tokio::test]
async fn a_silence_that_outlasts_the_turn_s_remaining_allowance_reports_the_allowance() {
    let sleeper = GapSleeper::expiring_at(5);
    let items = drain(
        Some(BEATING),
        &sleeper,
        stalling(vec![delta("a"), beat(), beat(), beat(), beat()]),
    )
    .await;
    assert_eq!(
        items,
        vec![
            delta("a"),
            beat(),
            beat(),
            beat(),
            beat(),
            Err(TransportError::Timeout {
                after: BEATING.idle
            }),
        ]
    );
    assert_eq!(sleeper.gaps(), secs(&[20, 20, 20, 20, 20, 10]));
}

/// A transport whose turn stalls after one event, so the decorator can be driven through the port
/// rather than through `within_gaps` directly.
struct StallingTransport;

impl BrainTransport for StallingTransport {
    async fn health(&self) -> Result<RpcHealth, TransportError> {
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

    async fn ack_reminder(
        &self,
        _reminder_id: &str,
        _fired_at_unix_ms: i64,
    ) -> Result<bool, TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn rename_session(&self, _session_id: &str, _title: &str) -> Result<(), TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn delete_session(&self, _session_id: &str) -> Result<(), TransportError> {
        Err(TransportError::Connection(String::from("unused")))
    }

    async fn set_session_hoisted(
        &self,
        _session_id: &str,
        _hoisted: bool,
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
    assert_eq!(plan.gaps_for(RpcMethod::Converse), Some(GAPS));
}
