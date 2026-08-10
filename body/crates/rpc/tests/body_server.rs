//! Contract tests for the `BodyService` server (ADR-0023, ADR-0025): the `body_service` adapter
//! over a fake `AudioControl` + a fake `Notify` is served on loopback (127.0.0.1:0, CI-safe) and
//! driven by the generated `BodyServiceClient` end to end, covering get/set with every
//! optional-field combination, the two `AudioError` arms → their gRPC statuses, the push
//! notification (shown, declined, and both `NotifyError` arms, plus the inert text that reaches
//! the backend), the screen capture (a real PNG produced by pure core from a fake frame source,
//! the body-authored receipt, and every `CaptureError` arm → its gRPC status), the
//! not-yet-built RPC → `Unimplemented`, and the seam-token validator (pass-through when unset;
//! every rejection path when set).
//!
//! The fakes also record **which thread** each call ran on, because where the synchronous OS
//! call happens is part of the contract now (it must not park an async worker), and a
//! current-thread test runtime makes that observable.

use std::net::SocketAddr;
use std::sync::{Arc, Mutex, PoisonError};
use std::thread::{self, ThreadId};

use body_core::{
    AudioControl, AudioError, Capture, CaptureError, CaptureRequest, CaptureTarget, CapturedFrame,
    DeniedScreenCapture, Notification, Notify, NotifyError, RawFrame, ScreenCapture, TargetRect,
    VolumeChange, VolumeState,
};
use body_rpc::body_service;
use body_rpc::generated::body_service_client::BodyServiceClient;
use body_rpc::generated::{
    CaptureScreenRequest, CaptureTarget as PbCaptureTarget, GetVolumeRequest, ImageBlob,
    InjectInputRequest, NotifyReply, NotifyRequest, SetVolumeRequest, VolumeState as PbVolumeState,
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

/// Serves the audio and notification fakes with capture switched off (the host default),
/// fronted by the seam-token validator on an ephemeral loopback port.
async fn spawn_with(
    audio: FakeAudio,
    notify: FakeNotify,
    token: &'static str,
) -> Result<SocketAddr, std::io::Error> {
    serve(audio, notify, DeniedScreenCapture, true, token).await
}

/// Serves a capture backend alongside the audio and notification fakes.
async fn spawn_screen(
    screen: FakeScreen,
    notify: FakeNotify,
    receipts: bool,
) -> Result<SocketAddr, std::io::Error> {
    serve(FakeAudio::new(0.5, false), notify, screen, receipts, "").await
}

/// Serves every fake fronted by the seam-token validator on an ephemeral loopback port.
async fn serve<S: ScreenCapture + 'static>(
    audio: FakeAudio,
    notify: FakeNotify,
    screen: S,
    receipts: bool,
    token: &'static str,
) -> Result<SocketAddr, std::io::Error> {
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    let incoming = TcpListenerStream::new(listener);
    tokio::spawn(async move {
        Server::builder()
            .add_service(body_service(audio, notify, screen, receipts, token))
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
async fn no_endpoint_maps_to_failed_precondition() {
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
    // Host state, not a body nobody could reach: the brain reserves `Unavailable` for a call
    // that never arrived, so an unplugged speaker must not borrow that code.
    assert_eq!(status.code(), Code::FailedPrecondition);
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
async fn inject_input_is_unimplemented() {
    let addr = spawn_body(FakeAudio::new(0.5, false), "").await.unwrap();
    let input = connect(addr)
        .await
        .unwrap()
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
async fn a_missing_notification_service_maps_to_failed_precondition() {
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
    assert_eq!(status.code(), Code::FailedPrecondition);
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

/// A fake `ScreenCapture`: answers a scripted frame or failure, records the resolved requests
/// it was handed and the thread each ran on.
struct FakeScreen {
    answer: Answer,
    seen: Arc<Mutex<Vec<CaptureRequest>>>,
    threads: Threads,
}

/// What a fake backend hands back. `Raw` is the honest shape of a backend fault in a buffer:
/// the frame is built by production's own `RawFrame::new` inside the handler, so a miscounted
/// buffer is rejected there and the message the brain reads is production's, not the test's.
enum Answer {
    Frame(RawFrame),
    Window(RawFrame, TargetRect),
    Failure(CaptureError),
    Raw(u32, u32, Vec<u8>),
}

impl FakeScreen {
    fn answering(frame: RawFrame) -> Self {
        Self::with(Answer::Frame(frame))
    }

    /// A backend that resolved a target to a window inside the frame, which is what the real
    /// one does after its Z-order walk.
    fn showing(frame: RawFrame, window: TargetRect) -> Self {
        Self::with(Answer::Window(frame, window))
    }

    fn failing(error: CaptureError) -> Self {
        Self::with(Answer::Failure(error))
    }

    /// A backend that reports a size its buffer does not match, as a real one would if it
    /// miscounted a `GetDIBits` stride.
    fn miscounting(width: u32, height: u32, pixels: Vec<u8>) -> Self {
        Self::with(Answer::Raw(width, height, pixels))
    }

    fn with(answer: Answer) -> Self {
        Self {
            answer,
            seen: Arc::default(),
            threads: Threads::default(),
        }
    }

    /// A handle on the requests, taken before the fake moves into the server.
    fn requests(&self) -> Arc<Mutex<Vec<CaptureRequest>>> {
        Arc::clone(&self.seen)
    }

    /// A handle on the call sites, taken before the fake moves into the server.
    fn threads(&self) -> Threads {
        Arc::clone(&self.threads)
    }
}

impl ScreenCapture for FakeScreen {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        record(&self.threads, thread::current().id());
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(*request);
        match &self.answer {
            Answer::Frame(frame) => Ok(CapturedFrame::display(frame.clone())),
            Answer::Window(frame, window) => Ok(CapturedFrame::window(frame.clone(), *window)),
            Answer::Failure(error) => Err(error.clone()),
            Answer::Raw(width, height, pixels) => {
                RawFrame::new(*width, *height, pixels.clone()).map(CapturedFrame::display)
            }
        }
    }
}

/// A flat BGRA frame of the given size.
fn frame(width: u32, height: u32) -> RawFrame {
    let pixels = [0x10, 0x20, 0x30, 0x00].repeat((width * height) as usize);
    RawFrame::new(width, height, pixels)
        .unwrap_or_else(|error| panic!("the fixture frame is malformed: {error}"))
}

/// Wall-clock milliseconds, read independently of the server so a timestamp assertion is not
/// checking production against a value production produced.
fn now_millis() -> i64 {
    let since_epoch = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    i64::try_from(since_epoch.as_millis()).unwrap_or(i64::MAX)
}

/// Runs one capture, returning the blob the seam carried.
async fn capture_once(addr: SocketAddr, max_edge: u32) -> Result<ImageBlob, tonic::Status> {
    capture_bounded(addr, max_edge, 0).await
}

/// Runs one capture that names its own byte ceiling.
async fn capture_bounded(
    addr: SocketAddr,
    max_edge: u32,
    max_bytes: u32,
) -> Result<ImageBlob, tonic::Status> {
    capture_targeted(addr, max_edge, max_bytes, PbCaptureTarget::Display.into()).await
}

/// Runs one capture that names what to point at, as the raw wire integer so a value the enum
/// does not name can be sent the way a newer brain would send one.
async fn capture_targeted(
    addr: SocketAddr,
    max_edge: u32,
    max_bytes: u32,
    target: i32,
) -> Result<ImageBlob, tonic::Status> {
    let mut client = connect(addr)
        .await
        .unwrap_or_else(|error| panic!("could not reach the body: {error}"));
    let reply = client
        .capture_screen(CaptureScreenRequest {
            max_edge,
            max_bytes,
            target,
        })
        .await?
        .into_inner();
    Ok(reply
        .image
        .unwrap_or_else(|| panic!("the reply carried no image")))
}

#[tokio::test]
async fn capture_screen_returns_a_real_downscaled_png_with_its_source_size() {
    let screen = FakeScreen::answering(frame(400, 200));
    let requests = screen.requests();
    let before = now_millis();
    let addr = spawn_screen(screen, FakeNotify::answering(true), true)
        .await
        .unwrap();

    let blob = capture_once(addr, 100).await.unwrap();
    let after = now_millis();

    assert_eq!(blob.mime_type, "image/png");
    assert_eq!(&blob.data[..8], &[0x89, b'P', b'N', b'G', 13, 10, 26, 10]);
    assert_eq!((blob.width, blob.height), (100, 50));
    assert_eq!((blob.source_width, blob.source_height), (400, 200));
    assert!(
        (before..=after).contains(&blob.captured_at_unix_ms),
        "{} is not between {before} and {after}",
        blob.captured_at_unix_ms
    );

    let seen = requests
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone();
    assert_eq!(seen, vec![CaptureRequest::new(100)]);
}

#[tokio::test]
async fn an_unset_max_edge_reaches_the_backend_as_the_body_default() {
    let screen = FakeScreen::answering(frame(4, 4));
    let requests = screen.requests();
    let addr = spawn_screen(screen, FakeNotify::answering(true), true)
        .await
        .unwrap();

    let blob = capture_once(addr, 0).await.unwrap();
    assert_eq!((blob.width, blob.height), (4, 4));

    let seen = requests
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone();
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].max_edge(), 1600);
}

#[tokio::test]
async fn a_targeted_capture_reaches_the_backend_as_a_target_and_crosses_cropped() {
    // The whole point of landing the field and the body's honouring of it together: a knob a
    // shipping body ignores is a silent lie under proto3, so this asserts both halves at once.
    let screen = FakeScreen::showing(frame(40, 20), TargetRect::new(10, 5, 20, 15));
    let requests = screen.requests();
    let addr = spawn_screen(screen, FakeNotify::answering(true), true)
        .await
        .unwrap();

    let blob = capture_targeted(addr, 0, 0, PbCaptureTarget::Focus.into())
        .await
        .unwrap();

    let seen = requests
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone();
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].target(), CaptureTarget::Focus);
    // The picture is the window, and the source size is still the display's, which is what the
    // brain shows the model as the size of the screen.
    assert_eq!((blob.width, blob.height), (10, 10));
    assert_eq!((blob.source_width, blob.source_height), (40, 20));
}

#[tokio::test]
async fn a_target_this_body_does_not_know_reads_as_the_whole_display() {
    // Proto3's own rule for an unrecognized enum, which is what a newer brain asking for
    // something this body cannot resolve looks like on the wire.
    let screen = FakeScreen::answering(frame(4, 4));
    let requests = screen.requests();
    let addr = spawn_screen(screen, FakeNotify::answering(true), true)
        .await
        .unwrap();

    let blob = capture_targeted(addr, 0, 0, 99).await.unwrap();

    assert_eq!((blob.width, blob.height), (4, 4));
    let seen = requests
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone();
    assert_eq!(seen[0].target(), CaptureTarget::Display);
}

#[tokio::test]
async fn a_desktop_with_no_window_to_point_at_is_a_host_state_failure() {
    let addr = spawn_screen(
        FakeScreen::failing(CaptureError::NoTarget(String::from("a bare desktop"))),
        FakeNotify::answering(true),
        true,
    )
    .await
    .unwrap();

    let status = capture_targeted(addr, 0, 0, PbCaptureTarget::Focus.into())
        .await
        .unwrap_err();

    // FailedPrecondition, like a shut lid: it is host state, and it works again the moment a
    // window is on screen. The brain reads that code as "the host is not in a state to capture".
    assert_eq!(status.code(), Code::FailedPrecondition);
    assert_eq!(status.message(), "no capture target: a bare desktop");
}

#[tokio::test]
async fn a_window_off_the_captured_display_is_refused_by_the_core_the_backend_fed() {
    // The backend resolved a window; pure core found it has nothing on the display and refused.
    // Nothing falls back to the whole screen, which is the widening this path must never do.
    let notifier = FakeNotify::answering(true);
    let addr = spawn_screen(
        FakeScreen::showing(frame(40, 20), TargetRect::new(200, 200, 300, 300)),
        notifier.clone(),
        true,
    )
    .await
    .unwrap();

    let status = capture_targeted(addr, 0, 0, PbCaptureTarget::Focus.into())
        .await
        .unwrap_err();

    assert_eq!(status.code(), Code::FailedPrecondition);
    assert!(
        status.message().starts_with("no capture target: "),
        "{}",
        status.message()
    );
    assert!(
        notifier.seen().is_empty(),
        "nothing was captured, so nothing may be announced"
    );
}

#[tokio::test]
async fn the_receipt_says_window_when_one_window_was_sent() {
    let notifier = FakeNotify::answering(true);
    let addr = spawn_screen(
        FakeScreen::showing(frame(40, 20), TargetRect::new(0, 0, 20, 10)),
        notifier.clone(),
        true,
    )
    .await
    .unwrap();

    capture_targeted(addr, 0, 0, PbCaptureTarget::Focus.into())
        .await
        .unwrap();

    let seen = notifier.seen();
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].title(), "Screen captured");
    assert_eq!(
        seen[0].body(),
        "A picture of one window was sent to the assistant."
    );
    assert!(!seen[0].tainted());
}

