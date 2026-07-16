//! Live seam checks in the Rust `integration` suite (AGENTS.md gate 3,
//! ADR-0003 decision 3; the Rust counterpart of ADR-0002 decision 8's
//! `integration` marker): `#[ignore]`d so they never run in CI or count
//! toward coverage. Run them manually against a real brain
//! (e.g. `docker compose up brain`, Slice 2 runbook) with:
//!
//! ```text
//! cargo test -p body-rpc --test live -- --ignored
//! ```
//!
//! The target address comes from `CORTEX_BRAIN_ADDR`
//! (default `http://127.0.0.1:50051`); a token-protected brain (ADR-0016)
//! additionally needs `CORTEX_SEAM_TOKEN` set to the same value it serves with.
//!
//! One check, `a_rejected_seam_token_is_answered_at_once_and_never_retried`, *requires* that
//! token: a token-free brain accepts anything, so there is no rejection for it to observe. It
//! fails with that as its message rather than skipping, since a live check that quietly opts
//! out is worse than one that says what it needs. Run the whole suite against a protected
//! brain with `CORTEX_SEAM_TOKEN=… just up` and the same value exported here.

use std::future::Future;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use body_core::{
    BrainTransport, LinkState, RetryPlan, RetryPolicy, RetryingTransport, Sleeper, probe_link,
};
use body_rpc::BrainSeamClient;
use body_rpc::generated::brain_service_client::BrainServiceClient;
use body_rpc::generated::{ClientEvent, UserTurn, client_event, server_event};

/// The live brain's address: `CORTEX_BRAIN_ADDR`, defaulting to the brain
/// server's own defaults (ADR-0003 decision 6).
fn brain_addr() -> String {
    std::env::var("CORTEX_BRAIN_ADDR").unwrap_or_else(|_| String::from("http://127.0.0.1:50051"))
}

/// The seam token to present, when the live brain requires one (ADR-0016).
fn seam_token() -> Option<String> {
    std::env::var("CORTEX_SEAM_TOKEN")
        .ok()
        .filter(|token| !token.is_empty())
}

/// A session id unique per test run, so reruns against the same live brain
/// never share session state (Slice 3's deterministic reply counts the user
/// turns accumulated in the session store under this id).
fn unique_session_id() -> String {
    let nanos = match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(elapsed) => elapsed.as_nanos(),
        Err(error) => panic!("system clock predates the unix epoch: {error}"),
    };
    let pid = std::process::id();
    format!("live-converse-{pid}-{nanos}")
}

#[tokio::test]
#[ignore = "live seam check: needs a real brain at CORTEX_BRAIN_ADDR (run with -- --ignored)"]
async fn brain_reports_ready_over_the_live_seam() {
    let addr = brain_addr();
    let token = seam_token();
    let client = match BrainSeamClient::connect_with_token(&addr, token.as_deref()).await {
        Ok(client) => client,
        Err(error) => panic!("cannot reach the brain at {addr}: {error}"),
    };
    let health = match client.health().await {
        Ok(health) => health,
        Err(error) => panic!("brain health call at {addr} failed: {error}"),
    };
    assert!(
        health.ready,
        "brain at {addr} is not ready: {}",
        health.detail
    );
}

#[tokio::test]
#[ignore = "live seam check: needs a real brain at CORTEX_BRAIN_ADDR (run with -- --ignored)"]
async fn the_link_probe_classifies_the_live_brain_and_a_dead_address() {
    // What the overlay's connection indicator runs (ADR-0011 addendum), against the real seam:
    // the running brain must probe Ready and carry its own detail, and an address nothing
    // listens on must probe Down rather than raise. A probe never fails; the failure is the
    // answer, which is what lets the dot render a state instead of an error.
    let addr = brain_addr();
    let token = seam_token();
    let client = match BrainSeamClient::connect_lazy_with_token(&addr, token.as_deref()) {
        Ok(client) => client,
        Err(error) => panic!("cannot build a lazy client for {addr}: {error}"),
    };
    let status = probe_link(&client).await;
    assert_eq!(
        status.state,
        LinkState::Ready,
        "the brain at {addr} probed {state}: {detail}",
        state = status.state.as_str(),
        detail = status.detail
    );
    assert!(
        !status.detail.is_empty(),
        "a ready brain should name itself in the probe detail"
    );

    // A loopback port with nothing behind it: the dial is refused, so the probe is Down and
    // says why. Lazy again, since an eager connect would fail before the probe could classify.
    let dead = match BrainSeamClient::connect_lazy_with_token("http://127.0.0.1:1", None) {
        Ok(client) => client,
        Err(error) => panic!("cannot build a lazy client for the dead address: {error}"),
    };
    let dead_status = probe_link(&dead).await;
    assert_eq!(
        dead_status.state,
        LinkState::Down,
        "an unreachable address probed {state}: {detail}",
        state = dead_status.state.as_str(),
        detail = dead_status.detail
    );
    assert!(
        !dead_status.detail.is_empty(),
        "a down probe should carry the dial failure"
    );
}

