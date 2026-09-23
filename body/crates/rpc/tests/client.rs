//! Contract tests for `BrainSeamClient`: a scripted in-process fake serves the generated
//! `BrainService` on loopback (port 0, with no network beyond 127.0.0.1, so CI can run it) and the
//! adapter's mappings are asserted end to end.

use std::net::SocketAddr;
use std::pin::Pin;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use body_core::{
    BrainTransport, DueReminder, LinkState, LinkStatus, RetryPlan, RetryingTransport, SeamHealth,
    SeamMethod, SessionMessage, SessionSummary, Sleeper, TransportError, is_transient, probe_link,
};
use body_rpc::BrainSeamClient;
use body_rpc::generated::brain_service_client::BrainServiceClient;
use body_rpc::generated::brain_service_server::{BrainService, BrainServiceServer};
use body_rpc::generated::{
    AckReminderReply, AckReminderRequest, ClientEvent, DeleteSessionReply, DeleteSessionRequest,
    DueReminder as PbDueReminder, GetPreferencesReply, GetPreferencesRequest,
    GetSessionMessagesReply, GetSessionMessagesRequest, HealthReply, HealthRequest,
    ListDueRemindersReply, ListDueRemindersRequest, ListSessionsReply, ListSessionsRequest,
    Preference, RenameSessionReply, RenameSessionRequest, ServerEvent,
    SessionMessage as PbSessionMessage, SessionSummary as PbSessionSummary, SetPreferenceReply,
    SetPreferenceRequest, SetSessionHoistedReply, SetSessionHoistedRequest,
};
use tokio::net::TcpListener;
use tokio::sync::oneshot;
use tokio::task::JoinHandle;
use tokio_stream::wrappers::TcpListenerStream;
use tokio_stream::{Stream, StreamExt};
use tonic::transport::Server;
use tonic::{Request, Response, Status, Streaming};

/// What the scripted fake brain answers to `Health`.
#[derive(Clone, Copy)]
enum Script {
    /// `Health` succeeds with `ready = true` and a detail string.
    Ready,
    /// `Health` fails with a gRPC `Internal` status.
    Failing,
    /// `Health` never answers: the connection is accepted and the call hangs forever.
    Hanging,
    /// `Health` fails `DEADLINE_EXCEEDED`: the brain gave up on the call itself, which is what the
    /// announced `grpc-timeout` invites it to do.
    Expired,
}

/// A scripted fake implementing the generated `BrainService` server trait.
struct FakeBrain {
    script: Script,
    expected_token: Option<&'static str>,
    /// When set, the read-only session RPCs fail `Unavailable` (a store-down abort); otherwise they
    /// answer with canned rows.
    sessions_fail: bool,
    /// The same for the reminder RPCs: a `ScheduleStoreError` aborts `Unavailable`.
    reminders_fail: bool,
    /// Records each `RenameSession` write `(session_id, title)` the fake received, so a test can
    /// prove both fields crossed the wire (the reply is a bare ack).
    renames: Arc<Mutex<Vec<(String, String)>>>,
    /// Records each `DeleteSession` write's `session_id`, so a test can prove the id crossed the
    /// wire (the reply is a bare ack).
    deletes: Arc<Mutex<Vec<String>>>,
    /// Records each `SetSessionHoisted` write `(session_id, hoisted)`, so a test can prove both
    /// fields crossed the wire (the reply is a bare ack).
    hoists: Arc<Mutex<Vec<(String, bool)>>>,
    /// Records each `SetPreference` write `(key, value)`, so a test can prove both fields crossed
    /// the wire, the empty clearing value included (the reply is a bare ack).
    preference_writes: Arc<Mutex<Vec<(String, String)>>>,
    /// Records the `grpc-timeout` metadata of every call the fake serves, `None` when a call
    /// sent none.
    timeouts: Arc<Mutex<Vec<Option<String>>>>,
}

