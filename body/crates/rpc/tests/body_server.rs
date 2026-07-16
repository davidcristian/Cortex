//! Contract tests for the `BodyService` server (ADR-0023, ADR-0025): the `body_service` adapter
//! over a fake `AudioControl` + a fake `Notify` is served on loopback (127.0.0.1:0, CI-safe) and
//! driven by the generated `BodyServiceClient` end to end, covering get/set with every
//! optional-field combination, the two `AudioError` arms → their gRPC statuses, the push
//! notification (shown, declined, and both `NotifyError` arms, plus the inert text that reaches
//! the backend), the not-yet-built RPCs → `Unimplemented`, and the seam-token validator
//! (pass-through when unset; every rejection path when set).
//!
//! The fakes also record **which thread** each call ran on, because where the synchronous OS
//! call happens is part of the contract now (it must not park an async worker), and a
//! current-thread test runtime makes that observable.

use std::net::SocketAddr;
use std::sync::{Arc, Mutex, PoisonError};
use std::thread::{self, ThreadId};

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

/// The threads a fake backend was called on, shared with the test after the fake itself has
/// moved into the server task.
type Threads = Arc<Mutex<Vec<ThreadId>>>;

/// Records `thread` as one call site.
fn record(threads: &Threads, thread: ThreadId) {
    threads
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .push(thread);
}

/// Reads back the recorded call sites.
fn recorded(threads: &Threads) -> Vec<ThreadId> {
    threads
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone()
}

/// What a fake `AudioControl` does when called. `Panic` stands in for a backend that dies
/// mid-call (an `unwrap` inside a COM wrapper, a poisoned lock): the handler must still answer.
enum AudioBehaviour {
    Answer,
    Fail(AudioError),
    Panic,
}

/// A fake `AudioControl`: reads/writes a `Mutex`-held state (the port is `Send + Sync`), or
/// applies a scripted failure on every call.
struct FakeAudio {
    state: Mutex<VolumeState>,
    behaviour: AudioBehaviour,
    threads: Threads,
}

impl FakeAudio {
    fn scripted(level: f32, muted: bool, behaviour: AudioBehaviour) -> Self {
        Self {
            state: Mutex::new(VolumeState { level, muted }),
            behaviour,
            threads: Threads::default(),
        }
    }

    fn new(level: f32, muted: bool) -> Self {
        Self::scripted(level, muted, AudioBehaviour::Answer)
    }

    fn failing(error: AudioError) -> Self {
        Self::scripted(0.5, false, AudioBehaviour::Fail(error))
    }

    fn panicking() -> Self {
        Self::scripted(0.5, false, AudioBehaviour::Panic)
    }

    /// A handle on the call sites, taken before the fake moves into the server.
    fn threads(&self) -> Threads {
        Arc::clone(&self.threads)
    }

    /// Records the calling thread, then applies the scripted behaviour.
    fn enter(&self) -> Result<(), AudioError> {
        record(&self.threads, thread::current().id());
        match &self.behaviour {
            AudioBehaviour::Answer => Ok(()),
            AudioBehaviour::Fail(error) => Err(error.clone()),
            AudioBehaviour::Panic => panic!("the audio backend died mid-call"),
        }
    }
}

impl AudioControl for FakeAudio {
    fn get_volume(&self) -> Result<VolumeState, AudioError> {
        self.enter()?;
        Ok(*self.state.lock().unwrap_or_else(PoisonError::into_inner))
    }

