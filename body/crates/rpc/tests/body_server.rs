//! Contract tests for the `BodyService` server (ADR-0023, ADR-0025): the `body_service` adapter
//! over a fake `AudioControl` + a fake `Notify` is served on loopback (127.0.0.1:0, CI-safe) and
//! driven by the generated `BodyServiceClient` end to end, covering get/set with every
//! optional-field combination, the two `AudioError` arms → their gRPC statuses, the push
//! notification (shown, declined, and both `NotifyError` arms, plus the inert text that reaches
//! the backend), the not-yet-built RPCs → `Unimplemented`, and the seam-token validator
//! (pass-through when unset; every rejection path when set).

use std::net::SocketAddr;
use std::sync::{Arc, Mutex, PoisonError};

use body_core::{
    AudioControl, AudioError, Notification, Notify, NotifyError, VolumeChange, VolumeState,
};
use body_rpc::body_service;
use body_rpc::generated::body_service_client::BodyServiceClient;
use body_rpc::generated::{
    CaptureScreenRequest, GetVolumeRequest, InjectInputRequest, NotifyReply, NotifyRequest,
    SetVolumeRequest, VolumeState as PbVolumeState,
};
use tokio::net::TcpListener;
use tokio_stream::wrappers::TcpListenerStream;
use tonic::metadata::MetadataValue;
use tonic::transport::{Channel, Server};
use tonic::{Code, Request};

const TOKEN: &str = "sekrit-seam-token";

/// A fake `AudioControl`: reads/writes a `Mutex`-held state (the port is `Send + Sync`), or
/// returns a scripted error on every call.
struct FakeAudio {
    state: Mutex<VolumeState>,
    fail: Option<AudioError>,
}

impl FakeAudio {
    fn new(level: f32, muted: bool) -> Self {
        Self {
            state: Mutex::new(VolumeState { level, muted }),
            fail: None,
        }
    }

    fn failing(error: AudioError) -> Self {
        Self {
            state: Mutex::new(VolumeState {
                level: 0.5,
                muted: false,
            }),
            fail: Some(error),
        }
    }
}

impl AudioControl for FakeAudio {
    fn get_volume(&self) -> Result<VolumeState, AudioError> {
        if let Some(error) = &self.fail {
            return Err(error.clone());
        }
        Ok(*self.state.lock().unwrap_or_else(PoisonError::into_inner))
    }

    fn set_volume(&self, change: VolumeChange) -> Result<VolumeState, AudioError> {
        if let Some(error) = &self.fail {
            return Err(error.clone());
        }
        let mut state = self.state.lock().unwrap_or_else(PoisonError::into_inner);
        if let Some(level) = change.level {
            state.level = level;
        }
        if let Some(mute) = change.mute {
            state.muted = mute;
        }
        Ok(*state)
    }
}

/// A fake `Notify`: records every notification it is shown and answers a scripted verdict, or
/// fails on every call. The record lives behind an `Arc` so a test can read what actually
/// crossed the seam after the fake moved into the server task.
#[derive(Clone)]
struct FakeNotify {
    shown: bool,
    fail: Option<NotifyError>,
    seen: Arc<Mutex<Vec<Notification>>>,
}

impl FakeNotify {
    fn answering(shown: bool) -> Self {
        Self {
            shown,
            fail: None,
            seen: Arc::default(),
        }
    }

    fn failing(error: NotifyError) -> Self {
        Self {
            shown: false,
            fail: Some(error),
            seen: Arc::default(),
        }
    }

