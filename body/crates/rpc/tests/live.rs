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

use std::time::{SystemTime, UNIX_EPOCH};

use body_core::BrainTransport;
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