#[tokio::test]
async fn a_window_filling_the_display_is_announced_as_a_screen_capture() {
    // The sentence describes what was sent rather than what was asked for, so a maximised
    // window whose frame reaches past every edge honestly reports a screen capture.
    let notifier = FakeNotify::answering(true);
    let addr = spawn_screen(
        FakeScreen::showing(frame(40, 20), TargetRect::new(-4, -4, 44, 24)),
        notifier.clone(),
        true,
    )
    .await
    .unwrap();

    let blob = capture_targeted(addr, 0, 0, PbCaptureTarget::Focus.into())
        .await
        .unwrap();

    assert_eq!((blob.width, blob.height), (40, 20));
    assert_eq!(
        notifier.seen()[0].body(),
        "A picture of your screen was sent to the assistant."
    );
}

#[tokio::test]
async fn a_successful_capture_shows_the_body_authored_receipt() {
    let notifier = FakeNotify::answering(true);
    let addr = spawn_screen(FakeScreen::answering(frame(4, 4)), notifier.clone(), true)
        .await
        .unwrap();

    capture_once(addr, 0).await.unwrap();

    let seen = notifier.seen();
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].title(), "Screen captured");
    assert_eq!(
        seen[0].body(),
        "A picture of your screen was sent to the assistant."
    );
    assert_eq!(seen[0].reminder_id(), "screen-capture");
    assert!(!seen[0].tainted());
    assert_eq!(seen[0].attribution(), None);
}

