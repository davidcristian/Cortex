//! Behavioral tests for `body_core::retry` covering the `RetryingTransport` decorator, its
//! `RetryPolicy` schedule, the `is_transient` classifier, and the `Sleeper` seam (ADR-0024).
//!
//! Deterministic and network-free: a `FlakyTransport` fake fails a scripted number of times
//! before succeeding (and counts every inner call), and a `FakeSleeper` records the backoff
//! *schedule* while returning instantly, so no wall-clock elapses. Both share their state via
//! `Arc` so the test can inspect them after they are moved into the decorator.

use std::future::Future;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use body_core::{
    BrainTransport, ConfirmDecision, RetryPolicy, RetryingTransport, SeamHealth, SessionMessage,
    SessionSummary, Sleeper, TransportError, TurnEvent, is_transient,
};
use futures_core::Stream;
use tokio_stream::StreamExt;

/// Which error a [`FlakyTransport`] returns while it is still failing (`TransportError` is not
/// `Clone`, so the fake rebuilds one per call from this discriminant).
#[derive(Clone, Copy)]
enum FailKind {
    Connection,
    Unavailable,
    Internal,
    Protocol,
}

impl FailKind {
    fn error(self) -> TransportError {
        match self {
            FailKind::Connection => TransportError::Connection(String::from("refused")),
            FailKind::Unavailable => TransportError::Rpc {
                code: String::from("Unavailable"),
                message: String::from("store down"),
            },
            FailKind::Internal => TransportError::Rpc {
                code: String::from("Internal"),
                message: String::from("boom"),
            },
            FailKind::Protocol => TransportError::Protocol(String::from("garbled")),
        }
    }
}

/// A fake `BrainTransport` that fails its first `remaining` idempotent calls with a scripted
/// error, then succeeds, counting every call. `Clone` shares the `Arc` counters, so a clone
/// kept by the test observes what the decorator did after taking ownership of the original.
#[derive(Clone)]
struct FlakyTransport {
    kind: FailKind,
    remaining: Arc<AtomicUsize>,
    calls: Arc<AtomicUsize>,
}

impl FlakyTransport {
    fn new(kind: FailKind, failures: usize) -> Self {
        Self {
            kind,
            remaining: Arc::new(AtomicUsize::new(failures)),
            calls: Arc::new(AtomicUsize::new(0)),
        }
    }

    /// One idempotent call: fail while failures remain, else succeed.
    fn tick(&self) -> Result<(), TransportError> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        if self.remaining.load(Ordering::SeqCst) > 0 {
            self.remaining.fetch_sub(1, Ordering::SeqCst);
            Err(self.kind.error())
        } else {
            Ok(())
        }
    }

    fn call_count(&self) -> usize {
        self.calls.load(Ordering::SeqCst)
    }
}

impl BrainTransport for FlakyTransport {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        self.tick()?;
        Ok(SeamHealth {
            ready: true,
            detail: String::from("ok"),
        })
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        // A scripted turn that ends in a transport error. The decorator must forward both
        // items verbatim and never retry (converse is non-idempotent). The decisions stream is
        // dropped and the failure counter untouched, proving converse bypasses the retry path.
        drop(decisions);
        let _ = session_id;
        tokio_stream::iter(vec![
            Ok(TurnEvent::Delta(format!("passed:{text}"))),
            Err(TransportError::Connection(String::from("mid-turn"))),
        ])
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        self.tick()?;
        Ok(vec![SessionSummary {
            session_id: String::from("s1"),
            title: format!("limit {limit}"),
            preview: String::from("p"),
            last_activity_unix_ms: 1,
        }])
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        self.tick()?;
        Ok(vec![SessionMessage {
            role: String::from("user"),
            text: String::from(session_id),
            turn_id: String::from("t"),
            at_unix_ms: 1,
        }])
    }
}

/// A `Sleeper` that records each requested delay and returns immediately (no real time). `Clone`
/// shares the log so the test can read the schedule after the sleeper is moved into the decorator.
#[derive(Clone, Default)]
struct FakeSleeper {
    recorded: Arc<Mutex<Vec<Duration>>>,
}

