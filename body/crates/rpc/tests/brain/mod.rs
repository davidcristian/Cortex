//! The one scripted `BrainService` the rpc tests serve on loopback (port 0, 127.0.0.1 only).
#![allow(
    dead_code,
    reason = "each test binary builds only the scripts it needs"
)]

use std::net::SocketAddr;
use std::pin::Pin;
use std::sync::{Arc, Mutex};

use body_contract::transport::Held;
use body_core::RpcHealth;
use body_rpc::generated::brain_service_server::{BrainService, BrainServiceServer};
use body_rpc::generated::{
    AckReminderReply, AckReminderRequest, ClientEvent, ConfirmRequest, ConfirmResolved,
    DeleteSessionReply, DeleteSessionRequest, DueReminder as PbDueReminder, GetPreferencesReply,
    GetPreferencesRequest, GetSessionMessagesReply, GetSessionMessagesRequest, HealthNote,
    HealthReply, HealthRequest, Heartbeat, ListDueRemindersReply, ListDueRemindersRequest,
    ListSessionsReply, ListSessionsRequest, Preference, RenameSessionReply, RenameSessionRequest,
    SeamError, ServerEvent, SessionMessage as PbSessionMessage, SessionSummary as PbSessionSummary,
    SetPreferenceReply, SetPreferenceRequest, SetSessionHoistedReply, SetSessionHoistedRequest,
    StatusUpdate, TextDelta, ToolActivity, ToolOutcome, TurnComplete, client_event, server_event,
};
use tokio::net::TcpListener;
use tokio_stream::Stream;
use tokio_stream::wrappers::TcpListenerStream;
use tonic::transport::Server;
use tonic::{Request, Response, Status, Streaming};

/// What the scripted fake brain answers to `Health`.
#[derive(Clone, Copy)]
pub enum Script {
    /// `Health` succeeds with `ready = true` and a detail string.
    Ready,
    /// `Health` fails with a gRPC `Internal` status.
    Failing,
    /// `Health` fails `Unavailable` with the message `store down`.
    Unavailable,
    /// `Health` never answers: the connection is accepted and the call hangs forever.
    Hanging,
    /// `Health` fails `DEADLINE_EXCEEDED`: the brain gave up on the call itself, which is what the
    /// announced `grpc-timeout` invites it to do.
    Expired,
}

/// What the scripted fake brain streams back for a `Converse` turn.
#[derive(Clone, Copy)]
pub enum Turn {
    /// Read the user turn and echo its text and session id, then a tool activity, a status update,
    /// and `TurnComplete`.
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
    /// Read the user turn, emit a `ConfirmRequest`, then read the next inbound client event and
    /// assert it is the matching `ConfirmResponse` with this `approved` value, which shows the
    /// client kept its sender open and relayed the caller's decision.
    Confirm { approved: bool },
    /// Read the user turn, emit a `ConfirmRequest`, then end the wait without any answer, as the
    /// brain's confirm timeout does: `ConfirmResolved{timeout}`, the declined turn's reply, and
    /// `TurnComplete`.
    ConfirmTimeout,
    /// Read the user turn, then assert the inbound stream half-closes when the caller's decisions
    /// stream is empty, which is the shape that predates confirms, then complete normally.
    HalfClose,
    /// Read the user turn and describe each attached image in one delta, then complete.
    Images,
}

