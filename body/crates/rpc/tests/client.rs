//! Contract tests for `BrainSeamClient`: a scripted in-process fake serves
//! the generated `BrainService` on loopback (port 0 with no network beyond
//! 127.0.0.1, CI-safe) and the adapter's mappings are asserted end to end:
//! healthy round-trip, brain-reported gRPC status → `TransportError::Rpc`,
//! and every way the brain can be unreachable (bad address, refused dial,
//! brain death after a successful connect) → `TransportError::Connection`.

use std::net::SocketAddr;
use std::pin::Pin;

use body_core::{BrainTransport, SeamHealth, SessionMessage, SessionSummary, TransportError};
use body_rpc::BrainSeamClient;
use body_rpc::generated::brain_service_client::BrainServiceClient;
use body_rpc::generated::brain_service_server::{BrainService, BrainServiceServer};
use body_rpc::generated::{
    AckReminderReply, AckReminderRequest, ClientEvent, GetSessionMessagesReply,
    GetSessionMessagesRequest, HealthReply, HealthRequest, ListDueRemindersReply,
    ListDueRemindersRequest, ListSessionsReply, ListSessionsRequest, ServerEvent,
    SessionMessage as PbSessionMessage, SessionSummary as PbSessionSummary,
};
use tokio::net::TcpListener;
use tokio::sync::oneshot;
use tokio::task::JoinHandle;
use tokio_stream::Stream;
use tokio_stream::wrappers::TcpListenerStream;
use tonic::transport::Server;
use tonic::{Request, Response, Status, Streaming};

/// What the scripted fake brain answers to `Health`.
#[derive(Clone, Copy)]
enum Script {
    /// `Health` succeeds with `ready = true` and a detail string.
    Ready,
    /// `Health` fails with a gRPC `Internal` status.
    Failing,
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
}

impl FakeBrain {
    fn new(script: Script) -> Self {
        Self {
            script,
            expected_token: None,
            sessions_fail: false,
        }
    }
}

#[tonic::async_trait]
impl BrainService for FakeBrain {
    type ConverseStream = Pin<Box<dyn Stream<Item = Result<ServerEvent, Status>> + Send>>;

    async fn converse(
        &self,
        _request: Request<Streaming<ClientEvent>>,
    ) -> Result<Response<Self::ConverseStream>, Status> {
        Err(Status::unimplemented("converse lands in a later slice"))
    }

    async fn health(
        &self,
        request: Request<HealthRequest>,
    ) -> Result<Response<HealthReply>, Status> {
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
        }
    }

    async fn list_sessions(
        &self,
        request: Request<ListSessionsRequest>,
    ) -> Result<Response<ListSessionsReply>, Status> {
        if self.sessions_fail {
            return Err(Status::unavailable("store down"));
        }
        // Echo the requested limit into the first title so the test can prove the
        // request field crossed the wire; two rows prove order is preserved.
        let limit = request.into_inner().limit;
        Ok(Response::new(ListSessionsReply {
            sessions: vec![
                PbSessionSummary {
                    session_id: String::from("beta"),
                    title: format!("limit={limit}"),
                    preview: String::from("newest chat"),
                    last_activity_unix_ms: 2000,
                },
                PbSessionSummary {
                    session_id: String::from("alpha"),
                    title: String::from("older chat"),
                    preview: String::from("oldest chat"),
                    last_activity_unix_ms: 1000,
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

    // The reminder RPCs are unused by these transport tests until BrainTransport grows
    // them (ADR-0025); they exist only to satisfy the generated server trait.
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
    // The folded source chain must name the actual cause, not just tonic's
    // opaque "transport error" wrapper.
    assert!(
        message.contains("refused") || message.contains("os error"),
        "message should name the root cause, got: {message}"
    );
}

#[tokio::test]
async fn brain_death_after_connect_maps_to_the_connection_variant() {
    // The taxonomy's most common runtime failure: the brain dies AFTER the
    // channel connected. tonic surfaces that as a locally-synthesized status;
    // the adapter must report it as Connection ("cannot reach the brain"),
    // never as a brain-reported Rpc error.
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
            },
            SessionSummary {
                session_id: String::from("alpha"),
                title: String::from("older chat"),
                preview: String::from("oldest chat"),
                last_activity_unix_ms: 1000,
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
async fn seam_token_round_trips_when_the_brain_requires_it() {
    let mut fake = FakeBrain::new(Script::Ready);
    fake.expected_token = Some("sekrit-seam-token");
    let addr = spawn_fake_brain(fake).await.unwrap();
    let client =
        BrainSeamClient::connect_with_token(&format!("http://{addr}"), Some("sekrit-seam-token"))
            .await
            .unwrap();
    assert!(client.health().await.unwrap().ready);
    // The client's Debug never carries the secret (tonic prints the
    // interceptor by type name; the interceptor itself has no Debug).
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