impl Sleeper for FakeSleeper {
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send {
        // Recover the guard from a poisoned lock without unwrap/expect (clippy-denied in
        // non-test-fn helpers). The bare fn ref keeps the never-taken poison path in stdlib,
        // so it adds no uncovered region (mirrors `os.rs`'s `FakeAudio`).
        self.recorded
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(duration);
        std::future::ready(())
    }
}

impl FakeSleeper {
    fn delays(&self) -> Vec<Duration> {
        self.recorded
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

/// A fast, generous policy for the retry-succeeds cases (cap never bites): `max_attempts` tries,
/// 100 ms base, ×2, capped at 10 s.
fn policy(max_attempts: u32) -> RetryPolicy {
    RetryPolicy {
        max_attempts,
        base_delay: Duration::from_millis(100),
        multiplier: 2,
        max_delay: Duration::from_secs(10),
    }
}

/// Compile-time check that a decorated `health` future is `Send`.
fn assert_send<F: Future + Send>(future: F) -> F {
    future
}

fn assert_send_sync<T: Send + Sync>() {}

#[tokio::test]
async fn succeeds_on_the_first_try_without_sleeping() {
    let flaky = FlakyTransport::new(FailKind::Connection, 0);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    let health = assert_send(transport.health()).await.unwrap();
    assert!(health.ready);
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
}

#[tokio::test]
async fn retries_a_transient_failure_then_succeeds() {
    let flaky = FlakyTransport::new(FailKind::Connection, 2);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert!(transport.health().await.unwrap().ready);
    assert_eq!(flaky.call_count(), 3); // first + two retries
    // Exponential backoff before each retry: base, then base × multiplier.
    assert_eq!(
        sleeper.delays(),
        vec![Duration::from_millis(100), Duration::from_millis(200)]
    );
}

#[tokio::test]
async fn gives_up_after_the_last_attempt_and_returns_the_error() {
    let flaky = FlakyTransport::new(FailKind::Connection, 9);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(2));
    let error = transport.health().await.unwrap_err();
    assert_eq!(error, TransportError::Connection(String::from("refused")));
    assert_eq!(flaky.call_count(), 2); // two attempts, one retry
    assert_eq!(sleeper.delays(), vec![Duration::from_millis(100)]);
}

#[tokio::test]
async fn does_not_retry_a_non_transient_rpc_error() {
    let flaky = FlakyTransport::new(FailKind::Internal, 9);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(5));
    let error = transport.health().await.unwrap_err();
    assert_eq!(
        error,
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("boom"),
        }
    );
    assert_eq!(flaky.call_count(), 1); // no retry
    assert!(sleeper.delays().is_empty());
}

#[tokio::test]
async fn retries_an_unavailable_rpc_error() {
    let flaky = FlakyTransport::new(FailKind::Unavailable, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert!(transport.health().await.unwrap().ready);
    assert_eq!(flaky.call_count(), 2);
    assert_eq!(sleeper.delays().len(), 1);
}

#[tokio::test]
async fn does_not_retry_a_protocol_error() {
    let flaky = FlakyTransport::new(FailKind::Protocol, 9);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(5));
    assert_eq!(
        transport.health().await.unwrap_err(),
        TransportError::Protocol(String::from("garbled"))
    );
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
}

#[tokio::test]
async fn max_attempts_of_one_disables_retry() {
    let flaky = FlakyTransport::new(FailKind::Connection, 9);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(1));
    assert!(transport.health().await.is_err());
    assert_eq!(flaky.call_count(), 1); // single try, no backoff
    assert!(sleeper.delays().is_empty());
}

#[tokio::test]
async fn retries_list_sessions_the_same_way() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    let sessions = transport.list_sessions(7).await.unwrap();
    assert_eq!(sessions.len(), 1);
    assert_eq!(sessions[0].title, "limit 7"); // the argument survived the retry
    assert_eq!(flaky.call_count(), 2);
    assert_eq!(sleeper.delays().len(), 1);
}