impl FakeBrain {
    fn new(script: Script) -> Self {
        Self {
            script,
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

/// The `grpc-timeout` header read back as a duration, over the gRPC unit suffixes: hours,
/// minutes, seconds, milli-, micro- and nanoseconds.
fn announced_deadline(header: &str) -> Duration {
    let (value, unit) = header.split_at(header.len() - 1);
    let Ok(value) = value.parse::<u64>() else {
        panic!("a grpc-timeout value is digits, got: {header}");
    };
    match unit {
        "H" => Duration::from_secs(value * 3600),
        "M" => Duration::from_secs(value * 60),
        "S" => Duration::from_secs(value),
        "m" => Duration::from_millis(value),
        "u" => Duration::from_micros(value),
        "n" => Duration::from_nanos(value),
        other => panic!("unknown grpc-timeout unit: {other}"),
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
        Err(Status::unimplemented("converse lands in a later slice"))
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
                ready: true,
                detail: String::from("fake brain ready"),
            })),
            Script::Failing => Err(Status::internal("scripted failure")),
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
        let limit = request.into_inner().limit;
        Ok(Response::new(ListSessionsReply {
            sessions: vec![
                PbSessionSummary {
                    session_id: String::from("beta"),
                    title: format!("limit={limit}"),
                    preview: String::from("newest chat"),
                    last_activity_unix_ms: 2000,
                    hoisted: true,
                },
                PbSessionSummary {
                    session_id: String::from("alpha"),
                    title: String::from("older chat"),
                    preview: String::from("oldest chat"),
                    last_activity_unix_ms: 1000,
                    hoisted: false,
                },
            ],
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
        Ok(Response::new(GetSessionMessagesReply {
            messages: vec![
                PbSessionMessage {
                    role: String::from("user"),
                    text: session_id,
                    turn_id: String::from("t1"),
                    at_unix_ms: 1000,
                },
                PbSessionMessage {
                    role: String::from("assistant"),
                    text: String::from("hi there"),
                    turn_id: String::from("t1"),
                    at_unix_ms: 1500,
                },
            ],
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
async fn spawn_fake_brain(fake: FakeBrain) -> Result<SocketAddr, std::io::Error> {
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

/// Like [`spawn_fake_brain`], but with graceful shutdown wired to the returned sender; awaiting the
/// returned handle after firing it guarantees the listener is released and nothing serves on the
/// address anymore.
async fn spawn_stoppable_fake_brain(
    fake: FakeBrain,
) -> Result<
    (
        SocketAddr,
        oneshot::Sender<()>,
        JoinHandle<Result<(), tonic::transport::Error>>,
    ),
    std::io::Error,
> {
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    let incoming = TcpListenerStream::new(listener);
    let (shutdown, on_shutdown) = oneshot::channel::<()>();
    let server = tokio::spawn(async move {
        Server::builder()
            .add_service(BrainServiceServer::new(fake))
            .serve_with_incoming_shutdown(incoming, async {
                let _ = on_shutdown.await;
            })
            .await
    });
    Ok((addr, shutdown, server))
}

#[tokio::test]
async fn health_round_trips_through_the_transport_port() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let health = client.health().await.unwrap();
    assert_eq!(
        health,
        SeamHealth {
            ready: true,
            detail: String::from("fake brain ready"),
        }
    );
}

#[tokio::test]
async fn non_ok_grpc_status_maps_to_the_rpc_variant() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Failing))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let error = client.health().await.unwrap_err();
    assert_eq!(
        error,
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("scripted failure"),
        }
    );
}

#[tokio::test]
async fn connection_refused_maps_to_the_connection_variant() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    drop(listener);
    let error = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    assert!(
        message.contains("refused") || message.contains("os error"),
        "message should name the root cause, got: {message}"
    );
}

#[tokio::test]
async fn brain_death_after_connect_maps_to_the_connection_variant() {
    let (addr, shutdown, server) = spawn_stoppable_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert!(client.health().await.unwrap().ready);
    shutdown.send(()).unwrap();
    server.await.unwrap().unwrap();
    let error = client.health().await.unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    assert!(!message.is_empty());
}

#[tokio::test]
async fn invalid_address_maps_to_the_connection_variant() {
    let error = BrainSeamClient::connect("not a valid uri")
        .await
        .unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    assert!(!message.is_empty());
}

#[tokio::test]
async fn client_clones_share_the_connection_and_debug_formats() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let cloned = client.clone();
    assert!(cloned.health().await.unwrap().ready);
    assert!(format!("{client:?}").contains("BrainSeamClient"));
}

#[tokio::test]
async fn fake_brain_scripts_converse_as_unimplemented() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let mut raw = BrainServiceClient::connect(format!("http://{addr}"))
        .await
        .unwrap();
    let status = raw
        .converse(tokio_stream::iter(Vec::<ClientEvent>::new()))
        .await
        .unwrap_err();
    assert_eq!(status.code(), tonic::Code::Unimplemented);
    assert_eq!(status.message(), "converse lands in a later slice");
}

#[tokio::test]
async fn list_sessions_maps_summaries_in_order() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let sessions = client.list_sessions(7).await.unwrap();
    assert_eq!(
        sessions,
        vec![
            SessionSummary {
                session_id: String::from("beta"),
                title: String::from("limit=7"),
                preview: String::from("newest chat"),
                last_activity_unix_ms: 2000,
                hoisted: true,
            },
            SessionSummary {
                session_id: String::from("alpha"),
                title: String::from("older chat"),
                preview: String::from("oldest chat"),
                last_activity_unix_ms: 1000,
                hoisted: false,
            },
        ]
    );
}

