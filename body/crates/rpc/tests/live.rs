//! Live seam checks in the Rust `integration` suite (AGENTS.md gate 3,
//! ADR-0003 decision 3; the Rust counterpart of ADR-0002 decision 8's
//! `integration` marker): `#[ignore]`d so they never run in CI or count
//! toward coverage. Run them manually against a real brain
//! (e.g. `docker compose up brain`, per the local-dev runbook) with:
//!
//! ```text
//! cargo test -p body-rpc --test live -- --ignored
//! ```
//!
//! The target address comes from `CORTEX_BRAIN_ADDR`
//! (default `http://127.0.0.1:50051`); a token-protected brain (ADR-0016)
//! additionally needs `CORTEX_SEAM_TOKEN` set to the same value it serves with.
//!
//! One check, `a_rejected_seam_token_is_answered_at_once_and_never_retried`, requires that
//! token, because a token-free brain accepts anything and leaves it no rejection to observe. It
//! fails with that as its message rather than skipping, so the missing precondition is visible
//! rather than silent. Run the whole suite against a protected brain with
//! `CORTEX_SEAM_TOKEN=… just up` and the same value exported here. `just seam-health` refuses to
//! start without it rather than let that check fail as a regression (ADR-0016 addendum on the
//! checked precondition).
//!
//! Two checks need no brain at all, both of them about what the connection indicator's probe
//! spends against a peer that cannot serve. They stay here because they measure the wall clock
//! the gated suites deliberately fake away.

use std::future::Future;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use body_core::{
    BrainTransport, LinkState, RetryPlan, RetryPolicy, RetryingTransport, Sleeper, probe_link,
};
use body_rpc::BrainSeamClient;
use body_rpc::generated::brain_service_client::BrainServiceClient;
use body_rpc::generated::{ClientEvent, UserTurn, client_event, server_event};
use tokio::net::TcpListener;

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
/// never share session state (the deterministic reply counts the user
/// turns accumulated in the session store under this id).
fn unique_session_id() -> String {
    let nanos = match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(elapsed) => elapsed.as_nanos(),
        Err(error) => panic!("system clock predates the unix epoch: {error}"),
    };
    let pid = std::process::id();
    format!("live-converse-{pid}-{nanos}")
}

/// A local peer that accepts every dial and drops it without a word: a real TCP connection with
/// no gRPC behind it, so every attempt fails `Connection` in about a millisecond on any host.
/// Returns the address to dial and the number of dials answered so far, which is the attempt
/// count read off the wire rather than inferred from a clock.
///
/// It exists because a dead address is not a portable fixture. A dial to a closed loopback port
/// is refused immediately by a Linux stack, and under WSL's mirrored networking, where loopback
/// belongs to the Windows host, a port outside the distro's own ephemeral range is dropped
/// instead, so the connect sits until something above it stops waiting. The probe classifies
/// both as `Down` and is correct both times, but only the refusing shape leaves a retry to
/// observe inside a budget, so a check that measures how long retrying takes has to own the peer
/// it dials.
async fn dial_dropping_peer() -> (String, Arc<AtomicUsize>) {
    let listener = match TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(error) => panic!("cannot bind a loopback listener: {error}"),
    };
    let addr = match listener.local_addr() {
        Ok(addr) => addr,
        Err(error) => panic!("the loopback listener has no address: {error}"),
    };
    let dials = Arc::new(AtomicUsize::new(0));
    let counted = Arc::clone(&dials);
    tokio::spawn(async move {
        while let Ok((stream, _)) = listener.accept().await {
            counted.fetch_add(1, Ordering::SeqCst);
            drop(stream);
        }
    });
    (format!("http://{addr}"), dials)
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
async fn the_link_probe_classifies_the_live_brain_and_a_peer_that_cannot_serve() {
    // What the overlay's connection indicator runs (ADR-0011 addendum), against the real seam:
    // the running brain must probe Ready and carry its own detail, and a peer that cannot serve
    // must probe Down rather than raise. A probe never fails, because the failure is itself the
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

    // A loopback peer that answers the dial and nothing else: the call fails Connection, so the
    // probe is Down and says why. Lazy again, since an eager connect would fail before the probe
    // could classify. This client is bare, with no decorator and therefore no deadline over it,
    // which is why the peer must be one that fails rather than one that hangs: a dial to a closed
    // port is refused on one host and dropped on the next, and on the second one an unbounded
    // attempt sits there until the kernel gives up retrying its SYN, which takes minutes.
    let (unserved, dials) = dial_dropping_peer().await;
    let dead = match BrainSeamClient::connect_lazy_with_token(&unserved, None) {
        Ok(client) => client,
        Err(error) => panic!("cannot build a lazy client for {unserved}: {error}"),
    };
    let dead_status = probe_link(&dead).await;
    assert!(
        dials.load(Ordering::SeqCst) >= 1,
        "the probe never dialed the unserving peer at {unserved}"
    );
    assert_eq!(
        dead_status.state,
        LinkState::Down,
        "a peer that cannot serve probed {state}: {detail}",
        state = dead_status.state.as_str(),
        detail = dead_status.detail
    );
    assert!(
        !dead_status.detail.is_empty(),
        "a down probe should carry the dial failure"
    );
}

