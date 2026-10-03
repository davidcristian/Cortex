//! Contract tests for `BrainRpcClient::converse`: a scripted in-process fake serves the generated
//! `BrainService.Converse` on loopback (CI-safe port 0) and the adapter's `ServerEvent`→`TurnEvent`
//! mapping is asserted end to end.

mod brain;

use std::net::SocketAddr;

use body_core::{AttachedImage, BrainTransport, ConfirmDecision, TransportError, TurnEvent};
use body_rpc::BrainRpcClient;
use brain::{FakeBrain, Script, Turn, spawn_fake_brain};
use tokio_stream::{Stream, StreamExt};

/// Serves the fake brain scripted to stream `turn` on an ephemeral loopback port.
async fn spawn_turn(turn: Turn) -> Result<SocketAddr, std::io::Error> {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.turn = turn;
    spawn_fake_brain(fake).await
}

/// Runs one turn through the transport port and collects every stream item.
async fn run_turn(
    turn: Turn,
    session_id: &str,
    text: &str,
    decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
) -> Result<Vec<Result<TurnEvent, TransportError>>, Box<dyn std::error::Error>> {
    let addr = spawn_turn(turn).await?;
    let client = BrainRpcClient::connect(&format!("http://{addr}")).await?;
    let stream = client.converse(session_id, text, Vec::new(), decisions);
    tokio::pin!(stream);
    let mut out = Vec::new();
    while let Some(item) = stream.next().await {
        out.push(item);
    }
    Ok(out)
}

/// Runs one `Turn::Confirm` turn the way the overlay would: the decision is sent in reaction to
/// the streamed `ConfirmRequest`, over a channel whose sender the caller holds open, rather than
/// being scripted in advance.
async fn run_confirm_turn(approved: bool) -> Result<Vec<TurnEvent>, Box<dyn std::error::Error>> {
    let addr = spawn_turn(Turn::Confirm { approved }).await?;
    let client = BrainRpcClient::connect(&format!("http://{addr}")).await?;
    let (sender, receiver) = tokio::sync::mpsc::unbounded_channel();
    let decisions = tokio_stream::wrappers::UnboundedReceiverStream::new(receiver);
    let stream = client.converse("sess-c", "send it", Vec::new(), decisions);
    tokio::pin!(stream);
    let mut events = Vec::new();
    while let Some(item) = stream.next().await {
        let event = item?;
        if let TurnEvent::ConfirmRequest { confirm_id, .. } = &event {
            sender.send(ConfirmDecision {
                confirm_id: confirm_id.clone(),
                approved,
            })?;
        }
        events.push(event);
    }
    Ok(events)
}

#[tokio::test]
async fn echo_turn_round_trips_every_event_kind() {
    let events = run_turn(Turn::Echo, "sess-42", "ping", tokio_stream::empty())
        .await
        .unwrap();
    let events: Vec<TurnEvent> = events.into_iter().map(Result::unwrap).collect();
    assert_eq!(
        events,
        vec![
            TurnEvent::Delta(String::from("echo:ping")),
            TurnEvent::Delta(String::from("sid:sess-42")),
            TurnEvent::ToolActivity {
                tool_name: String::from("read_email"),
                summary: String::from("reading inbox"),
            },
            TurnEvent::ToolOutcome {
                tool_name: String::from("read_email"),
                ok: false,
            },
            TurnEvent::Heartbeat {
                wait: String::from("calling"),
                detail: String::from("waiting for a tool to finish"),
            },
            TurnEvent::Status {
                state: String::from("model_loading"),
                detail: String::from("swapping"),
            },
            TurnEvent::Complete {
                turn_id: String::from("turn-echo"),
            },
        ],
    );
}

#[tokio::test]
async fn brain_reported_seam_error_maps_to_failed_and_is_terminal() {
    let events = run_turn(Turn::PartialThenError, "s", "hi", tokio_stream::empty())
        .await
        .unwrap();
    assert_eq!(events.len(), 2);
    assert_eq!(
        events[0].as_ref().unwrap(),
        &TurnEvent::Delta(String::from("partial"))
    );
    assert_eq!(
        events[1].as_ref().unwrap(),
        &TurnEvent::Failed {
            code: String::from("overloaded"),
            message: String::from("brain is busy"),
        },
    );
}

#[tokio::test]
async fn empty_server_event_maps_to_protocol_error() {
    let events = run_turn(Turn::EmptyEvent, "s", "hi", tokio_stream::empty())
        .await
        .unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(
        events[0].as_ref().unwrap_err(),
        &TransportError::Protocol(String::from("converse server event had no event set")),
    );
}

#[tokio::test]
async fn stream_ending_before_completion_maps_to_protocol_error() {
    let events = run_turn(Turn::EarlyClose, "s", "hi", tokio_stream::empty())
        .await
        .unwrap();
    assert_eq!(events.len(), 2);
    assert_eq!(
        events[0].as_ref().unwrap(),
        &TurnEvent::Delta(String::from("hi"))
    );
    assert_eq!(
        events[1].as_ref().unwrap_err(),
        &TransportError::Protocol(String::from(
            "converse stream ended before the turn completed"
        )),
    );
}

