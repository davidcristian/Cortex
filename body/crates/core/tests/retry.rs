//! Behavioral tests for `body_core::retry` covering the `RetryingTransport` decorator, its
//! `RetryPolicy` schedule, the `is_transient` classifier, and the `Sleeper` seam (ADR-0024).
//!
//! Deterministic and network-free: a `FlakyTransport` fake fails a scripted number of times
//! before succeeding (and counts every inner call), and a `FakeSleeper` records the backoff
//! *schedule* while returning instantly, so no wall-clock elapses. Both share their state via
//! `Arc` so the test can inspect them after they are moved into the decorator. The same fake
//! answers the clock's other question: it records the deadline every attempt was given, and an
//! expiring one scripts the deadline into winning, so what the decorator does with a call that
//! never answers is asserted without a call that never answers.
//!
//! The gate itself (`SeamMethod`, `RetryPlan`) is pure data and is tested in `retry_plan.rs`;
//! what this file adds is what the decorator *does* under one: a refused method makes one
//! call, the probe budget shortens the probe without touching the reads, and an expired
//! deadline ends the call rather than buying it another try.

use std::future::Future;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use body_core::{
    BrainTransport, ConfirmDecision, DueReminder, Randomness, RetryPlan, RetryPolicy,
    RetryingTransport, SeamHealth, SessionMessage, SessionSummary, Sleeper, TransportError,
    TurnEvent, is_transient, retry_with, within_deadline,
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
            pinned: false,
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

    async fn set_session_pinned(
        &self,
        session_id: &str,
        pinned: bool,
    ) -> Result<(), TransportError> {
        self.tick()?;
        let _ = (session_id, pinned);
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

/// A `Sleeper` that records each requested delay and returns immediately (no real time). `Clone`
/// shares the log so the test can read the schedule after the sleeper is moved into the decorator.
///
/// The clock's second question, `bounded`, is logged separately: `bounds()` records the deadline
/// each attempt was given, which is how a test proves the *right* deadline reached the effect
/// for that method. `expires` scripts which side of the race wins. Granting (the default) runs
/// the call, so every schedule assertion in this file is about backoff and nothing else;
/// expiring drops the call unpolled, which is what a real `tokio::time::timeout` does to the
/// loser and therefore what a cancelled attempt looks like from inside the decorator.
#[derive(Clone, Default)]
struct FakeSleeper {
    recorded: Arc<Mutex<Vec<Duration>>>,
    bounds: Arc<Mutex<Vec<Duration>>>,
    expires: bool,
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
                // The deadline won: the call is dropped without ever being polled, so the
                // fake's own call counter proves the attempt was abandoned, not merely lost.
                drop(call);
                return None;
            }
            Some(call.await)
        }
    }
}

impl FakeSleeper {
    /// A sleeper whose every deadline expires: the clock always beats the call.
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

/// A plan whose probe budget cannot bind, so a test about the retry *loop* sees the schedule it
/// configured rather than the trimmed probe. `health` is the loop's usual vehicle here and the
/// trim would otherwise shorten every schedule assertion in the file; the trim has its own
/// tests, where the arithmetic is the point rather than the noise.
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
async fn forwards_rename_session_without_retrying_it() {
    // The catalog write is a pass-through (ADR-0021 management addendum): a transient failure
    // surfaces on the first attempt rather than risking a repeat that re-applies a stale label.
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport.rename_session("s1", "Cats").await.unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1); // no second attempt
    assert!(sleeper.delays().is_empty());
    // And a healthy rename still crosses the decorator.
    assert!(transport.rename_session("s1", "Cats").await.is_ok());
}

#[tokio::test]
async fn forwards_delete_session_without_retrying_it() {
    // The destructive write is a pass-through (ADR-0021 management addendum): a transient failure
    // surfaces on the first attempt rather than risking a silent retry that re-destroys a chat a
    // still-streaming turn may have re-materialized.
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport.delete_session("s1").await.unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1); // no second attempt
    assert!(sleeper.delays().is_empty());
    // And a healthy delete still crosses the decorator.
    assert!(transport.delete_session("s1").await.is_ok());
}

#[tokio::test]
async fn forwards_set_session_pinned_without_retrying_it() {
    // The pin toggle is idempotent by value yet still a pass-through (ADR-0021 pinning addendum):
    // a transient failure surfaces on the first attempt rather than risking a retry that
    // re-asserts a pinned value the user's next toggle reversed.
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert_eq!(
        transport.set_session_pinned("s1", true).await.unwrap_err(),
        TransportError::Connection(String::from("refused"))
    );
    assert_eq!(flaky.call_count(), 1); // no second attempt
    assert!(sleeper.delays().is_empty());
    // And a healthy pin toggle still crosses the decorator.
    assert!(transport.set_session_pinned("s1", true).await.is_ok());
}

#[tokio::test]
async fn retries_get_preferences_the_same_way() {
    // The settings record is a read like the others: a transient failure is worth waiting out,
    // because a repeat answers the same question and touches nothing.
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), policy(3));
    assert!(transport.get_preferences().await.is_ok());
    assert_eq!(flaky.call_count(), 2);
    assert_eq!(sleeper.delays().len(), 1);
}

