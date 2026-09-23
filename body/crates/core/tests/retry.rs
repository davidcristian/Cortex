use std::future::Future;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use body_core::{
    BrainTransport, ConfirmDecision, DueReminder, Randomness, RetryPlan, RetryPolicy,
    RetryingTransport, RpcHealth, RpcMethod, SessionMessage, SessionSummary, Sleeper,
    TransportError, TurnEvent, is_transient, retry_with, within_deadline,
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

/// A fake `BrainTransport` that fails its first `remaining` idempotent calls with a scripted error,
/// then succeeds, counting every call.
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
    async fn health(&self) -> Result<RpcHealth, TransportError> {
        self.tick()?;
        Ok(RpcHealth {
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
            hoisted: false,
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

    async fn ack_reminder(
        &self,
        reminder_id: &str,
        fired_at_unix_ms: i64,
    ) -> Result<bool, TransportError> {
        self.tick()?;
        Ok(reminder_id == "r1" && fired_at_unix_ms == 1)
    }

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        self.tick()?;
        let _ = (session_id, title);
        Ok(())
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        self.tick()?;
        let _ = session_id;
        Ok(())
    }

    async fn set_session_hoisted(
        &self,
        session_id: &str,
        hoisted: bool,
    ) -> Result<(), TransportError> {
        self.tick()?;
        let _ = (session_id, hoisted);
        Ok(())
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        self.tick()?;
        Ok(Vec::new())
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        self.tick()?;
        let _ = (key, value);
        Ok(())
    }
}

/// A `Sleeper` that records each requested delay and returns immediately (no real time).
#[derive(Clone, Default)]
struct FakeSleeper {
    recorded: Arc<Mutex<Vec<Duration>>>,
    bounds: Arc<Mutex<Vec<Duration>>>,
    expires: bool,
}

impl Sleeper for FakeSleeper {
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send {
        self.recorded
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(duration);
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
        self.bounds
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(deadline);
        let expires = self.expires;
        async move {
            if expires {
                drop(call);
                return None;
            }
            Some(call.await)
        }
    }
}

impl FakeSleeper {
    /// A sleeper whose every deadline expires before the call it bounds finishes.
    fn expiring() -> Self {
        Self {
            expires: true,
            ..Self::default()
        }
    }

    fn delays(&self) -> Vec<Duration> {
        self.recorded
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }

    /// The deadline each bounded attempt was given, in order.
    fn bounds(&self) -> Vec<Duration> {
        self.bounds
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

/// A fast policy for the retry-succeeds cases, where the cap never applies: `max_attempts` tries,
/// 100 ms base, ×2, capped at 10 s.
fn policy(max_attempts: u32) -> RetryPolicy {
    RetryPolicy {
        max_attempts,
        base_delay: Duration::from_millis(100),
        multiplier: 2,
        max_delay: Duration::from_secs(10),
    }
}

/// A plan whose probe budget cannot bind, so a test about the retry loop sees the schedule it
/// configured rather than the trimmed probe.
fn untrimmed(reads: RetryPolicy) -> RetryPlan {
    RetryPlan {
        reads,
        probe_budget: Duration::from_mins(1),
        ..RetryPlan::default()
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
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), untrimmed(policy(3)));
    assert!(transport.health().await.unwrap().ready);
    assert_eq!(flaky.call_count(), 3);
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
    assert_eq!(flaky.call_count(), 2);
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
    assert_eq!(flaky.call_count(), 1);
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
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
}

#[tokio::test]
async fn retries_list_sessions_the_same_way() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    let sessions = transport.list_sessions(7).await.unwrap();
    assert_eq!(sessions.len(), 1);
    assert_eq!(sessions[0].title, "limit 7");
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
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport.ack_reminder("r1", 1).await.unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
    assert!(transport.ack_reminder("r1", 1).await.unwrap());
    assert!(!transport.ack_reminder("other", 1).await.unwrap());
    assert!(!transport.ack_reminder("r1", 2).await.unwrap());
}

#[tokio::test]
async fn forwards_rename_session_without_retrying_it() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport.rename_session("s1", "Cats").await.unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
    assert!(transport.rename_session("s1", "Cats").await.is_ok());
}

#[tokio::test]
async fn forwards_delete_session_without_retrying_it() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport.delete_session("s1").await.unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
    assert!(transport.delete_session("s1").await.is_ok());
}

#[tokio::test]
async fn forwards_set_session_hoisted_without_retrying_it() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport.set_session_hoisted("s1", true).await.unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
    assert!(transport.set_session_hoisted("s1", true).await.is_ok());
}