/// The real `Sleeper` the shell composes, repeated here because the shell is un-gated and this
/// suite cannot import it. Real time on purpose: these checks measure the wall clock the
/// deterministic fakes deliberately avoid.
struct RealSleeper;

impl Sleeper for RealSleeper {
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send {
        tokio::time::sleep(duration)
    }
}

/// A patient read schedule, as someone tuning `CORTEX_BRAIN_RETRY_*` for a slow brain restart
/// would set it: 5 attempts, 400 ms base, ×2, so the reads spend up to 6 s backing off.
fn patient_reads() -> RetryPolicy {
    RetryPolicy {
        max_attempts: 5,
        base_delay: Duration::from_millis(400),
        multiplier: 2,
        max_delay: Duration::from_secs(10),
    }
}

#[tokio::test]
#[ignore = "live seam check: needs a real brain at CORTEX_BRAIN_ADDR (run with -- --ignored)"]
async fn the_probe_budget_bounds_a_down_verdict_against_a_dead_address() {
    // The connection indicator's honesty, measured on the real transport rather than a fake
    // sleeper. Against an address nothing listens on, every attempt fails `Connection`, so the
    // schedule is spent in full: the reads take their whole 6 s, while the `Health` probe is
    // trimmed to its 1 s budget and reports Down inside it. Raising the read knobs must not
    // buy the dot a longer lie, and this is the assertion that says so on real time.
    let dead = match BrainSeamClient::connect_lazy_with_token("http://127.0.0.1:1", None) {
        Ok(client) => client,
        Err(error) => panic!("cannot build a lazy client for the dead address: {error}"),
    };
    let transport = RetryingTransport::new(
        dead,
        RealSleeper,
        RetryPlan {
            reads: patient_reads(),
            probe_budget: Duration::from_secs(1),
        },
    );

    let started = Instant::now();
    let status = probe_link(&transport).await;
    let probe_took = started.elapsed();
    assert_eq!(
        status.state,
        LinkState::Down,
        "an unreachable address probed {state}: {detail}",
        state = status.state.as_str(),
        detail = status.detail
    );
    // Backoff of 400 + 800 ms overruns the 1 s budget, so the probe keeps two attempts and
    // waits once. The upper bound is the honesty claim; the lower one proves it still retried.
    assert!(
        probe_took >= Duration::from_millis(400) && probe_took < Duration::from_secs(2),
        "probe took {probe_took:?}, outside the one wait its 1 s budget allows"
    );

    let started = Instant::now();
    let read = transport.list_sessions(1).await;
    let read_took = started.elapsed();
    assert!(read.is_err(), "a dead address should fail the read");
    // Same transport, same failure, untrimmed schedule: 400 + 800 + 1600 + 3200 ms of waiting.
    assert!(
        read_took > probe_took * 2,
        "the read ({read_took:?}) should stay far more patient than the probe ({probe_took:?})"
    );
}

#[tokio::test]
#[ignore = "live seam check: needs a TOKEN-PROTECTED brain (CORTEX_SEAM_TOKEN set on both sides)"]
async fn a_rejected_seam_token_is_answered_at_once_and_never_retried() {
    // The other half of the indicator's contract, and the error-code audit's live evidence:
    // a wrong `CORTEX_SEAM_TOKEN` makes the brain *answer* `Unauthenticated`, which is not
    // transient, so it must reach the caller on the first attempt with no backoff at all. The
    // classification is `Degraded` (the brain answered), never `Down`.
    //
    // Unlike its neighbours this one needs the brain serving *with* a token (ADR-0016): a
    // token-free brain's interceptor is a pass-through, so there is no rejection to observe
    // and the probe comes back Ready. That is a precondition, not a regression, and the
    // assertion below says so rather than reading as a broken classifier.
    let addr = brain_addr();
    let client = match BrainSeamClient::connect_lazy_with_token(&addr, Some("not-the-token")) {
        Ok(client) => client,
        Err(error) => panic!("cannot build a lazy client for {addr}: {error}"),
    };
    let transport = RetryingTransport::new(client, RealSleeper, patient_reads());
    let started = Instant::now();
    let status = probe_link(&transport).await;
    let took = started.elapsed();
    assert_ne!(
        status.state,
        LinkState::Ready,
        "the brain at {addr} accepted a deliberately wrong token, so it is serving without \
         auth: rerun the stack with CORTEX_SEAM_TOKEN set on both sides"
    );
    assert_eq!(
        status.state,
        LinkState::Degraded,
        "a rejected token probed {state}: {detail}",
        state = status.state.as_str(),
        detail = status.detail
    );
    assert!(
        status.detail.starts_with("Unauthenticated"),
        "expected an Unauthenticated status in the detail, got: {}",
        status.detail
    );
    // No wait was taken, so this is the dial plus one round trip on loopback.
    assert!(
        took < Duration::from_millis(400),
        "a terminal status took {took:?}, so it was retried when it should not have been"
    );
}

