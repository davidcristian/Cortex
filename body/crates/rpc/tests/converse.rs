//! Contract tests for `BrainSeamClient::converse`: a scripted in-process fake
//! serves the generated `BrainService.Converse` on loopback (CI-safe port 0)
//! and the adapter's `ServerEvent`→`TurnEvent` mapping is asserted end to end.
//!
//! Coverage of every branch in `crate::converse`: the happy path (which also
//! proves the one-turn request is transmitted, because the fake echoes the received
//! text and session id), a brain-reported `SeamError` (→ `Failed`), an empty
//! `ServerEvent` and a stream that ends before `TurnComplete` (→ `Protocol`),
//! the `Converse` call itself failing (→ `Rpc`), and a status raised mid-stream
//! (→ `Rpc`). The `Connection` mapping is shared with `health` and covered in
//! `tests/client.rs`.

use std::net::SocketAddr;
use std::pin::Pin;

use body_core::{BrainTransport, TransportError, TurnEvent};
use body_rpc::BrainSeamClient;
use body_rpc::generated::brain_service_server::{BrainService, BrainServiceServer};
use body_rpc::generated::{
    ClientEvent, HealthReply, HealthRequest, SeamError, ServerEvent, StatusUpdate, TextDelta,
    ToolActivity, TurnComplete, client_event, server_event,
};
use tokio::net::TcpListener;
use tokio_stream::wrappers::TcpListenerStream;
use tokio_stream::{Stream, StreamExt};
use tonic::transport::Server;
use tonic::{Request, Response, Status, Streaming};

/// What the scripted fake brain streams back for a `Converse` turn.
#[derive(Clone, Copy)]
enum Script {
    /// Read the user turn and echo its text + session id, then a tool-activity,
    /// a status update, and `TurnComplete`. This is the full happy path.
    Echo,
    /// One delta, then a brain-reported `SeamError` (terminal).
    PartialThenError,
    /// A single `ServerEvent` with no event set (malformed).
    EmptyEvent,
    /// One delta, then the stream ends with no `TurnComplete`.
    EarlyClose,
    /// The `Converse` call is rejected before any streaming.
    RejectCall,
    /// One delta, then a non-OK status raised mid-stream.
    MidStreamError,
}

/// A scripted fake implementing the generated `BrainService` server trait.
struct FakeBrain {
    script: Script,
}

fn delta(text: &str) -> ServerEvent {
    ServerEvent {
        event: Some(server_event::Event::TextDelta(TextDelta {
            text: String::from(text),
        })),
    }
}

/// Reads the single inbound `ClientEvent` and returns its `(session_id, text)`,
/// or placeholders if it is missing or not a user turn.
async fn read_user_turn(inbound: &mut Streaming<ClientEvent>) -> Result<(String, String), Status> {
    match inbound.message().await? {
        Some(ClientEvent {
            session_id,
            event: Some(client_event::Event::UserTurn(turn)),
        }) => Ok((session_id, turn.text)),
        _ => Ok((String::from("<none>"), String::from("<none>"))),
    }
}

#[tonic::async_trait]
impl BrainService for FakeBrain {
    type ConverseStream = Pin<Box<dyn Stream<Item = Result<ServerEvent, Status>> + Send>>;

    async fn converse(
        &self,
        request: Request<Streaming<ClientEvent>>,
    ) -> Result<Response<Self::ConverseStream>, Status> {
        if let Script::RejectCall = self.script {
            return Err(Status::internal("cannot start turn"));
        }
        let mut inbound = request.into_inner();
        let events: Vec<Result<ServerEvent, Status>> = match self.script {
            Script::Echo => {
                let (session_id, text) = read_user_turn(&mut inbound).await?;
                vec![
                    Ok(delta(&format!("echo:{text}"))),
                    Ok(delta(&format!("sid:{session_id}"))),
                    Ok(ServerEvent {
                        event: Some(server_event::Event::ToolActivity(ToolActivity {
                            tool_name: String::from("read_email"),
                            summary: String::from("reading inbox"),
                        })),
                    }),
                    Ok(ServerEvent {
                        event: Some(server_event::Event::Status(StatusUpdate {
                            state: String::from("model_loading"),
                            detail: String::from("swapping"),
                        })),
                    }),
                    Ok(ServerEvent {
                        event: Some(server_event::Event::TurnComplete(TurnComplete {
                            turn_id: String::from("turn-echo"),
                        })),
                    }),
                ]
            }
            Script::PartialThenError => vec![
                Ok(delta("partial")),
                Ok(ServerEvent {
                    event: Some(server_event::Event::Error(SeamError {
                        code: String::from("overloaded"),
                        message: String::from("brain is busy"),
                    })),
                }),
            ],
            Script::EmptyEvent => vec![Ok(ServerEvent { event: None })],
            Script::EarlyClose => vec![Ok(delta("hi"))],
            Script::MidStreamError => vec![Ok(delta("hi")), Err(Status::internal("boom"))],
            Script::RejectCall => unreachable!("handled above"),
        };
        Ok(Response::new(Box::pin(tokio_stream::iter(events))))
    }

    async fn health(
        &self,
        _request: Request<HealthRequest>,
    ) -> Result<Response<HealthReply>, Status> {
        Ok(Response::new(HealthReply {
            ready: true,
            detail: String::from("fake brain ready"),
        }))
    }
}

/// Serves a scripted fake on an ephemeral loopback port; returns the address.
async fn spawn_fake_brain(script: Script) -> Result<SocketAddr, std::io::Error> {
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    let incoming = TcpListenerStream::new(listener);
    tokio::spawn(async move {
        Server::builder()
            .add_service(BrainServiceServer::new(FakeBrain { script }))
            .serve_with_incoming(incoming)
            .await
    });
    Ok(addr)
}

/// Runs one turn through the transport port and collects every stream item.
/// Errors propagate (via `?`) so the `.unwrap()` stays in each `#[test]` body,
/// where clippy allows it, rather than in this shared helper.
async fn run_turn(
    script: Script,
    session_id: &str,
    text: &str,
) -> Result<Vec<Result<TurnEvent, TransportError>>, Box<dyn std::error::Error>> {
    let addr = spawn_fake_brain(script).await?;
    let client = BrainSeamClient::connect(&format!("http://{addr}")).await?;
    let stream = client.converse(session_id, text);
    tokio::pin!(stream);
    let mut out = Vec::new();
    while let Some(item) = stream.next().await {
        out.push(item);
    }
    Ok(out)
}

#[tokio::test]
async fn echo_turn_round_trips_every_event_kind() {
    let events = run_turn(Script::Echo, "sess-42", "ping").await.unwrap();
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
    let events = run_turn(Script::PartialThenError, "s", "hi").await.unwrap();
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
    let events = run_turn(Script::EmptyEvent, "s", "hi").await.unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(
        events[0].as_ref().unwrap_err(),
        &TransportError::Protocol(String::from("converse server event had no event set")),
    );
}

#[tokio::test]
async fn stream_ending_before_completion_maps_to_protocol_error() {
    let events = run_turn(Script::EarlyClose, "s", "hi").await.unwrap();
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
    let events = run_turn(Script::RejectCall, "s", "hi").await.unwrap();
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
    let events = run_turn(Script::MidStreamError, "s", "hi").await.unwrap();
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