#[tokio::test]
async fn retries_get_preferences_the_same_way() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert!(transport.get_preferences().await.is_ok());
    assert_eq!(flaky.call_count(), 2);
    assert_eq!(sleeper.delays().len(), 1);
}

#[tokio::test]
async fn forwards_set_preference_without_retrying_it() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport
            .set_preference("overlay.mark", "ping")
            .await
            .unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1);
    assert!(sleeper.delays().is_empty());
    assert!(
        transport
            .set_preference("overlay.mark", "ping")
            .await
            .is_ok()
    );
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
    assert_eq!(events.len(), 2);
    assert_eq!(events[0], Ok(TurnEvent::Delta(String::from("passed:hi"))));
    assert_eq!(
        events[1],
        Err(TransportError::Connection(String::from("mid-turn")))
    );
    assert_eq!(flaky.call_count(), 0);
    assert!(sleeper.delays().is_empty());
    let gaps = RetryPlan::default().turn_gaps;
    assert_eq!(sleeper.bounds(), vec![gaps.heartbeat; 3]);
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
    assert_eq!(capped.delay(1), Duration::from_millis(500));
    assert_eq!(capped.delay(2), Duration::from_millis(500));
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
    assert_eq!(
        policy.backoff(0, &TransportError::Connection(String::new())),
        Some(Duration::from_millis(100))
    );
    assert_eq!(
        policy.backoff(1, &TransportError::Connection(String::new())),
        None
    );
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
fn an_expired_deadline_is_terminal_and_never_buys_another_attempt() {
    assert!(!is_transient(&TransportError::Timeout {
        after: Duration::from_millis(250),
    }));
}

#[test]
fn the_codes_a_wider_table_would_have_added_are_still_terminal() {
    for code in ["ResourceExhausted", "Aborted", "DeadlineExceeded"] {
        assert!(
            !is_transient(&TransportError::Rpc {
                code: String::from(code),
                message: String::new(),
            }),
            "{code} was classified transient with no producer to justify it"
        );
    }
}

#[test]
fn the_decorator_is_send_and_sync() {
    assert_send_sync::<RetryingTransport<FlakyTransport, FakeSleeper>>();
}

/// A `Randomness` that replays scripted unit draws (front to back), sharing the script via `Arc`
/// like `FakeSleeper`.
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
    let flaky = FlakyTransport::new(FailKind::Connection, 2);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::with_randomness(
        flaky.clone(),
        sleeper.clone(),
        FakeRandomness::scripted(&[0.0, 1.0]),
        untrimmed(policy(3)),
    );
    assert!(transport.health().await.unwrap().ready);
    assert_eq!(
        sleeper.delays(),
        vec![Duration::from_millis(50), Duration::from_millis(200)]
    );
}

#[tokio::test]
async fn out_of_range_and_non_finite_draws_are_sanitized_not_panicked() {
    let flaky = FlakyTransport::new(FailKind::Connection, 3);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::with_randomness(
        flaky.clone(),
        sleeper.clone(),
        FakeRandomness::scripted(&[2.0, -3.0, f64::NAN]),
        untrimmed(policy(4)),
    );
    assert!(transport.health().await.unwrap().ready);
    assert_eq!(
        sleeper.delays(),
        vec![
            Duration::from_millis(100),
            Duration::from_millis(100),
            Duration::from_millis(400),
        ]
    );
}

/// A long read schedule, the same one `retry_plan.rs` uses: 6 attempts, 100 ms base, ×2, and no cap
/// in play, so its backoffs are 100/200/400/800/1600 ms and its worst case is 3.1 s.
fn patient_reads() -> RetryPolicy {
    policy(6)
}

#[tokio::test]
async fn an_unavailable_write_is_still_not_retried() {
    let flaky = FlakyTransport::new(FailKind::Unavailable, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), patient_reads());
    assert_eq!(
        transport.ack_reminder("r1", 1).await.unwrap_err(),
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
    let flaky = FlakyTransport::new(FailKind::Connection, 9);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(
        flaky.clone(),
        sleeper.clone(),
        RetryPlan {
            reads: patient_reads(),
            probe_budget: Duration::from_millis(250),
            probe_deadline: Duration::from_millis(50),
            ..RetryPlan::default()
        },
    );
    assert!(transport.health().await.is_err());
    assert_eq!(flaky.call_count(), 2);
    assert_eq!(sleeper.delays(), vec![Duration::from_millis(100)]);
}