#[tokio::test]
async fn forwards_set_preference_without_retrying_it() {
    // Last write wins in the store, so a repeat cannot duplicate an effect; it is still a
    // pass-through under the catalog-write convention, so a lost reply never re-asserts a value
    // the user's next change reversed.
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
    assert_eq!(flaky.call_count(), 1); // no second attempt
    assert!(sleeper.delays().is_empty());
    // And a healthy write still crosses the decorator.
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
fn an_expired_deadline_is_terminal_and_never_buys_another_attempt() {
    // The decision the deadline forced, in its smallest form. A timeout is not the brain's
    // report about the call, it is this side's decision to stop waiting, so it cannot say a
    // repeat would go better; and a retried deadline multiplies the very wait it was created
    // to bound, on a peer already too slow to answer. Terminal, and pinned here so widening it
    // is a decision someone makes rather than a line that drifts in.
    assert!(!is_transient(&TransportError::Timeout {
        after: Duration::from_millis(250),
    }));
}

#[test]
fn the_codes_a_wider_table_would_have_added_are_still_terminal() {
    // The three statuses a retryable-code table would have widened this classifier to, each
    // pinned terminal so widening is a decision someone makes here rather than a line that
    // drifts in. `Unavailable` is the whole set on purpose: the other three are conventionally
    // retryable at a *service* whose meaning for them is known, and this seam has no producer
    // for any of them, so each would ship as a guess about a failure nobody has seen.
    // `ResourceExhausted` is the sharpest of the three, because the one producer anywhere on
    // this seam pair raises it for a payload too large to send (the body's own screen capture),
    // and a repeat sends the same payload again. `Aborted` needs a store-contention retry no
    // handler performs. `DeadlineExceeded` used to be listed as merely unreachable, and is not
    // any more: this side sets deadlines now, so once the brain is told about one it can send
    // that status, and it is terminal for the reason the local `Timeout` variant is (above),
    // not for want of a producer. A repeat of any of them buys a second identical answer.
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
    // A misbehaving source cannot break the Duration math: finite draws are clamped into
    // [0, 1] (2.0 -> full delay, a negative draw -> the half-delay floor), and a non-finite
    // draw (which clamp would propagate as NaN, panicking mul_f64) falls back to full delay.
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
    // spends claiming a state the seam has stopped proving. The budget counts what the whole
    // probe costs: two 50 ms attempts and the 100 ms wait between them fit inside 250 ms, and
    // a third attempt would need 450 ms, so the probe reports Down after two tries instead of
    // burning the reads' whole 3.1 s.
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

#[tokio::test]
async fn each_attempt_carries_the_plans_deadline_for_that_method() {
    // The clock is asked once per attempt, with the duration the plan resolved for that
    // method: the probe's own for `health`, the general one for a session read. This is the
    // half a fake could quietly make vacuous, so it is asserted as a value rather than a count.
    let flaky = FlakyTransport::new(FailKind::Connection, 1);
    let sleeper = FakeSleeper::default();
    let plan = RetryPlan {
        probe_deadline: Duration::from_millis(40),
        call_deadline: Duration::from_secs(90),
        ..RetryPlan::default()
    };
    let transport = RetryingTransport::new(flaky.clone(), sleeper.clone(), plan);
    assert!(transport.health().await.is_ok());
    // One failure, so two attempts, each bounded by the probe's deadline.
    assert_eq!(
        sleeper.bounds(),
        vec![Duration::from_millis(40), Duration::from_millis(40)]
    );
    assert!(transport.list_sessions(3).await.is_ok());
    assert_eq!(sleeper.bounds().last(), Some(&Duration::from_secs(90)));
}

#[tokio::test]
async fn a_hung_attempt_becomes_a_timeout_and_is_not_retried() {
    // The case the whole deadline exists for: a brain that accepts the call and never answers.
    // The schedule is deliberately patient (6 attempts) and the failure would be transient if
    // it were a status, so anything that retried on a timeout would show up as more attempts
    // here. Exactly one attempt is made, its call is dropped unpolled (the inner transport
    // never ran), and the caller gets the deadline that expired rather than a status the brain
    // never sent.
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
    // Repeatability and a deadline are independent questions, and this is the call that shows
    // it: the plan refuses to retry an ack, and still bounds it, because bounding a write is
    // not repeating it. Without this the writes would be the one place a hung brain could
    // still hang the body.
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
        transport.ack_reminder("r1").await.unwrap_err(),
        TransportError::Timeout {
            after: Duration::from_secs(7),
        }
    );
    assert_eq!(flaky.call_count(), 0);
    assert_eq!(sleeper.bounds(), vec![Duration::from_secs(7)]);
}

#[tokio::test]
async fn the_turn_is_the_one_call_no_clock_ends() {
    // `Converse` is exempt by decision (a turn is long by design), and the exemption is real
    // rather than nominal: even an expiring clock never sees the turn, which streams its
    // scripted events verbatim.
    let flaky = FlakyTransport::new(FailKind::Connection, 0);
    let sleeper = FakeSleeper::expiring();
    let transport = RetryingTransport::new(flaky, sleeper.clone(), RetryPlan::default());
    let events: Vec<_> = transport
        .converse("s1", "hi", tokio_stream::empty())
        .collect()
        .await;
    assert_eq!(events.len(), 2);
    assert!(sleeper.bounds().is_empty());
}

#[tokio::test]
async fn within_deadline_grants_expires_and_can_be_asked_for_no_bound_at_all() {
    // The composition itself, driven directly: the three answers it has. The `None` case is
    // what `Converse` would take if the decorator ever routed a stream through the loop, and
    // it is also what a caller composing this around a non-seam future can ask for.
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
    // The call's own failure is returned unchanged: bounding a call does not reclassify it.
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
    // No deadline: the clock is still asked, at the end of time, which is what unbounded means
    // to a clock and what keeps this generic function free of an arm no caller could take.
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