#[tokio::test]
async fn session_messages_maps_history_in_order() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let messages = client.session_messages("chat-9").await.unwrap();
    assert_eq!(
        messages,
        vec![
            SessionMessage {
                role: String::from("user"),
                text: String::from("chat-9"),
                turn_id: String::from("t1"),
                at_unix_ms: 1000,
            },
            SessionMessage {
                role: String::from("assistant"),
                text: String::from("hi there"),
                turn_id: String::from("t1"),
                at_unix_ms: 1500,
            },
        ]
    );
}

#[tokio::test]
async fn list_sessions_store_failure_maps_to_the_rpc_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.sessions_fail = true;
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert_eq!(
        client.list_sessions(10).await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }
    );
}

#[tokio::test]
async fn session_messages_store_failure_maps_to_the_rpc_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.sessions_fail = true;
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert_eq!(
        client.session_messages("s").await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }
    );
}

#[tokio::test]
async fn rename_session_writes_both_fields_across_the_wire() {
    let recorder = Arc::new(Mutex::new(Vec::new()));
    let mut fake = FakeBrain::new(Script::Ready);
    fake.renames = recorder.clone();
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    client
        .rename_session("chat-9", "Everything about cats")
        .await
        .unwrap();
    assert_eq!(
        *recorder.lock().unwrap(),
        vec![(
            String::from("chat-9"),
            String::from("Everything about cats"),
        )]
    );
    client.rename_session("chat-9", "").await.unwrap();
    assert_eq!(recorder.lock().unwrap().len(), 2);
    assert_eq!(recorder.lock().unwrap()[1].1, "");
}

#[tokio::test]
async fn rename_session_store_failure_maps_to_the_rpc_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.sessions_fail = true;
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert_eq!(
        client.rename_session("s", "x").await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }
    );
}

#[tokio::test]
async fn delete_session_writes_the_session_id_across_the_wire() {
    let recorder = Arc::new(Mutex::new(Vec::new()));
    let mut fake = FakeBrain::new(Script::Ready);
    fake.deletes = recorder.clone();
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    client.delete_session("chat-9").await.unwrap();
    assert_eq!(*recorder.lock().unwrap(), vec![String::from("chat-9")]);
}

#[tokio::test]
async fn delete_session_store_failure_maps_to_the_rpc_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.sessions_fail = true;
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert_eq!(
        client.delete_session("s").await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }
    );
}

