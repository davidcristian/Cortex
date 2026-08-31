//! Contract tests for `BrainSeamClient`: a scripted in-process fake serves the generated
//! `BrainService` on loopback (port 0, with no network beyond 127.0.0.1, so CI can run it) and
//! the adapter's mappings are asserted end to end. A healthy round-trip, a brain-reported gRPC
//! status mapping to `TransportError::Rpc`, and every way the brain can be unreachable (a bad
//! address, a refused dial, the brain dying after a successful connect) mapping to
//! `TransportError::Connection`. Two checks spend real time on purpose, because a clock is what
//! they are about: the per-attempt deadline ending a brain that never answers, and how tonic's
//! own expired request timeout is classified (ADR-0024).

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
    SetPreferenceRequest, SetSessionPinnedReply, SetSessionPinnedRequest,
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
    /// `Health` never answers: the connection is accepted and the call hangs forever. This is
    /// the failure no status can report, and the reason the seam has a deadline (ADR-0024
    /// deadline addendum).
    Hanging,
    /// `Health` fails `DEADLINE_EXCEEDED`: the brain gave up on the call itself, which is what
    /// the announced `grpc-timeout` invites it to do (ADR-0024 courtesy-header addendum).
    Expired,
}

/// A scripted fake implementing the generated `BrainService` server trait.
/// With `expected_token` set it mirrors the brain's seam-token check
/// (ADR-0016): `Health` demands the matching `x-cortex-seam-token` metadata.
struct FakeBrain {
    script: Script,
    expected_token: Option<&'static str>,
    /// When set, the read-only session RPCs (ADR-0021) fail `Unavailable` (a
    /// store-down abort); otherwise they answer with canned rows.
    sessions_fail: bool,
    /// The same for the reminder RPCs (ADR-0025): a `ScheduleStoreError` aborts
    /// `Unavailable`. Separate from `sessions_fail` because the two read different
    /// stores, so a body sees one fail while the other answers.
    reminders_fail: bool,
    /// Records each `RenameSession` write `(session_id, title)` the fake received, so a test
    /// can prove both fields crossed the wire (the reply is a bare ack, ADR-0021).
    renames: Arc<Mutex<Vec<(String, String)>>>,
    /// Records each `DeleteSession` write's `session_id`, so a test can prove the id crossed the
    /// wire (the reply is a bare ack, ADR-0021).
    deletes: Arc<Mutex<Vec<String>>>,
    /// Records each `SetSessionPinned` write `(session_id, pinned)`, so a test can prove both
    /// fields crossed the wire (the reply is a bare ack, ADR-0021 pinning addendum).
    pins: Arc<Mutex<Vec<(String, bool)>>>,
    /// Records each `SetPreference` write `(key, value)`, so a test can prove both fields crossed
    /// the wire, the empty clearing value included (the reply is a bare ack).
    preference_writes: Arc<Mutex<Vec<(String, String)>>>,
    /// Records the `grpc-timeout` metadata of every call the fake serves, `None` for a call that
    /// carried none. The courtesy deadline is a header and nothing in a reply echoes it, so this
    /// is the only place a test can read what the body announced (ADR-0024 courtesy-header
    /// addendum).
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
            pins: Arc::new(Mutex::new(Vec::new())),
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

/// The `grpc-timeout` header read back as the duration it spells (the gRPC unit suffixes: hours,
/// minutes, seconds, milli-, micro-, nanoseconds). Parsed rather than string-compared so a test
/// asserts the duration the brain was told and not the unit tonic happened to pick for it.
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
                _ => return Err(Status::unauthenticated("invalid or missing seam token")),
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
        // Echo the requested limit into the first title so the test can prove the
        // request field crossed the wire; two rows prove order is preserved.
        let limit = request.into_inner().limit;
        Ok(Response::new(ListSessionsReply {
            sessions: vec![
                // `beta` is pinned, so it also proves the `pinned` flag crosses the wire.
                PbSessionSummary {
                    session_id: String::from("beta"),
                    title: format!("limit={limit}"),
                    preview: String::from("newest chat"),
                    last_activity_unix_ms: 2000,
                    pinned: true,
                },
                PbSessionSummary {
                    session_id: String::from("alpha"),
                    title: String::from("older chat"),
                    preview: String::from("oldest chat"),
                    last_activity_unix_ms: 1000,
                    pinned: false,
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
        // Echo the session id into the first message text (same wire-round-trip proof).
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
        // Two rows, differing in every flag, so the mapping cannot pass by luck: a
        // trusted recurring one and a tainted session-less one-shot.
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
        // Only the listed id is deliverable, mirroring the brain: acking anything else
        // clears nothing and answers false. This also proves the id crossed the wire.
        let reminder_id = request.into_inner().reminder_id;
        Ok(Response::new(AckReminderReply {
            acked: reminder_id == "r1",
        }))
    }

    async fn rename_session(
        &self,
        request: Request<RenameSessionRequest>,
    ) -> Result<Response<RenameSessionReply>, Status> {
        // A store-down abort behaves like the reads; otherwise record the write so the test can
        // prove both fields crossed the wire (the reply carries nothing to echo).
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
        // A store/memory-down abort behaves like the reads; otherwise record the deleted id so the
        // test can prove it crossed the wire (the reply carries nothing to echo).
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        self.deletes
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(request.into_inner().session_id);
        Ok(Response::new(DeleteSessionReply {}))
    }

    async fn set_session_pinned(
        &self,
        request: Request<SetSessionPinnedRequest>,
    ) -> Result<Response<SetSessionPinnedReply>, Status> {
        // A store-down abort behaves like the reads; otherwise record the write so the test can
        // prove both fields crossed the wire (the reply carries nothing to echo).
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        let req = request.into_inner();
        self.pins
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push((req.session_id, req.pinned));
        Ok(Response::new(SetSessionPinnedReply {}))
    }

    async fn get_preferences(
        &self,
        _request: Request<GetPreferencesRequest>,
    ) -> Result<Response<GetPreferencesReply>, Status> {
        // A store-down abort behaves like the reads; otherwise answer a canned record, sorted
        // by key exactly as the brain sorts it.
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

/// Like [`spawn_fake_brain`], but with graceful shutdown wired to the
/// returned sender; awaiting the returned handle after firing it guarantees
/// the listener is released and nothing serves on the address anymore.
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
    // Bind and immediately drop a loopback port so nothing is listening on it.
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    drop(listener);
    let error = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    // The folded source chain must name the root cause rather than only tonic's opaque
    // "transport error" wrapper.
    assert!(
        message.contains("refused") || message.contains("os error"),
        "message should name the root cause, got: {message}"
    );
}

#[tokio::test]
async fn brain_death_after_connect_maps_to_the_connection_variant() {
    // The most common runtime failure in the taxonomy: the brain dies after the channel
    // connected. tonic surfaces that as a locally-synthesized status, and the adapter reports it
    // as Connection, meaning the brain could not be reached, rather than as a brain-reported Rpc
    // error.
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
    // Drives the committed streaming codegen directly: the scripted fake
    // answers `Converse` with `Unimplemented` until a later slice ships it.
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
                title: String::from("limit=7"), // the limit crossed the wire
                preview: String::from("newest chat"),
                last_activity_unix_ms: 2000,
                pinned: true, // the pin flag crossed the wire
            },
            SessionSummary {
                session_id: String::from("alpha"),
                title: String::from("older chat"),
                preview: String::from("oldest chat"),
                last_activity_unix_ms: 1000,
                pinned: false,
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
                text: String::from("chat-9"), // the session id crossed the wire
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
    // The user's label and the target chat both crossed the seam intact.
    assert_eq!(
        *recorder.lock().unwrap(),
        vec![(
            String::from("chat-9"),
            String::from("Everything about cats"),
        )]
    );
    // An empty title (the clear-the-override signal) crosses just as faithfully.
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
    // The target chat crossed the seam intact (the reply is a bare ack).
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
async fn set_session_pinned_writes_both_fields_across_the_wire() {
    let recorder = Arc::new(Mutex::new(Vec::new()));
    let mut fake = FakeBrain::new(Script::Ready);
    fake.pins = recorder.clone();
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    client.set_session_pinned("chat-9", true).await.unwrap();
    // The target chat and the pin state both crossed the seam intact (the reply is a bare ack).
    assert_eq!(
        *recorder.lock().unwrap(),
        vec![(String::from("chat-9"), true)]
    );
    // Unpinning crosses just as faithfully.
    client.set_session_pinned("chat-9", false).await.unwrap();
    assert_eq!(recorder.lock().unwrap()[1], (String::from("chat-9"), false));
}

#[tokio::test]
async fn set_session_pinned_store_failure_maps_to_the_rpc_variant() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.sessions_fail = true;
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client = BrainSeamClient::connect(&format!("http://{addr}"))
        .await
        .unwrap();
    assert_eq!(
        client.set_session_pinned("s", true).await.unwrap_err(),
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
                tainted: true, // the provenance bit survives the seam, so a surface can badge it
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
    assert!(client.ack_reminder("r1").await.unwrap()); // the id crossed the wire
    // Nothing to clear answers `false` rather than failing: the overlay dismissing a reminder
    // the brain already dropped is a no-op.
    assert!(!client.ack_reminder("r-gone").await.unwrap());
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
    assert_eq!(client.ack_reminder("r1").await.unwrap_err(), unavailable);
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
    // The client's Debug never carries the secret: tonic prints the interceptor by type name,
    // and the interceptor itself has no Debug.
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
            message: String::from("invalid or missing seam token"),
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
    // The parse fails before any dial, so no server is needed at the address.
    let error = BrainSeamClient::connect_with_token("http://127.0.0.1:1", Some("bad\ntoken"))
        .await
        .unwrap_err();
    let TransportError::Connection(message) = error else {
        panic!("expected the connection variant, got: {error:?}");
    };
    assert!(
        message.contains("invalid seam token"),
        "message should name the token as the cause, got: {message}"
    );
}

#[tokio::test]
async fn lazy_connect_health_round_trips_over_a_lazy_channel() {
    // The lazy constructor (ADR-0024) never dials at construction; the first RPC
    // establishes the connection, so a healthy round-trip still works.
    let addr = spawn_fake_brain(FakeBrain::new(Script::Ready))
        .await
        .unwrap();
    let client = BrainSeamClient::connect_lazy_with_token(&format!("http://{addr}"), None).unwrap();
    assert!(client.health().await.unwrap().ready);
}

#[tokio::test]
async fn lazy_connect_to_a_dead_endpoint_constructs_then_fails_on_the_first_call() {
    // The point of the lazy channel: construction succeeds even with nothing
    // listening (unlike eager `connect`), so the `RetryingTransport` decorator
    // gets a channel to retry over. The failure surfaces on the call as
    // Connection, and tonic reconnects on a later call if the brain returns.
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
        message.contains("invalid seam token"),
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
    // Pairs arrive as the brain sorted them; the port hands them over verbatim.
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
    // The clearing write is the one that must not be mistaken for "nothing to send".
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

/// The real `Sleeper` over `tokio::time`, as the shell composes it. Repeated here because the
/// shell is un-gated and this suite cannot import it. The check below needs a real clock, since
/// what it asserts is that a genuine gRPC call which never answers is ended by one.
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
    // What the deadline exists for, over a real gRPC call rather than a fake transport: the
    // fake brain accepts the connection and its `Health` never returns, which is the failure no
    // status can report and the case no retry knob covered. The plan's probe deadline ends it,
    // the caller gets a `Timeout` naming that deadline, and the indicator therefore draws `Down`
    // rather than waiting forever behind its in-flight latch.
    //
    // The deadline is short (120 ms) because this is one of the two checks here that spend real
    // time, and a real clock is what it measures, so it cannot be faked away.
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
    // And the classification the overlay renders from it: nothing answered, so `Down`, with the
    // deadline in the detail. A status-shaped timeout would have drawn `Degraded` here, claiming
    // the brain replied, which is what this design avoids.
    let status = probe_link(&transport).await;
    assert_eq!(status.state, LinkState::Down);
    assert_eq!(status.detail, format!("no reply within {deadline:?}"));
}

#[tokio::test]
async fn tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure() {
    // This check exists because the record once said the opposite, from a reading of tonic
    // rather than a run of it. The deadline decision (ADR-0024) first recorded that an expired
    // client-side timeout arrives as a sourceless `Status::cancelled`, so `status_to_error`
    // would call it `Rpc` and the indicator would claim the brain answered. That reading stopped
    // one frame early: `find_status_in_source_chain` does create the cancelled status without a
    // source, and its caller then attaches the originating `tonic::transport::Error` to it, so
    // what arrives carries a transport source.
    //
    // The hazard that creates is what this pins. The classification is correct by accident
    // (`Connection`, drawn `Down`, since nothing answered), but `Connection` is in the retryable
    // set, so a deadline armed on the transport would be retried, which is the load
    // amplification the same decision rules out. Nothing in the tree arms a tonic timer today,
    // so this check is the answer to the next person who considers it. If a tonic upgrade
    // changes any of it, this fails and the answer gets re-derived.
    let addr = spawn_fake_brain(FakeBrain::new(Script::Hanging))
        .await
        .expect("fake brain should bind a loopback port");
    let mut raw = BrainServiceClient::connect(format!("http://{addr}"))
        .await
        .expect("the fake brain accepts connections; it just never answers");
    let mut request = Request::new(HealthRequest {});
    // Real time, and little of it: an armed clock is what this measures, 60 ms is enough of
    // one, and the hanging brain cannot beat it by answering early.
    request.set_timeout(Duration::from_millis(60));
    let status = raw
        .health(request)
        .await
        .expect_err("a brain that never answers cannot beat the timeout");

    // The half of the original reading that was right, kept so the correction is legible here.
    assert_eq!(status.code(), tonic::Code::Cancelled);
    assert_eq!(status.message(), "Timeout expired");

    // The half it got wrong, which is why this test exists.
    let error = body_rpc::status_to_error(&status);
    let TransportError::Connection(message) = &error else {
        panic!("tonic's own expiry should carry a transport source, got: {error:?}");
    };
    assert!(
        message.contains("Timeout expired"),
        "the folded chain should name the expiry, got: {message}"
    );
    assert_eq!(LinkStatus::from_error(&error).state, LinkState::Down);

    // And the consequence that decides where the deadline is enforced.
    assert!(
        is_transient(&error),
        "a transport-armed deadline would be retried, which is why the bound lives in the core"
    );
}

#[tokio::test]
async fn an_announcing_client_tells_the_brain_each_call_s_own_deadline() {
    // The courtesy header on the wire (ADR-0024 courtesy-header addendum), read back off the
    // request the fake brain received, because nothing in a reply echoes it. Two calls, because
    // the value is per method: a probe and a read are bounded differently, and a client that
    // announced one number for both would tell the brain to keep working on an abandoned probe
    // for twenty times its deadline.
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
    // And what the brain heard is longer than what the body holds it to, which is the ordering
    // this rests on: the announcement arms tonic's clock too, and that clock must expire second.
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
    // Two calls announce nothing, for two different reasons. A client that was never told a
    // plan, which is what every constructor returns, sends no header at all, so this slice
    // cannot have changed what an existing caller puts on the wire. And `Converse` sends none
    // even from an announcing client, because the plan gives a turn no deadline and a header
    // would hand tonic a clock to end a turn with, which is what the exemption prevents.
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
async fn a_deadline_the_header_cannot_spell_is_dropped_rather_than_sent() {
    // `grpc-timeout` carries at most 8 digits, and tonic panics on a duration past its coarsest
    // unit. `RetryPlan`'s fields are public, so that duration is reachable. The adapter drops
    // such an announcement instead of clamping it, since a clamp would announce something
    // shorter than the bound the core enforces and let tonic's clock expire first. The call
    // still succeeds, which is what this asserts: a courtesy that cannot be paid must not cost
    // the call.
    //
    // This duration is far past the filter's bound rather than at it. The filter sits at the
    // millisecond rung, four rungs below the panic, and the case below holds that edge. Both are
    // kept, because they pin two different facts about the same drop: a duration the header
    // cannot spell at all, and one it spells in a unit that reorders the two clocks.
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
    // Where the filter sits, and why it is not at tonic's panic (ADR-0024 unit-ladder addendum).
    // Three parts, the first of which is measured against tonic rather than read from its source.
    //
    // `set_timeout` is the whole of what the interceptor does, and the channel's own
    // `GrpcTimeout` layer parses that header back off the outgoing request and sleeps on what it
    // decodes. Putting an announcement past the millisecond rung through the public call
    // therefore shows the clock tonic would arm. It truncates onto whole seconds: 100_000_999 ms
    // is announced and 100_000_000 ms is armed, which is 749 ms short of the 100_000_749 ms
    // bound the core would have been enforcing, so tonic's timer expires first and its expiry is
    // retryable. That is the load amplification the grace margin prevents, and it is why an
    // announcement this far up is not sent at all.
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

    // Second, the drop, over the wire: a plan holding exactly that bound announces nothing, and
    // the call it would have been a courtesy to still succeeds.
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

    // Third, the edge itself, one millisecond lower: the last bound whose announcement lands on
    // the rung is still sent, decodes to exactly what was announced, and so still stands above
    // the bound the core enforces. A filter one step too low would silence this call too.
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
    // The ordering the design turns on, measured rather than argued. Announcing a deadline arms
    // tonic's own clock from the same header, so both clocks are running against this brain that
    // accepts the call and never answers. The two are told apart by what they produce: the
    // core's bound gives a terminal `Timeout`, and tonic's would give a `Connection` folding
    // "Timeout expired", which is retryable and would be repeated twice more against a brain
    // already too slow to answer. Getting `Timeout` here shows the grace margin ordered them,
    // and the elapsed bound is the second half of it: the announcement is 250 ms past the
    // deadline, so finishing inside the deadline itself cannot be tonic's clock expiring.
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
    // The header invites the brain to give up on an abandoned call, so the body has to be able
    // to read that answer, and it means what its own expired clock means: nothing came back
    // inside the deadline. It is the same variant, so the indicator draws `Down` rather than the
    // `Degraded` an `Rpc` would draw, which would claim the brain answered the question, and the
    // retry decision leaves it terminal. `after` is the deadline the brain was told, since that
    // is the one that expired at the far end.
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
    // A call that announced nothing stays an `Rpc`: with no deadline of the body's on the wire,
    // the status is the brain's own report about a bound it chose, and there is no duration to
    // name. Both are terminal, so the retry decision does not turn on the difference.
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
    // The client holds the token itself, since it rebuilds an interceptor per call, so the
    // redaction that used to come free from tonic printing interceptors by type name is written
    // out instead. The secret must not be reachable through a `{:?}` of the client that carries
    // it (ADR-0016).
    let client = BrainSeamClient::connect_lazy_with_token("http://127.0.0.1:1", Some("sekrit"))
        .unwrap()
        .announcing(RetryPlan::default());
    let printed = format!("{client:?}");
    assert!(printed.contains("BrainSeamClient"));
    assert!(!printed.contains("sekrit"), "printed: {printed}");
    assert!(printed.contains("redacted"), "printed: {printed}");
}