#[tokio::test]
#[ignore = "live seam check: needs a real brain at CORTEX_BRAIN_ADDR (run with -- --ignored)"]
async fn the_ack_write_is_answered_once_against_the_live_brain() {
    // The gate, live: `ack_reminder` is the one write on the port and the plan refuses it, so
    // it crosses the decorator exactly once. A brain with no schedule backend answers `false`
    // benignly (ADR-0025), which is the answer this asserts; the point is that it is *an*
    // answer and arrives with no backoff spent on it.
    let addr = brain_addr();
    let token = seam_token();
    let client = match BrainSeamClient::connect_lazy_with_token(&addr, token.as_deref()) {
        Ok(client) => client,
        Err(error) => panic!("cannot build a lazy client for {addr}: {error}"),
    };
    let transport = RetryingTransport::new(client, RealSleeper, patient_reads());
    let started = Instant::now();
    let acked = match transport.ack_reminder("live-no-such-reminder").await {
        Ok(acked) => acked,
        Err(error) => panic!("AckReminder at {addr} failed: {error}"),
    };
    assert!(!acked, "an unknown reminder id should not report as acked");
    assert!(
        started.elapsed() < Duration::from_millis(400),
        "the unretried write should cost one round trip, not a backoff"
    );
}

#[tokio::test]
#[ignore = "live seam check: needs a real brain at CORTEX_BRAIN_ADDR (run with -- --ignored)"]
async fn converse_round_trips_one_turn_over_the_live_seam() {
    let addr = brain_addr();
    // Raw generated client on purpose: the `BrainTransport` port does not
    // grow a typed converse method this slice (it lands with the body slices).
    let mut client = match BrainServiceClient::connect(addr.clone()).await {
        Ok(client) => client,
        Err(error) => panic!("cannot reach the brain at {addr}: {error}"),
    };
    let session_id = unique_session_id();
    let turn = ClientEvent {
        session_id: session_id.clone(),
        event: Some(client_event::Event::UserTurn(UserTurn {
            text: String::from("ping from the body"),
            images: Vec::new(),
        })),
    };
    let mut request = tonic::Request::new(tokio_stream::iter(vec![turn]));
    if let Some(token) = seam_token() {
        let value = match token.parse() {
            Ok(value) => value,
            Err(error) => panic!("CORTEX_SEAM_TOKEN is not valid ASCII metadata: {error}"),
        };
        request.metadata_mut().insert("x-cortex-seam-token", value);
    }
    let response = match client.converse(request).await {
        Ok(response) => response,
        Err(status) => {
            panic!("opening Converse on session {session_id} at {addr} failed: {status}")
        }
    };
    let mut events = response.into_inner();

    // Collect TextDelta fragments until TurnComplete ends the turn.
    let mut delta_count = 0_usize;
    let mut reply_text = String::new();
    let turn_id = loop {
        let event = match events.message().await {
            Ok(Some(event)) => event,
            Ok(None) => panic!(
                "Converse stream on session {session_id} ended without a TurnComplete \
                 (after {delta_count} deltas)"
            ),
            Err(status) => {
                panic!("Converse stream on session {session_id} failed mid-turn: {status}")
            }
        };
        match event.event {
            Some(server_event::Event::TextDelta(delta)) => {
                delta_count += 1;
                reply_text.push_str(&delta.text);
            }
            Some(server_event::Event::TurnComplete(complete)) => break complete.turn_id,
            Some(server_event::Event::Error(error)) => panic!(
                "brain reported a seam error on session {session_id}: [{code}] {message}",
                code = error.code,
                message = error.message
            ),
            // Tool/status traffic is legal on the stream; this check only
            // cares about the reply text and turn completion.
            Some(server_event::Event::ToolActivity(_) | server_event::Event::Status(_)) => {}
            // Nothing gated is asked for here, and this raw one-shot client
            // could not answer anyway (ADR-0022). A confirm request means
            // something is wrong brain-side.
            Some(server_event::Event::ConfirmRequest(request)) => panic!(
                "unexpected confirm request for tool {tool} on session {session_id}",
                tool = request.tool_name
            ),
            // Likewise its resolution: with nothing asked, nothing can have been resolved.
            Some(server_event::Event::ConfirmResolved(resolved)) => panic!(
                "unexpected confirm resolution ({outcome}) on session {session_id}",
                outcome = resolved.outcome
            ),
            None => panic!("server sent an event with an empty oneof on session {session_id}"),
        }
    };

    assert!(
        delta_count >= 1,
        "no TextDelta arrived before TurnComplete on session {session_id}"
    );
    assert!(
        !reply_text.is_empty(),
        "concatenated reply text is empty on session {session_id}"
    );
    assert!(
        !turn_id.is_empty(),
        "TurnComplete carried an empty turn_id on session {session_id}"
    );
}