    fn seen(&self) -> Vec<Notification> {
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

impl Notify for FakeNotify {
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError> {
        if let Some(error) = &self.fail {
            return Err(error.clone());
        }
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(notification.clone());
        Ok(self.shown)
    }
}

/// Serves `fake` (with a notification backend that always shows) fronted by the seam-token
/// validator on an ephemeral loopback port.
async fn spawn_body(fake: FakeAudio, token: &'static str) -> Result<SocketAddr, std::io::Error> {
    spawn_with(fake, FakeNotify::answering(true), token).await
}

/// Serves both fakes fronted by the seam-token validator on an ephemeral loopback port.
async fn spawn_with(
    audio: FakeAudio,
    notify: FakeNotify,
    token: &'static str,
) -> Result<SocketAddr, std::io::Error> {
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    let incoming = TcpListenerStream::new(listener);
    tokio::spawn(async move {
        Server::builder()
            .add_service(body_service(audio, notify, token))
            .serve_with_incoming(incoming)
            .await
    });
    Ok(addr)
}

/// One reminder push, as the brain's ticker sends it.
fn notify_request(body: &str, tainted: bool) -> NotifyRequest {
    NotifyRequest {
        title: String::from("Reminder"),
        body: String::from(body),
        reminder_id: String::from("r1"),
        tainted,
    }
}

async fn connect(addr: SocketAddr) -> Result<BodyServiceClient<Channel>, tonic::transport::Error> {
    BodyServiceClient::connect(format!("http://{addr}")).await
}

/// A request carrying the seam token as `x-cortex-seam-token` metadata (a `&'static str`, so
/// the metadata value needs no fallible parse).
fn with_token<T>(message: T, token: &'static str) -> Request<T> {
    let mut request = Request::new(message);
    request
        .metadata_mut()
        .insert("x-cortex-seam-token", MetadataValue::from_static(token));
    request
}

#[tokio::test]
async fn get_volume_reports_the_host_state() {
    let addr = spawn_body(FakeAudio::new(0.4, true), "").await.unwrap();
    let reply = connect(addr)
        .await
        .unwrap()
        .get_volume(GetVolumeRequest {})
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        reply,
        PbVolumeState {
            level: 0.4,
            muted: true,
        }
    );
}

#[tokio::test]
async fn set_volume_applies_each_field_combination() {
    let addr = spawn_body(FakeAudio::new(0.1, false), "").await.unwrap();
    let mut client = connect(addr).await.unwrap();

    // Level only: mute is left untouched.
    let reply = client
        .set_volume(SetVolumeRequest {
            level: Some(0.9),
            mute: None,
        })
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        reply,
        PbVolumeState {
            level: 0.9,
            muted: false,
        }
    );

    // Mute only: level is left untouched.
    let reply = client
        .set_volume(SetVolumeRequest {
            level: None,
            mute: Some(true),
        })
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        reply,
        PbVolumeState {
            level: 0.9,
            muted: true,
        }
    );

    // Neither field: the state is reported unchanged.
    let reply = client
        .set_volume(SetVolumeRequest {
            level: None,
            mute: None,
        })
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        reply,
        PbVolumeState {
            level: 0.9,
            muted: true,
        }
    );

    // Both fields: the whole state changes.
    let reply = client
        .set_volume(SetVolumeRequest {
            level: Some(0.2),
            mute: Some(false),
        })
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        reply,
        PbVolumeState {
            level: 0.2,
            muted: false,
        }
    );
}

#[tokio::test]
async fn no_endpoint_maps_to_unavailable() {
    let addr = spawn_body(
        FakeAudio::failing(AudioError::NoEndpoint(String::from("gone"))),
        "",
    )
    .await
    .unwrap();
    let status = connect(addr)
        .await
        .unwrap()
        .get_volume(GetVolumeRequest {})
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Unavailable);
    assert!(status.message().contains("gone"));
}

#[tokio::test]
async fn backend_failure_maps_to_internal() {
    let addr = spawn_body(
        FakeAudio::failing(AudioError::Backend(String::from("COM 0x1"))),
        "",
    )
    .await
    .unwrap();
    let status = connect(addr)
        .await
        .unwrap()
        .set_volume(SetVolumeRequest {
            level: Some(0.5),
            mute: None,
        })
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Internal);
    assert!(status.message().contains("COM 0x1"));
}

#[tokio::test]
async fn capture_screen_and_inject_input_are_unimplemented() {
    let addr = spawn_body(FakeAudio::new(0.5, false), "").await.unwrap();
    let mut client = connect(addr).await.unwrap();
    let screen = client
        .capture_screen(CaptureScreenRequest {})
        .await
        .unwrap_err();
    assert_eq!(screen.code(), Code::Unimplemented);
    let input = client
        .inject_input(InjectInputRequest { input: None })
        .await
        .unwrap_err();
    assert_eq!(input.code(), Code::Unimplemented);
}