#[tokio::test]
async fn set_session_hoisted_writes_both_fields_across_the_wire() {
    let recorder = Arc::new(Mutex::new(Vec::new()));
    let mut fake = FakeBrain::new(Script::Ready);
    fake.hoists = recorder.clone();
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    client.set_session_hoisted("chat-9", true).await.unwrap();
    assert_eq!(
        *recorder.lock().unwrap(),
        vec![(String::from("chat-9"), true)]
    );
    client.set_session_hoisted("chat-9", false).await.unwrap();
    assert_eq!(recorder.lock().unwrap()[1], (String::from("chat-9"), false));
}

#[tokio::test]
async fn set_session_hoisted_store_failure_maps_to_the_rpc_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.sessions_fail = true;
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert_eq!(
        client.set_session_hoisted("s", true).await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }
    );
}

#[tokio::test]
async fn list_due_reminders_maps_every_field_in_order() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let due = client.list_due_reminders().await.unwrap();
    assert_eq!(
        due,
        vec![
            DueReminder {
                reminder_id: String::from("r1"),
                text: String::from("stand up"),
                fired_at_unix_ms: 2000,
                recurring: true,
                tainted: false,
                session_id: String::from("chat-1"),
            },
            DueReminder {
                reminder_id: String::from("r2"),
                text: String::from("read the flagged mail"),
                fired_at_unix_ms: 3000,
                recurring: false,
                tainted: true,
                session_id: String::new(),
            },
        ]
    );
}

#[tokio::test]
async fn ack_reminder_reports_what_the_brain_cleared() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert!(client.ack_reminder("r1", 2000).await.unwrap());
    assert!(!client.ack_reminder("r-gone", 2000).await.unwrap());
    assert!(!client.ack_reminder("r1", 1999).await.unwrap());
}

#[tokio::test]
async fn reminder_store_failure_maps_to_the_rpc_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.reminders_fail = true;
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let unavailable = TransportError::Rpc {
        code: String::from("Unavailable"),
        message: String::from("schedule store down"),
    };
    assert_eq!(client.list_due_reminders().await.unwrap_err(), unavailable);
    assert_eq!(
        client.ack_reminder("r1", 2000).await.unwrap_err(),
        unavailable
    );
}

#[tokio::test]
async fn seam_token_round_trips_when_the_brain_requires_it() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.expected_token = Some("sekrit-seam-token");
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client =
        BrainSeamClient::connect_with_token(&format!("http://{addr}"), Some("sekrit-seam-token"))
            .await
            .unwrap();
    assert!(client.health().await.unwrap().ready);
    let debugged = format!("{client:?}");
    assert!(debugged.contains("BrainSeamClient"));
    assert!(!debugged.contains("sekrit-seam-token"));
}

#[tokio::test]
async fn missing_seam_token_maps_to_the_rpc_unauthenticated_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.expected_token = Some("sekrit-seam-token");
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert_eq!(
        client.health().await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unauthenticated"),
            message: String::from("invalid or missing token"),
        }
    );
}

#[tokio::test]
async fn wrong_seam_token_maps_to_the_rpc_unauthenticated_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.expected_token = Some("sekrit-seam-token");
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect_with_token(&format!("http://{addr}"), Some("guessed"))
        .await
        .unwrap();
    let error = client.health().await.unwrap_err();
    let TransportError::Rpc { code, .. } = error else {
        panic!("expected the rpc variant, got: {error:?}");
    };
    assert_eq!(code, "Unauthenticated");
}

#[tokio::test]
async fn non_ascii_seam_token_maps_to_the_connection_variant() {
    let error = BrainSeamClient::connect_with_token("http://127.0.0.1:1", Some("bad\ntoken"))
        .await
        .unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    assert!(
        message.contains("invalid token"),
        "message should name the token as the cause, got: {message}"
    );
}