/// The real `Sleeper` the shell composes, repeated here because the shell is un-gated and this
/// suite cannot import it. It uses real time on purpose, since these checks measure the wall
/// clock the deterministic fakes avoid.
struct RealSleeper;

impl Sleeper for RealSleeper {
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send {
        tokio::time::sleep(duration)
    }

    async fn bounded<F>(&self, deadline: Duration, call: F) -> Option<F::Output>
    where
        F: Future + Send,
        F::Output: Send,
    {
        tokio::time::timeout(deadline, call).await.ok()
    }
}

/// A long read schedule, as someone tuning `CORTEX_BRAIN_RETRY_*` for a slow brain restart
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
#[ignore = "live seam check: dials a dead loopback address on real time (needs no brain)"]
async fn the_probe_budget_bounds_a_down_verdict_against_a_dead_address() {
    // What the connection indicator spends, measured on the real transport rather than a fake
    // sleeper, against the one peer no fixture can imitate: a loopback address with nothing
    // listening at all. How long the verdict takes here is a fact about the host and only its
    // bound is a fact about this code, which is why the bound is all this asserts.
    //
    // Two shapes reach `Down`, and both are correct. Where the stack refuses the dial, every
    // attempt fails `Connection` in microseconds, that failure is transient, and the probe spends
    // the two attempts its budget allows with one 400 ms wait between them. Where the stack drops
    // the dial instead (WSL's mirrored networking hands loopback to the Windows host, which
    // answers nothing outside the distro's own ephemeral range), the first attempt reaches its
    // 250 ms deadline, and an expired deadline is terminal by decision (ADR-0024 deadline
    // addendum), so the verdict comes after one attempt. A clock cannot tell those apart, so the
    // check that the probe still retries counts attempts against a peer this suite owns instead:
    // `the_probe_trims_its_attempts_where_a_read_spends_them_all` below.
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
            ..RetryPlan::default()
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
    // The budget counts attempts and waits together: two 250 ms attempts plus the 400 ms wait
    // between them fit inside 1 s and a third would need 1.95 s, so the probe can spend at most
    // 900 ms of its own however the dial fails. Anything above that is the wall clock rather than
    // the schedule. Time spent retrying past the budget would be the dot claiming a state the
    // seam stopped proving, and no read knob may extend it.
    assert!(
        probe_took < Duration::from_secs(2),
        "probe took {probe_took:?}, past anything its 1 s budget can spend"
    );
}