#[tokio::test]
async fn the_receipt_can_be_switched_off_without_losing_the_capture() {
    let notifier = FakeNotify::answering(true);
    let addr = spawn_screen(FakeScreen::answering(frame(4, 4)), notifier.clone(), false)
        .await
        .unwrap();

    let blob = capture_once(addr, 0).await.unwrap();

    assert_eq!((blob.width, blob.height), (4, 4));
    assert!(notifier.seen().is_empty(), "the receipt must not fire");
}

#[tokio::test]
async fn a_failed_receipt_does_not_lose_the_capture() {
    // The pixels have already been read by the time the receipt runs, so refusing to answer
    // would cost the capability and buy no privacy back.
    let notifier = FakeNotify::failing(NotifyError::Unavailable(String::from("no service")));
    let addr = spawn_screen(FakeScreen::answering(frame(4, 4)), notifier, true)
        .await
        .unwrap();

    let blob = capture_once(addr, 0).await.unwrap();
    assert_eq!((blob.width, blob.height), (4, 4));
}

#[tokio::test]
async fn a_capture_runs_off_the_async_worker() {
    let screen = FakeScreen::answering(frame(4, 4));
    let threads = screen.threads();
    let addr = spawn_screen(screen, FakeNotify::answering(true), true)
        .await
        .unwrap();

    capture_once(addr, 0).await.unwrap();

    let calls = recorded(&threads);
    assert_eq!(calls.len(), 1);
    assert_ne!(
        calls[0],
        thread::current().id(),
        "the blit must not run on an async worker"
    );
}