#[tokio::test]
async fn lazy_connect_health_round_trips_over_a_lazy_channel() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect_lazy_with_token(&format!("http://{addr}"), None).unwrap();
    assert!(client.health().await.unwrap().ready);
}

#[tokio::test]
async fn lazy_connect_to_a_dead_endpoint_constructs_then_fails_on_the_first_call() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    drop(listener);
    let client = BrainSeamClient::connect_lazy_with_token(&format!("http://{addr}"), None).unwrap();
    let error = client.health().await.unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    assert!(!message.is_empty());
}

#[tokio::test]
async fn lazy_connect_invalid_address_maps_to_the_connection_variant() {
    let error = BrainSeamClient::connect_lazy_with_token("not a valid uri", None).unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    assert!(!message.is_empty());
}

#[tokio::test]
async fn lazy_connect_non_ascii_seam_token_maps_to_the_connection_variant() {
    let error = BrainSeamClient::connect_lazy_with_token("http://127.0.0.1:1", Some("bad\ntoken"))
        .unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    assert!(
        message.contains("invalid token"),
        "message should name the token as the cause, got: {message}"
    );
}

#[tokio::test]
async fn get_preferences_maps_every_pair_in_the_brains_order() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let record = client.get_preferences().await.unwrap();
    assert_eq!(
        record,
        vec![
            (String::from("overlay.mark"), String::from("foam")),
            (String::from("overlay.theme"), String::from("midnight")),
        ]
    );
}

#[tokio::test]
async fn set_preference_writes_both_fields_across_the_wire() {
    let recorder = Arc::new(Mutex::new(Vec::new()));
    let mut fake = FakeBrain::new(Script::Ready);
    fake.preference_writes = recorder.clone();
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    client.set_preference("overlay.mark", "ping").await.unwrap();
    client.set_preference("overlay.theme", "").await.unwrap();
    assert_eq!(
        *recorder.lock().unwrap(),
        vec![
            (String::from("overlay.mark"), String::from("ping")),
            (String::from("overlay.theme"), String::new()),
        ]
    );
}

#[tokio::test]
async fn preference_store_failures_map_to_the_rpc_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.sessions_fail = true;
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let read = client.get_preferences().await.unwrap_err();
    let write = client
        .set_preference("overlay.mark", "ping")
        .await
        .unwrap_err();
    for error in [read, write] {
        match error {
            TransportError::Rpc { code, message } => {
                assert_eq!(code, "Unavailable");
                assert!(message.contains("store down"));
            }
            other => panic!("expected an Rpc error, got {other:?}"),
        }
    }
}

/// The real `Sleeper` over `tokio::time`, as the shell composes it.
struct RealSleeper;

impl Sleeper for RealSleeper {
    fn sleep(&self, duration: Duration) -> impl std::future::Future<Output = ()> + Send {
        tokio::time::sleep(duration)
    }

    async fn bounded<F>(&self, deadline: Duration, call: F) -> Option<F::Output>
    where
        F: std::future::Future + Send,
        F::Output: Send,
    {
        tokio::time::timeout(deadline, call).await.ok()
    }
}

#[tokio::test]
async fn a_brain_that_accepts_the_call_and_never_answers_is_ended_by_the_deadline() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Hanging))
        .await
        .expect("fake brain should bind a loopback port");
    let client = BrainSeamClient::connect_lazy_with_token(&format!("http://{addr}"), None)
        .expect("a lazy client should build for a valid address");
    let deadline = Duration::from_millis(120);
    let transport = RetryingTransport::new(
        client,
        RealSleeper,
        RetryPlan {
            probe_deadline: deadline,
            ..RetryPlan::default()
        },
    );
    assert_eq!(
        transport.health().await.unwrap_err(),
        TransportError::Timeout { after: deadline }
    );
    let status = probe_link(&transport).await;
    assert_eq!(status.state, LinkState::Down);
    assert_eq!(status.detail, format!("no reply within {deadline:?}"));
}