/// Drives one turn to completion over the raw client, so a session exists in the
/// store for the read RPCs to list. Panics on any failure (this is a live check).
async fn seed_one_turn(addr: &str, session_id: &str, text: &str) {
    let mut client = match BrainServiceClient::connect(addr.to_owned()).await {
        Ok(client) => client,
        Err(error) => panic!("cannot reach the brain at {addr}: {error}"),
    };
    let turn = ClientEvent {
        session_id: session_id.to_owned(),
        event: Some(client_event::Event::UserTurn(UserTurn {
            text: text.to_owned(),
            images: Vec::new(),
        })),
    };
    let mut request = tonic::Request::new(tokio_stream::iter(vec![turn]));
    if let Some(token) = seam_token() {
        match token.parse() {
            Ok(value) => {
                request.metadata_mut().insert("x-cortex-seam-token", value);
            }
            Err(error) => panic!("CORTEX_SEAM_TOKEN is not valid ASCII metadata: {error}"),
        }
    }
    let mut events = match client.converse(request).await {
        Ok(response) => response.into_inner(),
        Err(status) => panic!("seeding a turn on {session_id} failed: {status}"),
    };
    // Drain until the turn completes, so the assistant reply is persisted too.
    loop {
        match events.message().await {
            Ok(Some(event)) => {
                if matches!(event.event, Some(server_event::Event::TurnComplete(_))) {
                    return;
                }
            }
            Ok(None) => panic!("seed turn on {session_id} ended without TurnComplete"),
            Err(status) => panic!("seed turn on {session_id} failed mid-stream: {status}"),
        }
    }
}

#[tokio::test]
#[ignore = "live seam check: needs a real brain at CORTEX_BRAIN_ADDR (run with -- --ignored)"]
async fn session_reads_round_trip_over_the_live_seam() {
    // ListSessions / GetSessionMessages (ADR-0021) end to end: seed a turn, then read
    // the chat back over the typed BrainTransport port. Needs only the brain + Redis
    // (no GPU), since the echo backend serves the turn.
    let addr = brain_addr();
    let token = seam_token();
    let session_id = unique_session_id();
    let question = "list me over the seam";
    seed_one_turn(&addr, &session_id, question).await;

    let client = match BrainSeamClient::connect_with_token(&addr, token.as_deref()).await {
        Ok(client) => client,
        Err(error) => panic!("cannot reach the brain at {addr}: {error}"),
    };

    let sessions = match client.list_sessions(50).await {
        Ok(sessions) => sessions,
        Err(error) => panic!("ListSessions at {addr} failed: {error}"),
    };
    let Some(mine) = sessions.iter().find(|s| s.session_id == session_id) else {
        panic!("session {session_id} was not returned by ListSessions");
    };
    // Title derives from the first user message (ADR-0021), which fits under the cap.
    assert_eq!(mine.title, question);
    assert!(
        mine.last_activity_unix_ms > 0,
        "expected a real last-activity timestamp, got {}",
        mine.last_activity_unix_ms
    );

    let messages = match client.session_messages(&session_id).await {
        Ok(messages) => messages,
        Err(error) => panic!("GetSessionMessages at {addr} failed: {error}"),
    };
    assert!(
        messages.len() >= 2,
        "expected the user turn + assistant reply, got {} messages",
        messages.len()
    );
    assert_eq!(messages[0].role, "user");
    assert_eq!(messages[0].text, question);
    assert_eq!(messages[1].role, "assistant");
    assert!(
        !messages[1].text.is_empty(),
        "the assistant reply for {session_id} was empty"
    );
}