/// A scripted fake implementing the generated `BrainService` server trait.
pub struct FakeBrain {
    pub script: Script,
    pub turn: Turn,
    /// The health `Script::Ready` answers and the chats the session reads answer from.
    pub held: Held,
    pub expected_token: Option<&'static str>,
    /// When set, the read-only session RPCs fail `Unavailable` (a store-down abort); otherwise they
    /// answer from `held`.
    pub sessions_fail: bool,
    /// The same for the reminder RPCs: a `ScheduleStoreError` aborts `Unavailable`.
    pub reminders_fail: bool,
    /// Records each `RenameSession` write `(session_id, title)` the fake received, so a test can
    /// prove both fields crossed the wire (the reply is a bare ack).
    pub renames: Arc<Mutex<Vec<(String, String)>>>,
    /// Records each `DeleteSession` write's `session_id`, so a test can prove the id crossed the
    /// wire (the reply is a bare ack).
    pub deletes: Arc<Mutex<Vec<String>>>,
    /// Records each `SetSessionHoisted` write `(session_id, hoisted)`, so a test can prove both
    /// fields crossed the wire (the reply is a bare ack).
    pub hoists: Arc<Mutex<Vec<(String, bool)>>>,
    /// Records each `SetPreference` write `(key, value)`, so a test can prove both fields crossed
    /// the wire, the empty clearing value included (the reply is a bare ack).
    pub preference_writes: Arc<Mutex<Vec<(String, String)>>>,
    /// Records the `grpc-timeout` metadata of every call the fake serves, `None` when a call
    /// sent none.
    pub timeouts: Arc<Mutex<Vec<Option<String>>>>,
}

impl FakeBrain {
    pub fn new(script: Script) -> Self {
        Self {
            script,
            turn: Turn::RejectCall,
            held: Held {
                health: RpcHealth {
                    ready: true,
                    detail: String::from("fake brain ready"),
                    notes: vec![String::from("first"), String::from("second")],
                },
                chats: Vec::new(),
            },
            expected_token: None,
            sessions_fail: false,
            reminders_fail: false,
            renames: Arc::new(Mutex::new(Vec::new())),
            deletes: Arc::new(Mutex::new(Vec::new())),
            hoists: Arc::new(Mutex::new(Vec::new())),
            preference_writes: Arc::new(Mutex::new(Vec::new())),
            timeouts: Arc::new(Mutex::new(Vec::new())),
        }
    }

    /// Records what `request` announced as its deadline, before answering it.
    fn record_timeout<T>(&self, request: &Request<T>) {
        let announced = request
            .metadata()
            .get("grpc-timeout")
            .map(|value| String::from(value.to_str().unwrap_or("not ascii")));
        self.timeouts
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(announced);
    }
}

fn delta(text: &str) -> ServerEvent {
    ServerEvent {
        event: Some(server_event::Event::TextDelta(TextDelta {
            text: String::from(text),
        })),
    }
}

/// Reads the next inbound `ClientEvent` and returns its `(session_id, event)` oneof, or `None` when
/// the client has half-closed.
async fn read_client_event(
    inbound: &mut Streaming<ClientEvent>,
) -> Result<Option<(String, client_event::Event)>, Status> {
    Ok(inbound
        .message()
        .await?
        .and_then(|event| event.event.map(|inner| (event.session_id, inner))))
}

/// Reads one inbound `ClientEvent` and returns its `(session_id, text)`, or placeholders if it is
/// missing or not a user turn.
async fn read_user_turn(inbound: &mut Streaming<ClientEvent>) -> Result<(String, String), Status> {
    match read_client_event(inbound).await? {
        Some((session_id, client_event::Event::UserTurn(turn))) => Ok((session_id, turn.text)),
        _ => Ok((String::from("<none>"), String::from("<none>"))),
    }
}

/// One delta per image the user turn has, naming every field the fake received, then completion.
async fn describe_images(
    inbound: &mut Streaming<ClientEvent>,
) -> Result<Vec<Result<ServerEvent, Status>>, Status> {
    let Some((_, client_event::Event::UserTurn(turn))) = read_client_event(inbound).await? else {
        return Ok(vec![Err(Status::internal("expected the user turn"))]);
    };
    let described = turn.images.iter().map(|image| {
        Ok(delta(&format!(
            "{} {}x{} {:?} source {}x{} at {}",
            image.mime_type,
            image.width,
            image.height,
            image.data,
            image.source_width,
            image.source_height,
            image.captured_at_unix_ms
        )))
    });
    let complete = Ok(ServerEvent {
        event: Some(server_event::Event::TurnComplete(TurnComplete {
            turn_id: String::from("turn-images"),
        })),
    });
    Ok(described.chain([complete]).collect())
}