#[tokio::test]
async fn rejected_converse_call_maps_to_rpc_error() {
    let events = run_turn(Turn::RejectCall, "s", "hi", tokio_stream::empty())
        .await
        .unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(
        events[0].as_ref().unwrap_err(),
        &TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("cannot start turn"),
        },
    );
}

#[tokio::test]
async fn status_raised_mid_stream_maps_to_rpc_error() {
    let events = run_turn(Turn::MidStreamError, "s", "hi", tokio_stream::empty())
        .await
        .unwrap();
    assert_eq!(events.len(), 2);
    assert_eq!(
        events[0].as_ref().unwrap(),
        &TurnEvent::Delta(String::from("hi"))
    );
    assert_eq!(
        events[1].as_ref().unwrap_err(),
        &TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("boom"),
        },
    );
}

#[tokio::test]
async fn approved_confirm_round_trips_over_the_open_request_stream() {
    let events = run_confirm_turn(true).await.unwrap();
    assert_eq!(
        events,
        vec![
            TurnEvent::ConfirmRequest {
                confirm_id: String::from("confirm-7"),
                tool_name: String::from("send_email"),
                arguments_json: String::from("{\"to\":\"x@y\"}"),
                reason: String::from("outbound and irreversible"),
            },
            TurnEvent::Delta(String::from("verdict:true")),
            TurnEvent::Complete {
                turn_id: String::from("turn-confirm"),
            },
        ],
    );
}

#[tokio::test]
async fn denied_confirm_round_trips_over_the_open_request_stream() {
    let events = run_confirm_turn(false).await.unwrap();
    assert_eq!(
        events,
        vec![
            TurnEvent::ConfirmRequest {
                confirm_id: String::from("confirm-7"),
                tool_name: String::from("send_email"),
                arguments_json: String::from("{\"to\":\"x@y\"}"),
                reason: String::from("outbound and irreversible"),
            },
            TurnEvent::Delta(String::from("verdict:false")),
            TurnEvent::Complete {
                turn_id: String::from("turn-confirm"),
            },
        ],
    );
}

#[tokio::test]
async fn an_unanswered_confirm_resolves_mid_turn_without_ending_it() {
    let events = run_turn(Turn::ConfirmTimeout, "s", "send it", tokio_stream::empty())
        .await
        .unwrap();
    let events: Vec<TurnEvent> = events.into_iter().map(Result::unwrap).collect();
    assert_eq!(
        events,
        vec![
            TurnEvent::ConfirmRequest {
                confirm_id: String::from("confirm-9"),
                tool_name: String::from("send_email"),
                arguments_json: String::from("{\"to\":\"x@y\"}"),
                reason: String::from("outbound and irreversible"),
            },
            TurnEvent::ConfirmResolved {
                confirm_id: String::from("confirm-9"),
                outcome: String::from("timeout"),
            },
            TurnEvent::Delta(String::from("not sent")),
            TurnEvent::Complete {
                turn_id: String::from("turn-timeout"),
            },
        ],
    );
}

#[tokio::test]
async fn empty_decisions_stream_still_half_closes_and_the_turn_completes() {
    let events = run_turn(Turn::HalfClose, "s", "hi", tokio_stream::empty())
        .await
        .unwrap();
    let events: Vec<TurnEvent> = events.into_iter().map(Result::unwrap).collect();
    assert_eq!(
        events,
        vec![
            TurnEvent::Delta(String::from("half-closed")),
            TurnEvent::Complete {
                turn_id: String::from("turn-halfclose"),
            },
        ],
    );
}

#[tokio::test]
async fn attached_images_reach_the_user_turn_in_order_without_a_capture_source() {
    let addr = spawn_turn(Turn::Images).await.unwrap();
    let client = BrainRpcClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let images = vec![
        AttachedImage {
            data: vec![0x89, 0x50],
            mime_type: String::from("image/png"),
            width: 1600,
            height: 900,
        },
        AttachedImage {
            data: vec![0xff, 0xd8, 0xff],
            mime_type: String::from("image/jpeg"),
            width: 30,
            height: 40,
        },
    ];
    let stream = client.converse("sess-i", "what is this", images, tokio_stream::empty());
    tokio::pin!(stream);
    let mut events = Vec::new();
    while let Some(item) = stream.next().await {
        events.push(item.unwrap());
    }
    assert_eq!(
        events,
        vec![
            TurnEvent::Delta(String::from("image/png 1600x900 [137, 80] source 0x0 at 0")),
            TurnEvent::Delta(String::from(
                "image/jpeg 30x40 [255, 216, 255] source 0x0 at 0"
            )),
            TurnEvent::Complete {
                turn_id: String::from("turn-images"),
            },
        ]
    );
}