#[tokio::test]
async fn tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Hanging))
        .await
        .expect("fake brain should bind a loopback port");
    let mut raw = BrainServiceClient::connect(format!("http://{addr}"))
        .await
        .expect("the fake brain accepts connections; it just never answers");
    let mut request = Request::new(HealthRequest {});
    request.set_timeout(Duration::from_millis(60));
    let status = raw
        .health(request)
        .await
        .expect_err("a brain that never answers cannot beat the timeout");

    assert_eq!(status.code(), tonic::Code::Cancelled);
    assert_eq!(status.message(), "Timeout expired");

    let error = body_rpc::status_to_error(&status);
    let TransportError::Connection(message) = &error else {
        panic!("tonic's own expiry should carry a transport source, got: {error:?}");
    };
    assert!(
        message.contains("Timeout expired"),
        "the folded chain should name the expiry, got: {message}"
    );
    assert_eq!(LinkStatus::from_error(&error).state, LinkState::Down);

    assert!(
        is_transient(&error),
        "a transport-armed deadline would be retried, which is why the bound lives in the core"
    );
}

#[tokio::test]
async fn an_announcing_client_tells_the_brain_each_call_s_own_deadline() {
    let fake = FakeBrain::new(Script::Ready);
    let announced = Arc::clone(&fake.timeouts);
    let addr = spawn_fake_brain(fake).await.unwrap();
    let plan = RetryPlan::default();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap()
        .announcing(plan);
    assert!(client.health().await.unwrap().ready);
    assert_eq!(client.list_sessions(2).await.unwrap().len(), 2);
    let recorded = announced
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
        .clone();
    let heard: Vec<Duration> = recorded
        .iter()
        .map(|header| announced_deadline(header.as_deref().expect("every call announced one")))
        .collect();
    assert_eq!(
        heard,
        vec![
            plan.announced_deadline_for(SeamMethod::Health).unwrap(),
            plan.announced_deadline_for(SeamMethod::ListSessions)
                .unwrap(),
        ]
    );
    for (heard, enforced) in heard.iter().zip([
        plan.deadline_for(SeamMethod::Health).unwrap(),
        plan.deadline_for(SeamMethod::ListSessions).unwrap(),
    ]) {
        assert!(
            *heard > enforced,
            "announced {heard:?} against {enforced:?}"
        );
    }
}

#[tokio::test]
async fn a_client_told_no_plan_announces_nothing_and_a_turn_never_does() {
    let fake = FakeBrain::new(Script::Ready);
    let announced = Arc::clone(&fake.timeouts);
    let addr = spawn_fake_brain(fake).await.unwrap();
    let silent = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert!(silent.health().await.unwrap().ready);
    let announcing = silent.clone().announcing(RetryPlan::default());
    let turn: Vec<_> = announcing
        .converse("s1", "hi", tokio_stream::empty())
        .collect()
        .await;
    assert_eq!(turn.len(), 1, "the fake refuses the turn with one status");
    assert_eq!(
        *announced
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner),
        vec![None, None]
    );
}

#[tokio::test]
async fn a_deadline_the_header_cannot_express_is_dropped_rather_than_sent() {
    let fake = FakeBrain::new(Script::Ready);
    let announced = Arc::clone(&fake.timeouts);
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap()
        .announcing(RetryPlan {
            call_deadline: Duration::from_secs(u64::MAX / 2),
            ..RetryPlan::default()
        });
    assert_eq!(client.list_sessions(1).await.unwrap().len(), 2);
    assert_eq!(
        *announced
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner),
        vec![None]
    );
}

