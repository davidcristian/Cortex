//! Behavioral tests for `body_core::retry` covering the `RetryingTransport` decorator, its
//! `RetryPolicy` schedule, the `is_transient` classifier, and the `Sleeper` seam (ADR-0024).
//!
//! Deterministic and network-free: a `FlakyTransport` fake fails a scripted number of times
//! before succeeding (and counts every inner call), and a `FakeSleeper` records the backoff
//! *schedule* while returning instantly, so no wall-clock elapses. Both share their state via
//! `Arc` so the test can inspect them after they are moved into the decorator.
//!
//! The gate itself (`SeamMethod`, `RetryPlan`) is pure data and is tested in `retry_plan.rs`;
//! what this file adds is what the decorator *does* under one: a refused method makes one
//! call, and the probe budget shortens the probe without touching the reads.

use std::future::Future;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use body_core::{
    BrainTransport, ConfirmDecision, DueReminder, Randomness, RetryPlan, RetryPolicy,
    RetryingTransport, SeamHealth, SessionMessage, SessionSummary, Sleeper, TransportError,
    TurnEvent, is_transient, retry_with,
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

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        self.tick()?;
        Ok(vec![DueReminder {
            reminder_id: String::from("r1"),
            text: String::from("stand up"),
            fired_at_unix_ms: 1,
            recurring: false,
            tainted: false,
            session_id: String::from("s1"),
        }])
    }

    async fn ack_reminder(&self, reminder_id: &str) -> Result<bool, TransportError> {
        self.tick()?;
        Ok(reminder_id == "r1")
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
async fn retries_list_due_reminders_the_same_way() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    let due = transport.list_due_reminders().await.unwrap();
    assert_eq!(due.len(), 1);
    assert_eq!(due[0].reminder_id, "r1");
    assert_eq!(flaky.call_count(), 2);
    assert_eq!(sleeper.delays().len(), 1);
}

#[tokio::test]
async fn forwards_ack_reminder_without_retrying_it() {
    // The write is a pass-through (ADR-0025): a transient failure surfaces on the first
    // attempt rather than risking a repeat that answers false for an ack that landed.
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport.ack_reminder("r1").await.unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1); // no second attempt
    assert!(sleeper.delays().is_empty());
    // And a healthy ack still crosses the decorator with its argument intact.
    assert!(transport.ack_reminder("r1").await.unwrap());
    assert!(!transport.ack_reminder("other").await.unwrap());
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

/// A `Randomness` that replays scripted unit draws (front to back), sharing the script via
/// `Arc` like `FakeSleeper`. Draws past the script's end return 1 (full delay), so a test
/// only scripts the draws it asserts.
#[derive(Clone, Default)]
struct FakeRandomness {
    draws: Arc<Mutex<Vec<f64>>>,
}

impl FakeRandomness {
    fn scripted(draws: &[f64]) -> Self {
        Self {
            draws: Arc::new(Mutex::new(draws.to_vec())),
        }
    }
}

impl Randomness for FakeRandomness {
    fn unit(&self) -> f64 {
        let mut draws = self.draws.lock().unwrap_or_else(PoisonError::into_inner);
        if draws.is_empty() {
            1.0
        } else {
            draws.remove(0)
        }
    }
}

#[tokio::test]
async fn with_randomness_equal_jitters_each_delay() {
    // Equal jitter (ADR-0024 addendum): each computed delay is scaled by 0.5 + 0.5 * draw,
    // so a 0 draw halves it (the floor) and a 1 draw keeps it whole (the v1 schedule).
    let flaky = FlakyTransport::new(FailKind::Connection, 2);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::with_randomness(
        flaky.clone(),
        sleeper.clone(),
        FakeRandomness::scripted(&[0.0, 1.0]),
        policy(3),
    );
    assert!(transport.health().await.unwrap().ready);
    assert_eq!(
        sleeper.delays(),
        vec![Duration::from_millis(50), Duration::from_millis(200)]
    );
}

#[tokio::test]
async fn out_of_range_and_non_finite_draws_are_sanitized_not_panicked() {
    // A misbehaving source cannot break the Duration math: finite draws are clamped into
    // [0, 1] (2.0 -> full delay, a negative draw -> the half-delay floor), and a non-finite
    // draw (which clamp would propagate as NaN, panicking mul_f64) falls back to full delay.
    let flaky = FlakyTransport::new(FailKind::Connection, 3);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::with_randomness(
        flaky.clone(),
        sleeper.clone(),
        FakeRandomness::scripted(&[2.0, -3.0, f64::NAN]),
        policy(4),
    );
    assert!(transport.health().await.unwrap().ready);
    assert_eq!(
        sleeper.delays(),
        vec![
            Duration::from_millis(100), // 2.0 clamps to 1.0: full first delay
            Duration::from_millis(100), // -3.0 clamps to 0.0: the half-delay floor of 200
            Duration::from_millis(400), // NaN -> full: the third delay (base*4) whole
        ]
    );
}