#[tokio::test]
async fn retries_session_messages_the_same_way() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    let messages = transport.session_messages("chat-3").await.unwrap();
    assert_eq!(messages.len(), 1);
    assert_eq!(messages[0].text, "chat-3");
    assert_eq!(flaky.call_count(), 2);
    assert_eq!(sleeper.delays().len(), 1);
}

#[tokio::test]
async fn converse_is_forwarded_verbatim_without_retry() {
    let flaky = FlakyTransport::new(FailKind::Connection, 0);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(5));
    let decisions = tokio_stream::iter(vec![ConfirmDecision {
        confirm_id: String::from("c-1"),
        approved: true,
    }]);
    let stream = transport.converse("sess", "hi", decisions);
    tokio::pin!(stream);
    let mut events = Vec::new();
    while let Some(item) = stream.next().await {
        events.push(item);
    }
    // Both items forwarded, including the terminal error. There is no retry, no sleep, no tick.
    assert_eq!(events.len(), 2);
    assert_eq!(events[0], Ok(TurnEvent::Delta(String::from("passed:hi"))));
    assert_eq!(
        events[1],
        Err(TransportError::Connection(String::from("mid-turn")))
    );
    assert_eq!(flaky.call_count(), 0);
    assert!(sleeper.delays().is_empty());
}

#[test]
fn retry_policy_delay_grows_exponentially_and_caps() {
    let capped = RetryPolicy {
        max_attempts: 5,
        base_delay: Duration::from_millis(100),
        multiplier: 10,
        max_delay: Duration::from_millis(500),
    };
    assert_eq!(capped.delay(0), Duration::from_millis(100));
    assert_eq!(capped.delay(1), Duration::from_millis(500)); // 1000 clamped to the cap
    assert_eq!(capped.delay(2), Duration::from_millis(500)); // stays at the cap
    // A base already above the cap is clamped from the start.
    let over = RetryPolicy {
        base_delay: Duration::from_secs(1),
        max_delay: Duration::from_millis(500),
        ..capped
    };
    assert_eq!(over.delay(0), Duration::from_millis(500));
}

#[test]
fn retry_policy_backoff_decides_when_to_wait() {
    let policy = policy(2);
    // Transient with an attempt remaining → wait.
    assert_eq!(
        policy.backoff(0, &TransportError::Connection(String::new())),
        Some(Duration::from_millis(100))
    );
    // Transient but no attempt left → give up.
    assert_eq!(
        policy.backoff(1, &TransportError::Connection(String::new())),
        None
    );
    // Non-transient → give up even with attempts left.
    assert_eq!(
        policy.backoff(0, &TransportError::Protocol(String::new())),
        None
    );
}

#[test]
fn retry_policy_default_is_the_documented_schedule() {
    let default = RetryPolicy::default();
    assert_eq!(default.max_attempts, 3);
    assert_eq!(default.base_delay, Duration::from_millis(200));
    assert_eq!(default.multiplier, 2);
    assert_eq!(default.max_delay, Duration::from_secs(2));
    // Copy + Eq + Debug.
    let copy = default;
    assert_eq!(copy, default);
    assert_ne!(
        default,
        RetryPolicy {
            max_attempts: 4,
            ..default
        }
    );
    assert!(format!("{default:?}").contains("RetryPolicy"));
}

#[test]
fn is_transient_classifies_every_variant() {
    assert!(is_transient(&TransportError::Connection(String::from("x"))));
    assert!(is_transient(&TransportError::Rpc {
        code: String::from("Unavailable"),
        message: String::new(),
    }));
    assert!(!is_transient(&TransportError::Rpc {
        code: String::from("Internal"),
        message: String::new(),
    }));
    assert!(!is_transient(&TransportError::Protocol(String::from("x"))));
}

#[test]
fn the_decorator_is_send_and_sync() {
    assert_send_sync::<RetryingTransport<FlakyTransport, FakeSleeper>>();
}