#[tokio::test]
async fn an_announcement_off_the_millisecond_rung_is_dropped_and_one_on_it_is_sent() {
    let enforced = Duration::from_millis(100_000_749);
    let mut request = Request::new(());
    request.set_timeout(Duration::from_millis(100_000_999));
    let armed = announced_deadline(
        request
            .metadata()
            .get("grpc-timeout")
            .expect("set_timeout writes the header")
            .to_str()
            .expect("a grpc-timeout value is ascii"),
    );
    assert_eq!(armed, Duration::from_secs(100_000));
    assert_eq!(
        enforced
            .checked_sub(armed)
            .expect("tonic truncates, so the armed clock is the shorter one"),
        Duration::from_millis(749)
    );

    let fake = FakeBrain::new(Script::Ready);
    let heard = Arc::clone(&fake.timeouts);
    let addr = spawn_fake_brain(fake).await.unwrap();
    let over = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap()
        .announcing(RetryPlan {
            call_deadline: enforced,
            ..RetryPlan::default()
        });
    assert_eq!(over.list_sessions(1).await.unwrap().len(), 2);

    let plan = RetryPlan {
        call_deadline: Duration::from_millis(99_999_749),
        ..RetryPlan::default()
    };
    let under = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap()
        .announcing(plan);
    assert_eq!(under.list_sessions(1).await.unwrap().len(), 2);
    let recorded = heard
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
        .clone();
    let [dropped, sent] = recorded.as_slice() else {
        panic!("two calls were served, got: {recorded:?}");
    };
    assert_eq!(*dropped, None, "an announcement off the rung is not sent");
    let sent = announced_deadline(sent.as_deref().expect("the one on the rung is"));
    assert_eq!(
        sent,
        plan.announced_deadline_for(SeamMethod::ListSessions)
            .unwrap()
    );
    assert!(
        sent > plan.deadline_for(SeamMethod::ListSessions).unwrap(),
        "announced {sent:?}, which no longer stands above what the core enforces"
    );
}

#[tokio::test]
async fn the_core_s_own_bound_wins_the_race_the_announcement_starts() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Hanging))
        .await
        .expect("fake brain should bind a loopback port");
    let plan = RetryPlan {
        probe_deadline: Duration::from_millis(60),
        ..RetryPlan::default()
    };
    let client = BrainSeamClient::connect_lazy_with_token(&format!("http://{addr}"), None)
        .expect("a lazy client should build for a valid address")
        .announcing(plan);
    let transport = RetryingTransport::new(client, RealSleeper, plan);
    let started = std::time::Instant::now();
    let error = transport.health().await.unwrap_err();
    let elapsed = started.elapsed();
    assert_eq!(
        error,
        TransportError::Timeout {
            after: Duration::from_millis(60)
        },
        "the local bound lost the race to tonic's own timer",
    );
    assert!(!is_transient(&error), "a timeout must stay terminal");
    assert!(
        elapsed < plan.announced_deadline_for(SeamMethod::Health).unwrap(),
        "took {elapsed:?}, which is past the announcement tonic armed a clock from",
    );
}

#[tokio::test]
async fn a_brain_sent_deadline_exceeded_is_the_body_s_own_timeout_coming_back() {
    let addr = spawn_fake_brain(FakeBrain::new(Script::Expired))
        .await
        .unwrap();
    let plan = RetryPlan::default();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    let error = client.clone().announcing(plan).health().await.unwrap_err();
    assert_eq!(
        error,
        TransportError::Timeout {
            after: plan.announced_deadline_for(SeamMethod::Health).unwrap(),
        }
    );
    assert!(!is_transient(&error));
    assert_eq!(LinkStatus::from_error(&error).state, LinkState::Down);
    assert_eq!(
        client.health().await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("DeadlineExceeded"),
            message: String::from("the brain stopped working on it"),
        }
    );
}

#[tokio::test]
async fn the_seam_token_never_reaches_a_debug_line() {
    let client = BrainSeamClient::connect_lazy_with_token("http://127.0.0.1:1", Some("sekrit"))
        .unwrap()
        .announcing(RetryPlan::default());
    let printed = format!("{client:?}");
    assert!(printed.contains("BrainSeamClient"));
    assert!(!printed.contains("sekrit"), "printed: {printed}");
    assert!(printed.contains("redacted"), "printed: {printed}");
}