#[tokio::test]
async fn the_same_plan_leaves_the_session_read_patient() {
    let flaky = FlakyTransport::new(FailKind::Connection, 9);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(
        flaky.clone(),
        sleeper.clone(),
        RetryPlan {
            reads: patient_reads(),
            probe_budget: Duration::from_millis(250),
            ..RetryPlan::default()
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

#[tokio::test]
async fn each_attempt_has_the_plans_deadline_for_that_method() {
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let plan = RetryPlan {
        probe_deadline: Duration::from_millis(40),
        call_deadline: Duration::from_secs(90),
        ..RetryPlan::default()
    };
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), plan);
    assert!(transport.health().await.is_ok());
    assert_eq!(
        sleeper.bounds(),
        vec![Duration::from_millis(40), Duration::from_millis(40)]
    );
    assert!(transport.list_sessions(3).await.is_ok());
    assert_eq!(sleeper.bounds().last(), Some(&Duration::from_secs(90)));
}

#[tokio::test]
async fn a_hung_attempt_becomes_a_timeout_and_is_not_retried() {
    let flaky = FlakyTransport::new(FailKind::Connection, 0);
    let sleeper = FakeSleeper::expiring();
    let transport = RetryingTransport::new(
        flaky.clone(),
        sleeper.clone(),
        RetryPlan {
            reads: patient_reads(),
            probe_deadline: Duration::from_millis(80),
            ..RetryPlan::default()
        },
    );
    assert_eq!(
        transport.health().await.unwrap_err(),
        TransportError::Timeout {
            after: Duration::from_millis(80),
        }
    );
    assert_eq!(flaky.call_count(), 0);
    assert_eq!(sleeper.bounds(), vec![Duration::from_millis(80)]);
    assert!(sleeper.delays().is_empty());
}

#[tokio::test]
async fn a_refused_write_is_bounded_even_though_it_is_never_retried() {
    let flaky = FlakyTransport::new(FailKind::Connection, 0);
    let sleeper = FakeSleeper::expiring();
    let transport = RetryingTransport::new(
        flaky.clone(),
        sleeper.clone(),
        RetryPlan {
            call_deadline: Duration::from_secs(7),
            ..RetryPlan::default()
        },
    );
    assert_eq!(
        transport.ack_reminder("r1", 1).await.unwrap_err(),
        TransportError::Timeout {
            after: Duration::from_secs(7),
        }
    );
    assert_eq!(flaky.call_count(), 0);
    assert_eq!(sleeper.bounds(), vec![Duration::from_secs(7)]);
}

#[tokio::test]
async fn the_turn_is_the_one_call_no_deadline_ends_and_its_silence_is_bounded_instead() {
    let flaky = FlakyTransport::new(FailKind::Connection, 0);
    let sleeper = FakeSleeper::expiring();
    let plan = RetryPlan::default();
    let transport = RetryingTransport::new(flaky, sleeper.clone(), plan);
    let events: Vec<_> = transport
        .converse("s1", "hi", tokio_stream::empty())
        .collect()
        .await;
    let heartbeat = plan.turn_gaps.heartbeat;
    assert_eq!(
        events,
        vec![Err(TransportError::Timeout { after: heartbeat })]
    );
    assert_eq!(sleeper.bounds(), vec![heartbeat]);
    assert_eq!(plan.deadline_for(RpcMethod::Converse), None);
}

#[tokio::test]
async fn within_deadline_grants_expires_and_can_be_asked_for_no_bound_at_all() {
    let granting = FakeSleeper::default();
    assert_eq!(
        within_deadline(
            Some(Duration::from_millis(5)),
            &granting,
            std::future::ready(Ok::<_, TransportError>(String::from("in time"))),
        )
        .await
        .unwrap(),
        "in time"
    );
    assert_eq!(granting.bounds(), vec![Duration::from_millis(5)]);
    assert_eq!(
        within_deadline(
            Some(Duration::from_millis(5)),
            &granting,
            std::future::ready(Err::<(), _>(TransportError::Protocol(String::from(
                "garbled"
            )))),
        )
        .await
        .unwrap_err(),
        TransportError::Protocol(String::from("garbled"))
    );
    let expiring = FakeSleeper::expiring();
    assert_eq!(
        within_deadline(
            Some(Duration::from_secs(2)),
            &expiring,
            std::future::pending::<Result<(), TransportError>>(),
        )
        .await
        .unwrap_err(),
        TransportError::Timeout {
            after: Duration::from_secs(2),
        }
    );
    let granted = FakeSleeper::default();
    assert_eq!(
        within_deadline(
            None,
            &granted,
            std::future::ready(Ok::<_, TransportError>(7))
        )
        .await
        .unwrap(),
        7
    );
    assert_eq!(granted.bounds(), vec![Duration::MAX]);
    assert_eq!(expiring.bounds(), vec![Duration::from_secs(2)]);
}
