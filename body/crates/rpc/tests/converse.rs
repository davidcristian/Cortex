//! Contract tests for `BrainSeamClient::converse`: a scripted in-process fake
//! serves the generated `BrainService.Converse` on loopback (CI-safe port 0)
//! and the adapter's `ServerEvent`→`TurnEvent` mapping is asserted end to end.
//!
//! Coverage of every branch in `crate::converse`: the happy path (which also
//! proves the one-turn request is transmitted, because the fake echoes the received
//! text and session id), a brain-reported `SeamError` (→ `Failed`), an empty
//! `ServerEvent` and a stream that ends before `TurnComplete` (→ `Protocol`),
//! the `Converse` call itself failing (→ `Rpc`), a status raised mid-stream
//! (→ `Rpc`), and the confirm round-trip (ADR-0022): a mid-turn
//! `ConfirmRequest` (→ non-terminal `TurnEvent::ConfirmRequest`) answered by a
//! decision the client relays as a `confirm_response` on the still-open
//! request stream (approve and deny), a `ConfirmResolved` for the confirm the
//! caller never answered (→ non-terminal `TurnEvent::ConfirmResolved`), plus the
//! half-close of an ended/empty decisions stream (the pre-8.8 one-shot shape).
//! The `Connection` mapping is shared with `health` and covered in
//! `tests/client.rs`.

use std::net::SocketAddr;
use std::pin::Pin;