/// Every `CaptureError` variant, with the code the brain classifies it by. The whole set is
/// here rather than a sample, because the brain reads the code to choose what it tells the
/// model, so a variant sharing another's code is a variant the model cannot be told apart.
fn capture_failure_table() -> [(CaptureError, Code, &'static str); 4] {
    [
        (
            CaptureError::NoDisplay(String::from("lid shut")),
            Code::FailedPrecondition,
            "no display: lid shut",
        ),
        (
            CaptureError::Disabled,
            Code::PermissionDenied,
            "screen capture is disabled on this host",
        ),
        (
            CaptureError::Backend(String::from("BitBlt 0x2")),
            Code::Internal,
            "screen capture backend error: BitBlt 0x2",
        ),
        (
            CaptureError::TooLarge(6_291_457),
            Code::ResourceExhausted,
            "the capture is too large for the seam: 6291457 bytes",
        ),
    ]
}

#[tokio::test]
async fn each_capture_failure_maps_to_its_own_status() {
    for (error, code, fragment) in capture_failure_table() {
        let addr = spawn_screen(
            FakeScreen::failing(error),
            FakeNotify::answering(true),
            true,
        )
        .await
        .unwrap();
        let status = capture_once(addr, 0).await.unwrap_err();
        assert_eq!(status.code(), code);
        assert_eq!(status.message(), fragment);
    }
}

#[tokio::test]
async fn no_two_capture_failures_share_a_status_code() {
    // `TooLarge` used to answer `Internal` beside `Backend`, which left a picture that was taken
    // and would not fit indistinguishable from a backend that broke.
    //
    // This reads the table rather than the server, which is a harness rather than production, so
    // on its own it proves nothing. What ties it down is the test above, which requires the
    // server's code to equal this table's for every variant. Composed: production equals a table,
    // and the table has no duplicates, so production has none either.
    let mut codes: Vec<Code> = capture_failure_table()
        .into_iter()
        .map(|(_, code, _)| code)
        .collect();
    codes.sort_by_key(|code| *code as i32);
    codes.dedup();
    assert_eq!(codes.len(), 4, "each capture failure needs its own code");
}

#[tokio::test]
async fn nothing_this_server_answers_is_unavailable() {
    // The rule that makes the brain's classification possible. tonic synthesizes `Unavailable`
    // client-side when a channel cannot connect, and the brain's grpc-python client cannot tell
    // a synthesized status from a sent one, so a body spending that code on host state would be
    // indistinguishable from a body that is not running. Every failure this server can answer is
    // driven here, capture, volume and notify alike.
    for (error, _, _) in capture_failure_table() {
        let addr = spawn_screen(
            FakeScreen::failing(error),
            FakeNotify::answering(true),
            true,
        )
        .await
        .unwrap();
        let status = capture_once(addr, 0).await.unwrap_err();
        assert_ne!(status.code(), Code::Unavailable, "{}", status.message());
    }
    for error in [
        AudioError::NoEndpoint(String::from("gone")),
        AudioError::Backend(String::from("COM 0x1")),
    ] {
        let addr = spawn_body(FakeAudio::failing(error), "").await.unwrap();
        let status = connect(addr)
            .await
            .unwrap()
            .get_volume(GetVolumeRequest {})
            .await
            .unwrap_err();
        assert_ne!(status.code(), Code::Unavailable, "{}", status.message());
    }
    for error in [
        NotifyError::Unavailable(String::from("no notifier")),
        NotifyError::Backend(String::from("HRESULT 0x1")),
    ] {
        let addr = spawn_with(FakeAudio::new(0.5, false), FakeNotify::failing(error), "")
            .await
            .unwrap();
        let status = connect(addr)
            .await
            .unwrap()
            .notify(notify_request("stretch", false))
            .await
            .unwrap_err();
        assert_ne!(status.code(), Code::Unavailable, "{}", status.message());
    }
}

#[tokio::test]
async fn a_failed_capture_shows_no_receipt() {
    let notifier = FakeNotify::answering(true);
    let addr = spawn_screen(
        FakeScreen::failing(CaptureError::Disabled),
        notifier.clone(),
        true,
    )
    .await
    .unwrap();

    capture_once(addr, 0).await.unwrap_err();
    assert!(
        notifier.seen().is_empty(),
        "nothing was captured, so nothing may be announced"
    );
}

#[tokio::test]
async fn a_host_with_capture_switched_off_refuses_every_request() {
    let addr = spawn_body(FakeAudio::new(0.5, false), "").await.unwrap();
    let status = capture_once(addr, 0).await.unwrap_err();
    assert_eq!(status.code(), Code::PermissionDenied);
}

#[tokio::test]
async fn a_backend_that_miscounts_its_buffer_is_caught_by_the_pure_core_frame_check() {
    // The frame is built INSIDE the handler here, from a raw buffer the fake hands over, so
    // `RawFrame::new` really runs and the sentence the brain reads is production's own. Handing
    // over a pre-built error instead would have made this a second copy of the Backend arm of
    // the mapping table above, asserting on a string the test itself wrote.
    let addr = spawn_screen(
        FakeScreen::miscounting(2, 2, vec![0x10; 15]),
        FakeNotify::answering(true),
        true,
    )
    .await
    .unwrap();
    let status = capture_once(addr, 0).await.unwrap_err();
    assert_eq!(status.code(), Code::Internal);
    assert_eq!(
        status.message(),
        "screen capture backend error: the frame is 2x2 but carries 15 bytes, not 16"
    );
}

/// The pure-core capture value is what the handler maps, so a `Capture` built here and the
/// blob the seam carried must agree byte for byte.
#[tokio::test]
async fn the_blob_carries_exactly_what_the_core_encoded() {
    let source = frame(30, 12);
    let expected = Capture::from_bgra(
        &CapturedFrame::display(source.clone()),
        &CaptureRequest::new(10),
    )
    .unwrap();
    let addr = spawn_screen(
        FakeScreen::answering(source),
        FakeNotify::answering(true),
        true,
    )
    .await
    .unwrap();

    let blob = capture_once(addr, 10).await.unwrap();
    assert_eq!(blob.data, expected.data());
    assert_eq!(blob.width, expected.width());
    assert_eq!(blob.height, expected.height());
}

#[tokio::test]
async fn a_ceiling_the_ladder_cannot_meet_is_refused_as_too_large() {
    // The brain names a ceiling no PNG can fit under, so all three rungs overshoot and the
    // body refuses rather than sending a picture the caller already said it would not take.
    let addr = spawn_screen(
        FakeScreen::answering(frame(32, 32)),
        FakeNotify::answering(true),
        true,
    )
    .await
    .unwrap();

    let status = capture_bounded(addr, 32, 40).await.unwrap_err();
    // Resource exhausted, not internal: the picture was taken and the ladder ran out, which is
    // a different thing from a backend that broke and is worth a different sentence.
    assert_eq!(status.code(), Code::ResourceExhausted);
    assert!(
        status
            .message()
            .starts_with("the capture is too large for the seam: "),
        "{}",
        status.message()
    );
}

#[tokio::test]
async fn a_ceiling_the_ladder_can_meet_is_honoured() {
    let notifier = FakeNotify::answering(true);
    let addr = spawn_screen(
        FakeScreen::answering(frame(400, 400)),
        notifier.clone(),
        true,
    )
    .await
    .unwrap();

    // 400x400 flat colour encodes tiny, so a 4 KiB ceiling is met on the first rung.
    let blob = capture_bounded(addr, 400, 4096).await.unwrap();
    assert_eq!((blob.width, blob.height), (400, 400));
    assert!(blob.data.len() <= 4096, "{} bytes", blob.data.len());
    assert_eq!(notifier.seen().len(), 1);
}