#[tokio::test]
#[ignore = "live seam check: runs entirely against a loopback peer of its own (needs no brain)"]
async fn the_probe_trims_its_attempts_where_a_read_spends_them_all() {
    // The other half of the budget's guarantee, and the half a clock cannot show: the probe is
    // trimmed to the attempts its budget affords while the same schedule leaves the reads every
    // one of theirs. Raising `CORTEX_BRAIN_RETRY_ATTEMPTS` for a slow brain restart gives a
    // session read more attempts without extending how long the indicator may show a stale
    // state.
    //
    // Attempts are counted on the wire, off a peer that accepts each dial and drops it, because
    // an elapsed time cannot say how many attempts produced it and because a dead address does
    // not fail the same way on every host (see `dial_dropping_peer`). The time is still real:
    // the wait between the attempts is a real 400 ms of the real `Sleeper`.
    let (unserved, dials) = dial_dropping_peer().await;
    let client = match BrainSeamClient::connect_lazy_with_token(&unserved, None) {
        Ok(client) => client,
        Err(error) => panic!("cannot build a lazy client for {unserved}: {error}"),
    };
    let transport = RetryingTransport::new(
        client,
        RealSleeper,
        RetryPlan {
            reads: patient_reads(),
            probe_budget: Duration::from_secs(1),
            ..RetryPlan::default()
        },
    );

    let started = Instant::now();
    let status = probe_link(&transport).await;
    let probe_took = started.elapsed();
    let probe_dials = dials.swap(0, Ordering::SeqCst);
    assert_eq!(
        status.state,
        LinkState::Down,
        "a peer that cannot serve probed {state}: {detail}",
        state = status.state.as_str(),
        detail = status.detail
    );
    // Two attempts and no more: the first fails `Connection`, which is transient, so the budget
    // allows the one retry that fits (250 + 400 + 250 fits 1 s) and refuses a third (1.95 s).
    assert_eq!(
        probe_dials, 2,
        "the probe made {probe_dials} attempts on a 5-attempt schedule trimmed to a 1 s budget"
    );
    assert!(
        probe_took >= Duration::from_millis(400) && probe_took < Duration::from_secs(2),
        "probe took {probe_took:?}, which is not the one 400 ms wait its budget allows"
    );

    let started = Instant::now();
    let read = transport.list_sessions(1).await;
    let read_took = started.elapsed();
    let read_dials = dials.swap(0, Ordering::SeqCst);
    assert!(read.is_err(), "an unserved peer should fail the read");
    // Same transport, same failure, untrimmed schedule: all 5 attempts, 400 + 800 + 1600 + 3200
    // ms of waiting between them.
    assert_eq!(
        read_dials, 5,
        "the read made {read_dials} attempts of the 5 its schedule allows"
    );
    assert!(
        read_took > probe_took * 2,
        "the read ({read_took:?}) should stay far more patient than the probe ({probe_took:?})"
    );
}

#[tokio::test]
#[ignore = "live seam check: needs a TOKEN-PROTECTED brain (CORTEX_SEAM_TOKEN set on both sides)"]
async fn a_rejected_seam_token_is_answered_at_once_and_never_retried() {
    // The other half of the indicator's contract, and the error-code audit's live evidence: a
    // wrong `CORTEX_SEAM_TOKEN` makes the brain answer `Unauthenticated`, which is not transient,
    // so it must reach the caller on the first attempt with no backoff at all. The classification
    // is `Degraded`, because the brain answered, and never `Down`.
    //
    // Unlike its neighbours this one needs the brain serving with a token (ADR-0016): a
    // token-free brain's interceptor is a pass-through, so there is no rejection to observe and
    // the probe comes back Ready. That is a missing precondition rather than a regression, and
    // the assertion below says so rather than reading as a broken classifier.
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
    // The refusal, live: `ack_reminder` is the one write on the port and the plan does not retry
    // it, so it crosses the decorator exactly once. A brain with no schedule backend answers
    // `false` (ADR-0025), which is what this asserts, and it arrives with no backoff spent on it.
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
    // The raw generated client on purpose, because the `BrainTransport` port does not grow a
    // typed converse method this slice; it lands with the body slices.
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
            // Tool and status traffic is legal on the stream, an announced dispatch's outcome
            // included, and this check only reads the reply text and the turn completion.
            Some(
                server_event::Event::ToolActivity(_)
                | server_event::Event::ToolOutcome(_)
                | server_event::Event::Status(_),
            ) => {}
            // Nothing gated is asked for here, and this raw one-shot client could not answer
            // one anyway (ADR-0022), so a confirm request means something is wrong brain-side.
            Some(server_event::Event::ConfirmRequest(request)) => panic!(
                "unexpected confirm request for tool {tool} on session {session_id}",
                tool = request.tool_name
            ),
            // The same holds for a resolution: with nothing asked, nothing can be resolved.
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

/// Drives one turn to completion over the raw client, so a session exists in the store for the
/// read RPCs to list. It panics on any failure, as a live check does.
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
    // ListSessions and GetSessionMessages (ADR-0021) end to end: seed a turn, then read the
    // chat back over the typed BrainTransport port. It needs only the brain and Redis, with no
    // GPU, since the echo backend serves the turn.
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