use body_core::{BrainTransport, ConfirmDecision, TransportError, TurnEvent};
use body_rpc::BrainSeamClient;
use body_rpc::generated::brain_service_server::{BrainService, BrainServiceServer};
use body_rpc::generated::{
    AckReminderReply, AckReminderRequest, ClientEvent, ConfirmRequest, ConfirmResolved,
    GetSessionMessagesReply, GetSessionMessagesRequest, HealthReply, HealthRequest,
    ListDueRemindersReply, ListDueRemindersRequest, ListSessionsReply, ListSessionsRequest,
    RenameSessionReply, RenameSessionRequest, SeamError, ServerEvent, StatusUpdate, TextDelta,
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
    /// Read the user turn, emit a `ConfirmRequest`, then read the next inbound
    /// client event and assert it is the matching `ConfirmResponse` with this
    /// `approved` value, proving the client kept its sender open and relayed
    /// the caller's decision (ADR-0022). Then echo the verdict and complete.
    Confirm { approved: bool },
    /// Read the user turn, emit a `ConfirmRequest`, then end the wait without any
    /// answer, as the brain's confirm timeout does: `ConfirmResolved{timeout}`,
    /// the declined turn's reply, and `TurnComplete` (ADR-0022 addendum).
    ConfirmTimeout,
    /// Read the user turn, then assert the inbound stream half-closes (ends)
    /// in the pre-8.8 shape when the caller's decisions stream is empty, then
    /// complete normally.
    HalfClose,
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

/// Reads the next inbound `ClientEvent` and returns its `(session_id, event)`
/// oneof, or `None` when the client has half-closed. This is the generalized inbound
/// reader every script builds on (the confirm scripts read past the user turn).
async fn read_client_event(
    inbound: &mut Streaming<ClientEvent>,
) -> Result<Option<(String, client_event::Event)>, Status> {
    Ok(inbound
        .message()
        .await?
        .and_then(|event| event.event.map(|inner| (event.session_id, inner))))
}

/// Reads one inbound `ClientEvent` and returns its `(session_id, text)`,
/// or placeholders if it is missing or not a user turn.
async fn read_user_turn(inbound: &mut Streaming<ClientEvent>) -> Result<(String, String), Status> {
    match read_client_event(inbound).await? {
        Some((session_id, client_event::Event::UserTurn(turn))) => Ok((session_id, turn.text)),
        _ => Ok((String::from("<none>"), String::from("<none>"))),
    }
}

/// The confirm round-trip response stream (ADR-0022): emit a `ConfirmRequest`,
/// then read the client's next inbound event and assert it is the matching
/// `ConfirmResponse{confirm_id, approved}` on the same session, which proves the
/// client kept its request sender open past the user turn and relayed the
/// caller's decision. Any mismatch fails the stream with an `internal` status
/// the test surfaces as an unexpected `Rpc` error.
fn confirm_script(
    mut inbound: Streaming<ClientEvent>,
    session_id: String,
    expect_approved: bool,
) -> impl Stream<Item = Result<ServerEvent, Status>> + Send {
    async_stream::stream! {
        yield Ok(ServerEvent {
            event: Some(server_event::Event::ConfirmRequest(ConfirmRequest {
                confirm_id: String::from("confirm-7"),
                tool_name: String::from("send_email"),
                arguments_json: String::from("{\"to\":\"x@y\"}"),
                reason: String::from("outbound and irreversible"),
            })),
        });
        match read_client_event(&mut inbound).await {
            Ok(Some((sid, client_event::Event::ConfirmResponse(response))))
                if sid == session_id
                    && response.confirm_id == "confirm-7"
                    && response.approved == expect_approved =>
            {
                yield Ok(delta(&format!("verdict:{}", response.approved)));
                yield Ok(ServerEvent {
                    event: Some(server_event::Event::TurnComplete(TurnComplete {
                        turn_id: String::from("turn-confirm"),
                    })),
                });
            }
            other => {
                yield Err(Status::internal(format!(
                    "expected the echoed confirm response, got {other:?}"
                )));
            }
        }
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
        if let Script::Confirm { approved } = self.script {
            let (session_id, _text) = read_user_turn(&mut inbound).await?;
            return Ok(Response::new(Box::pin(confirm_script(
                inbound, session_id, approved,
            ))));
        }
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
            Script::ConfirmTimeout => {
                let _ = read_user_turn(&mut inbound).await?;
                vec![
                    Ok(ServerEvent {
                        event: Some(server_event::Event::ConfirmRequest(ConfirmRequest {
                            confirm_id: String::from("confirm-9"),
                            tool_name: String::from("send_email"),
                            arguments_json: String::from("{\"to\":\"x@y\"}"),
                            reason: String::from("outbound and irreversible"),
                        })),
                    }),
                    Ok(ServerEvent {
                        event: Some(server_event::Event::ConfirmResolved(ConfirmResolved {
                            confirm_id: String::from("confirm-9"),
                            outcome: String::from("timeout"),
                        })),
                    }),
                    Ok(delta("not sent")),
                    Ok(ServerEvent {
                        event: Some(server_event::Event::TurnComplete(TurnComplete {
                            turn_id: String::from("turn-timeout"),
                        })),
                    }),
                ]
            }
            Script::HalfClose => {
                let _ = read_user_turn(&mut inbound).await?;
                match read_client_event(&mut inbound).await? {
                    None => vec![
                        Ok(delta("half-closed")),
                        Ok(ServerEvent {
                            event: Some(server_event::Event::TurnComplete(TurnComplete {
                                turn_id: String::from("turn-halfclose"),
                            })),
                        }),
                    ],
                    Some(event) => vec![Err(Status::internal(format!(
                        "expected the half-close after the user turn, got {event:?}"
                    )))],
                }
            }
            Script::RejectCall | Script::Confirm { .. } => unreachable!("handled above"),
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

    // The session-read RPCs are unused by these converse tests; they exist only to
    // satisfy the server trait (their own mapping is covered in tests/client.rs).
    async fn list_sessions(
        &self,
        _request: Request<ListSessionsRequest>,
    ) -> Result<Response<ListSessionsReply>, Status> {
        Err(Status::unimplemented("not exercised here"))
    }

    async fn get_session_messages(
        &self,
        _request: Request<GetSessionMessagesRequest>,
    ) -> Result<Response<GetSessionMessagesReply>, Status> {
        Err(Status::unimplemented("not exercised here"))
    }

    async fn list_due_reminders(
        &self,
        _request: Request<ListDueRemindersRequest>,
    ) -> Result<Response<ListDueRemindersReply>, Status> {
        Err(Status::unimplemented("not exercised here"))
    }

    async fn ack_reminder(
        &self,
        _request: Request<AckReminderRequest>,
    ) -> Result<Response<AckReminderReply>, Status> {
        Err(Status::unimplemented("not exercised here"))
    }

    async fn rename_session(
        &self,
        _request: Request<RenameSessionRequest>,
    ) -> Result<Response<RenameSessionReply>, Status> {
        Err(Status::unimplemented("not exercised here"))
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
/// `decisions` is the caller's confirm-answer stream (ADR-0022); the legacy
/// scripts pass an empty one (immediate half-close, the pre-8.8 shape).
/// Errors propagate (via `?`) so the `.unwrap()` stays in each `#[test]` body,
/// where clippy allows it, rather than in this shared helper.
async fn run_turn(
    script: Script,
    session_id: &str,
    text: &str,
    decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
) -> Result<Vec<Result<TurnEvent, TransportError>>, Box<dyn std::error::Error>> {
    let addr = spawn_fake_brain(script).await?;
    let client = BrainSeamClient::connect(&format!("http://{addr}")).await?;
    let stream = client.converse(session_id, text, decisions);
    tokio::pin!(stream);
    let mut out = Vec::new();
    while let Some(item) = stream.next().await {
        out.push(item);
    }
    Ok(out)
}

/// Runs one `Script::Confirm` turn the way the overlay would: the decision is
/// sent *in reaction to* the streamed `ConfirmRequest` over a channel whose
/// sender the caller holds open. It is never pre-scripted. Proves the adapter keeps
/// polling the outbound stream mid-turn (no deadlock between "brain awaits the
/// response" and "client only sends at call time").
async fn run_confirm_turn(approved: bool) -> Result<Vec<TurnEvent>, Box<dyn std::error::Error>> {
    let addr = spawn_fake_brain(Script::Confirm { approved }).await?;
    let client = BrainSeamClient::connect(&format!("http://{addr}")).await?;
    let (sender, receiver) = tokio::sync::mpsc::unbounded_channel();
    let decisions = tokio_stream::wrappers::UnboundedReceiverStream::new(receiver);
    let stream = client.converse("sess-c", "send it", decisions);
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
    let events = run_turn(Script::Echo, "sess-42", "ping", tokio_stream::empty())
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
    let events = run_turn(Script::PartialThenError, "s", "hi", tokio_stream::empty())
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
    let events = run_turn(Script::EmptyEvent, "s", "hi", tokio_stream::empty())
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
    let events = run_turn(Script::EarlyClose, "s", "hi", tokio_stream::empty())
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
    let events = run_turn(Script::RejectCall, "s", "hi", tokio_stream::empty())
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
    let events = run_turn(Script::MidStreamError, "s", "hi", tokio_stream::empty())
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
    // The fake asserts the wire shape (echoed confirm_id + approved=true on
    // the same session) before completing. A mismatch would surface as an
    // unexpected Rpc error below instead of this exact event vector.
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
    // The overlay's timeout case (ADR-0022 addendum): the brain answers for the user and
    // says so, so the caller can close the card. The resolution is non-terminal, which is
    // what this vector proves: the turn's reply and TurnComplete still arrive after it.
    let events = run_turn(
        Script::ConfirmTimeout,
        "s",
        "send it",
        tokio_stream::empty(),
    )
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
    // The pre-8.8 one-shot shape: with no decisions the request stream ends
    // right after the user turn; the fake proves the half-close reached it
    // (an extra inbound event would fail the turn with an Rpc error).
    let events = run_turn(Script::HalfClose, "s", "hi", tokio_stream::empty())
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