#[tokio::test]
async fn notify_shows_the_reminder_as_inert_text_and_reports_it() {
    let notifier = FakeNotify::answering(true);
    let addr = spawn_with(FakeAudio::new(0.5, false), notifier.clone(), "")
        .await
        .unwrap();
    let reply = connect(addr)
        .await
        .unwrap()
        .notify(notify_request("stretch\nnow <b>", true))
        .await
        .unwrap()
        .into_inner();
    assert_eq!(reply, NotifyReply { shown: true });

    // The wire values reached the backend through `Notification`, so the newline is already
    // a space and the taint carries its body-authored attribution. Markup characters stay:
    // escaping is the renderer's step, and the value must not double-escape for it.
    let shown = notifier.seen();
    assert_eq!(shown.len(), 1);
    assert_eq!(shown[0].title(), "Reminder");
    assert_eq!(shown[0].body(), "stretch now <b>");
    assert_eq!(shown[0].reminder_id(), "r1");
    assert!(shown[0].attribution().is_some());
}

#[tokio::test]
async fn a_declined_notification_answers_shown_false_rather_than_a_status() {
    let addr = spawn_with(FakeAudio::new(0.5, false), FakeNotify::answering(false), "")
        .await
        .unwrap();
    let reply = connect(addr)
        .await
        .unwrap()
        .notify(notify_request("stretch", false))
        .await
        .unwrap()
        .into_inner();
    assert_eq!(reply, NotifyReply { shown: false });
}

#[tokio::test]
async fn a_missing_notification_service_maps_to_unavailable() {
    let addr = spawn_with(
        FakeAudio::new(0.5, false),
        FakeNotify::failing(NotifyError::Unavailable(String::from("no notifier"))),
        "",
    )
    .await
    .unwrap();
    let status = connect(addr)
        .await
        .unwrap()
        .notify(notify_request("stretch", false))
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Unavailable);
    assert!(status.message().contains("no notifier"));
}

#[tokio::test]
async fn a_notification_backend_failure_maps_to_internal() {
    let addr = spawn_with(
        FakeAudio::new(0.5, false),
        FakeNotify::failing(NotifyError::Backend(String::from("HRESULT 0x1"))),
        "",
    )
    .await
    .unwrap();
    let status = connect(addr)
        .await
        .unwrap()
        .notify(notify_request("stretch", false))
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Internal);
    assert!(status.message().contains("HRESULT 0x1"));
}

#[tokio::test]
async fn tokenless_server_accepts_calls_without_a_token() {
    let addr = spawn_body(FakeAudio::new(0.6, false), "").await.unwrap();
    let reply = connect(addr)
        .await
        .unwrap()
        .get_volume(GetVolumeRequest {})
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        reply,
        PbVolumeState {
            level: 0.6,
            muted: false,
        }
    );
}

#[tokio::test]
async fn the_matching_token_is_accepted() {
    let addr = spawn_body(FakeAudio::new(0.3, false), TOKEN).await.unwrap();
    let reply = connect(addr)
        .await
        .unwrap()
        .get_volume(with_token(GetVolumeRequest {}, TOKEN))
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        reply,
        PbVolumeState {
            level: 0.3,
            muted: false,
        }
    );
}

#[tokio::test]
async fn a_missing_token_is_unauthenticated() {
    let addr = spawn_body(FakeAudio::new(0.3, false), TOKEN).await.unwrap();
    let status = connect(addr)
        .await
        .unwrap()
        .get_volume(GetVolumeRequest {})
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Unauthenticated);
}

#[tokio::test]
async fn a_wrong_same_length_token_is_unauthenticated() {
    let addr = spawn_body(FakeAudio::new(0.3, false), TOKEN).await.unwrap();
    // Same length as TOKEN so the constant-time compare runs its full byte loop.
    let status = connect(addr)
        .await
        .unwrap()
        .get_volume(with_token(GetVolumeRequest {}, "sekrit-seam-tokeX"))
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Unauthenticated);
}

#[tokio::test]
async fn a_wrong_length_token_is_unauthenticated() {
    let addr = spawn_body(FakeAudio::new(0.3, false), TOKEN).await.unwrap();
    // Different length exercises the constant-time compare's length-mismatch short-circuit.
    let status = connect(addr)
        .await
        .unwrap()
        .get_volume(with_token(GetVolumeRequest {}, "short"))
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Unauthenticated);
}