/// A patient read schedule (as `retry_plan.rs` uses): 6 attempts, 100 ms base, ×2, no cap in
/// play, so its backoffs are 100/200/400/800/1600 ms and its worst case is 3.1 s.
fn patient_reads() -> RetryPolicy {
    policy(6)
}

#[tokio::test]
async fn an_unavailable_write_is_still_not_retried() {
    // The sharpest form of the gate: `Unavailable` is *the* retryable gRPC status, and the
    // plan still refuses, because retryability is decided by what the call does, not by what
    // the failure is called. A status saying the brain could not serve the ack never says the
    // brain did not already clear the reminder.
    let flaky = FlakyTransport::new(FailKind::Unavailable, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), patient_reads());
    assert_eq!(
        transport.ack_reminder("r1").await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }
    );
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
}

#[tokio::test]
async fn the_probe_budget_shortens_the_health_probe() {
    // The connection indicator renders this probe's answer, so its patience is time the dot
    // spends claiming a state the seam has stopped proving. With a 250 ms budget the 100 ms
    // wait fits and 100 + 200 does not, so the probe reports Down after two attempts instead
    // of burning the reads' whole 3.1 s.
    let flaky = FlakyTransport::new(FailKind::Connection, 9);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(
        flaky.clone(),
        sleeper.clone(),
        RetryPlan {
            reads: patient_reads(),
            probe_budget: Duration::from_millis(250),
        },
    );
    assert!(transport.health().await.is_err());
    assert_eq!(flaky.call_count(), 2);
    assert_eq!(sleeper.delays(), vec![Duration::from_millis(100)]);
}

#[tokio::test]
async fn the_same_plan_leaves_the_session_read_patient() {
    // The other half of the pair: trimming the probe must not trim the reads. Same plan,
    // same failure, and `list_sessions` still spends every attempt it was configured for.
    let flaky = FlakyTransport::new(FailKind::Connection, 9);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(
        flaky.clone(),
        sleeper.clone(),
        RetryPlan {
            reads: patient_reads(),
            probe_budget: Duration::from_millis(250),
        },
    );
    assert!(transport.list_sessions(5).await.is_err());
    assert_eq!(flaky.call_count(), 6);
    assert_eq!(
        sleeper.delays(),
        vec![
            Duration::from_millis(100),
            Duration::from_millis(200),
            Duration::from_millis(400),
            Duration::from_millis(800),
            Duration::from_millis(1600),
        ]
    );
}

#[tokio::test]
async fn retry_with_composes_patience_around_a_dial_style_factory() {
    // The extracted loop retries any fallible async factory (the shell wraps its eager dial
    // in exactly this, ADR-0024 addendum): one refused dial, then success.
    let attempts = Arc::new(AtomicUsize::new(0));
    let sleeper = FakeSleeper::default();
    let counted = Arc::clone(&attempts);
    let dialed = retry_with(policy(3), &sleeper, &FakeRandomness::default(), move || {
        let attempt = counted.fetch_add(1, Ordering::SeqCst);
        async move {
            if attempt == 0 {
                Err(TransportError::Connection(String::from("refused")))
            } else {
                Ok(String::from("client"))
            }
        }
    })
    .await;
    assert_eq!(dialed.unwrap(), "client");
    assert_eq!(attempts.load(Ordering::SeqCst), 2);
    assert_eq!(sleeper.delays(), vec![Duration::from_millis(100)]);
}

#[tokio::test]
async fn retry_with_fails_fast_on_a_non_transient_error() {
    // A genuine application answer is returned immediately: no sleep, no second attempt.
    let attempts = Arc::new(AtomicUsize::new(0));
    let sleeper = FakeSleeper::default();
    let counted = Arc::clone(&attempts);
    let denied = retry_with(policy(3), &sleeper, &FakeRandomness::default(), move || {
        counted.fetch_add(1, Ordering::SeqCst);
        std::future::ready(Err::<(), _>(TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("boom"),
        }))
    })
    .await;
    assert!(matches!(denied, Err(TransportError::Rpc { .. })));
    assert_eq!(attempts.load(Ordering::SeqCst), 1);
    assert!(sleeper.delays().is_empty());
}