    fn set_volume(&self, change: VolumeChange) -> Result<VolumeState, AudioError> {
        self.enter()?;
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

/// What a fake `Notify` does when called, mirroring [`AudioBehaviour`]. `Answer` carries the
/// verdict the host would give (shown, or declined because notifications are off).
#[derive(Clone)]
enum NotifyBehaviour {
    Answer(bool),
    Fail(NotifyError),
    Panic,
}

/// A fake `Notify`: records every notification it is shown and answers a scripted verdict, or
/// fails on every call. The record lives behind an `Arc` so a test can read what actually
/// crossed the seam after the fake moved into the server task.
#[derive(Clone)]
struct FakeNotify {
    behaviour: NotifyBehaviour,
    seen: Arc<Mutex<Vec<Notification>>>,
    threads: Threads,
}

impl FakeNotify {
    fn scripted(behaviour: NotifyBehaviour) -> Self {
        Self {
            behaviour,
            seen: Arc::default(),
            threads: Threads::default(),
        }
    }

    fn answering(shown: bool) -> Self {
        Self::scripted(NotifyBehaviour::Answer(shown))
    }

    fn failing(error: NotifyError) -> Self {
        Self::scripted(NotifyBehaviour::Fail(error))
    }

    fn panicking() -> Self {
        Self::scripted(NotifyBehaviour::Panic)
    }

    fn seen(&self) -> Vec<Notification> {
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }

    /// A handle on the call sites, taken before the fake moves into the server.
    fn threads(&self) -> Threads {
        Arc::clone(&self.threads)
    }
}

impl Notify for FakeNotify {
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError> {
        record(&self.threads, thread::current().id());
        match &self.behaviour {
            NotifyBehaviour::Fail(error) => Err(error.clone()),
            NotifyBehaviour::Panic => panic!("the notification backend died mid-call"),
            NotifyBehaviour::Answer(shown) => {
                self.seen
                    .lock()
                    .unwrap_or_else(PoisonError::into_inner)
                    .push(notification.clone());
                Ok(*shown)
            }
        }
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
async fn every_os_call_runs_off_the_async_worker() {
    let audio = FakeAudio::new(0.5, false);
    let notifier = FakeNotify::answering(true);
    let (audio_threads, notify_threads) = (audio.threads(), notifier.threads());
    let addr = spawn_with(audio, notifier, "").await.unwrap();
    let mut client = connect(addr).await.unwrap();
    client.get_volume(GetVolumeRequest {}).await.unwrap();
    client
        .set_volume(SetVolumeRequest {
            level: Some(0.2),
            mute: None,
        })
        .await
        .unwrap();
    client
        .notify(notify_request("stretch", false))
        .await
        .unwrap();

    // `#[tokio::test]` builds a current-thread runtime, so the server task and its handlers run
    // on this very thread. A synchronous OS call made inline would therefore report *this*
    // thread; each of the three reporting a different one is the proof it was handed to the
    // blocking pool instead, which is the whole point of the change (ADR-0023 addendum).
    let here = thread::current().id();
    let ran_on = [recorded(&audio_threads), recorded(&notify_threads)].concat();
    assert_eq!(ran_on.len(), 3);
    assert!(ran_on.iter().all(|&id| id != here));
}

#[tokio::test]
async fn a_panicking_audio_backend_answers_internal_and_keeps_the_connection() {
    let addr = spawn_body(FakeAudio::panicking(), "").await.unwrap();
    let mut client = connect(addr).await.unwrap();
    let status = client.get_volume(GetVolumeRequest {}).await.unwrap_err();
    assert_eq!(status.code(), Code::Internal);
    assert!(status.message().contains("the OS call failed"));

    // The brain holds this connection for every later OS action, so a dead backend must cost
    // it a status and not the channel: the next call is answered rather than dropped.
    let status = client
        .set_volume(SetVolumeRequest {
            level: Some(0.3),
            mute: None,
        })
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Internal);
    assert!(status.message().contains("the OS call failed"));
}

#[tokio::test]
async fn a_panicking_notification_backend_answers_internal() {
    let addr = spawn_with(FakeAudio::new(0.5, false), FakeNotify::panicking(), "")
        .await
        .unwrap();
    let status = connect(addr)
        .await
        .unwrap()
        .notify(notify_request("stretch", false))
        .await
        .unwrap_err();
    assert_eq!(status.code(), Code::Internal);
    assert!(status.message().contains("the OS call failed"));
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