/// The confirm round trip: emit a `ConfirmRequest`, then check that the client's next inbound
/// event is the matching `ConfirmResponse` on the same session, which shows it kept its request
/// sender open past the user turn.
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

/// A heartbeat whose turn waits on a tool call.
fn calling_heartbeat() -> ServerEvent {
    ServerEvent {
        event: Some(server_event::Event::Heartbeat(Heartbeat {
            wait: String::from("calling"),
            detail: String::from("waiting for a tool to finish"),
        })),
    }
}

#[tonic::async_trait]
impl BrainService for FakeBrain {
    type ConverseStream = Pin<Box<dyn Stream<Item = Result<ServerEvent, Status>> + Send>>;

    async fn converse(
        &self,
        request: Request<Streaming<ClientEvent>>,
    ) -> Result<Response<Self::ConverseStream>, Status> {
        self.record_timeout(&request);
        if let Turn::RejectCall = self.turn {
            return Err(Status::internal("cannot start turn"));
        }
        let mut inbound = request.into_inner();
        if let Turn::Confirm { approved } = self.turn {
            let (session_id, _text) = read_user_turn(&mut inbound).await?;
            return Ok(Response::new(Box::pin(confirm_script(
                inbound, session_id, approved,
            ))));
        }
        let events: Vec<Result<ServerEvent, Status>> = match self.turn {
            Turn::Echo => {
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
                        event: Some(server_event::Event::ToolOutcome(ToolOutcome {
                            tool_name: String::from("read_email"),
                            ok: false,
                        })),
                    }),
                    Ok(calling_heartbeat()),
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
            Turn::PartialThenError => vec![
                Ok(delta("partial")),
                Ok(ServerEvent {
                    event: Some(server_event::Event::Error(SeamError {
                        code: String::from("overloaded"),
                        message: String::from("brain is busy"),
                    })),
                }),
            ],
            Turn::EmptyEvent => vec![Ok(ServerEvent { event: None })],
            Turn::EarlyClose => vec![Ok(delta("hi"))],
            Turn::MidStreamError => vec![Ok(delta("hi")), Err(Status::internal("boom"))],
            Turn::ConfirmTimeout => {
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
            Turn::HalfClose => {
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
            Turn::Images => describe_images(&mut inbound).await?,
            Turn::RejectCall | Turn::Confirm { .. } => unreachable!("handled above"),
        };
        Ok(Response::new(Box::pin(tokio_stream::iter(events))))
    }

    async fn health(
        &self,
        request: Request<HealthRequest>,
    ) -> Result<Response<HealthReply>, Status> {
        self.record_timeout(&request);
        if let Some(expected) = self.expected_token {
            match request.metadata().get("x-cortex-seam-token") {
                Some(value) if *value == *expected => {}
                _ => return Err(Status::unauthenticated("invalid or missing token")),
            }
        }
        match self.script {
            Script::Ready => Ok(Response::new(HealthReply {
                ready: self.held.health.ready,
                detail: self.held.health.detail.clone(),
                notes: (self.held.health.notes.iter())
                    .map(|text| HealthNote { text: text.clone() })
                    .collect(),
            })),
            Script::Failing => Err(Status::internal("scripted failure")),
            Script::Unavailable => Err(Status::unavailable("store down")),
            Script::Hanging => std::future::pending().await,
            Script::Expired => Err(Status::deadline_exceeded("the brain stopped working on it")),
        }
    }

    async fn list_sessions(
        &self,
        request: Request<ListSessionsRequest>,
    ) -> Result<Response<ListSessionsReply>, Status> {
        self.record_timeout(&request);
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        let limit = usize::try_from(request.into_inner().limit).unwrap_or(0);
        let rows = self.held.chats.iter().take(limit);
        Ok(Response::new(ListSessionsReply {
            sessions: rows
                .map(|chat| PbSessionSummary {
                    session_id: chat.summary.session_id.clone(),
                    title: chat.summary.title.clone(),
                    preview: chat.summary.preview.clone(),
                    last_activity_unix_ms: chat.summary.last_activity_unix_ms,
                    hoisted: chat.summary.hoisted,
                })
                .collect(),
        }))
    }

    async fn get_session_messages(
        &self,
        request: Request<GetSessionMessagesRequest>,
    ) -> Result<Response<GetSessionMessagesReply>, Status> {
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        let session_id = request.into_inner().session_id;
        let chats = self.held.chats.iter();
        let asked = chats.filter(|chat| chat.summary.session_id == session_id);
        Ok(Response::new(GetSessionMessagesReply {
            messages: asked
                .flat_map(|chat| chat.messages.iter())
                .map(|message| PbSessionMessage {
                    role: message.role.clone(),
                    text: message.text.clone(),
                    turn_id: message.turn_id.clone(),
                    at_unix_ms: message.at_unix_ms,
                })
                .collect(),
        }))
    }

    async fn list_due_reminders(
        &self,
        _request: Request<ListDueRemindersRequest>,
    ) -> Result<Response<ListDueRemindersReply>, Status> {
        if self.reminders_fail {
            return Err(Status::unavailable("schedule store down"));
        }
        Ok(Response::new(ListDueRemindersReply {
            reminders: vec![
                PbDueReminder {
                    reminder_id: String::from("r1"),
                    text: String::from("stand up"),
                    fired_at_unix_ms: 2000,
                    recurring: true,
                    tainted: false,
                    session_id: String::from("chat-1"),
                },
                PbDueReminder {
                    reminder_id: String::from("r2"),
                    text: String::from("read the flagged mail"),
                    fired_at_unix_ms: 3000,
                    recurring: false,
                    tainted: true,
                    session_id: String::new(),
                },
            ],
        }))
    }

    async fn ack_reminder(
        &self,
        request: Request<AckReminderRequest>,
    ) -> Result<Response<AckReminderReply>, Status> {
        if self.reminders_fail {
            return Err(Status::unavailable("schedule store down"));
        }
        let request = request.into_inner();
        Ok(Response::new(AckReminderReply {
            acked: request.reminder_id == "r1" && request.fired_at_unix_ms == 2000,
        }))
    }

    async fn rename_session(
        &self,
        request: Request<RenameSessionRequest>,
    ) -> Result<Response<RenameSessionReply>, Status> {
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        let req = request.into_inner();
        self.renames
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push((req.session_id, req.title));
        Ok(Response::new(RenameSessionReply {}))
    }

    async fn delete_session(
        &self,
        request: Request<DeleteSessionRequest>,
    ) -> Result<Response<DeleteSessionReply>, Status> {
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        self.deletes
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(request.into_inner().session_id);
        Ok(Response::new(DeleteSessionReply {}))
    }

    async fn set_session_hoisted(
        &self,
        request: Request<SetSessionHoistedRequest>,
    ) -> Result<Response<SetSessionHoistedReply>, Status> {
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        let req = request.into_inner();
        self.hoists
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push((req.session_id, req.hoisted));
        Ok(Response::new(SetSessionHoistedReply {}))
    }

    async fn get_preferences(
        &self,
        _request: Request<GetPreferencesRequest>,
    ) -> Result<Response<GetPreferencesReply>, Status> {
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        Ok(Response::new(GetPreferencesReply {
            preferences: vec![
                Preference {
                    key: String::from("overlay.mark"),
                    value: String::from("foam"),
                },
                Preference {
                    key: String::from("overlay.theme"),
                    value: String::from("midnight"),
                },
            ],
        }))
    }

    async fn set_preference(
        &self,
        request: Request<SetPreferenceRequest>,
    ) -> Result<Response<SetPreferenceReply>, Status> {
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        let req = request.into_inner();
        self.preference_writes
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push((req.key, req.value));
        Ok(Response::new(SetPreferenceReply {}))
    }
}

/// Serves `fake` on an ephemeral loopback port; returns the bound address.
pub async fn spawn_fake_brain(fake: FakeBrain) -> Result<SocketAddr, std::io::Error> {
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    let incoming = TcpListenerStream::new(listener);
    tokio::spawn(async move {
        Server::builder()
            .add_service(BrainServiceServer::new(fake))
            .serve_with_incoming(incoming)
            .await
    });
    Ok(addr)
}
