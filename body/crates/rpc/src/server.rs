//! The body-side `BodyService` server: the brain's OS-action calls, translated to the
//! `body_core` OS ports (ADR-0023) in the first brain→body direction of the seam.
//!
//! A thin adapter (AGENTS.md): [`OsService`] implements the generated `BodyService` trait over
//! an injected [`AudioControl`] backend and an injected [`Notify`] backend (ADR-0025).
//! `get_volume`/`set_volume` map the wire messages onto the volume port (the clamp lives in
//! `body_core::VolumeChange`); `notify` builds a `body_core::Notification` (which is where the
//! inert-text rule lives) and reports whether the host displayed it;
//! `capture_screen`/`inject_input` answer `Unimplemented` until their slices. No business
//! logic, no state: volume is read from the OS on demand and a notification is fire and
//! forget (the one hard rule). The bind/serve lifecycle lives in the ungated Tauri shell;
//! this crate holds only the coverable translation plus the seam-token validator
//! ([`crate::auth`]).
//!
//! Both OS ports are **synchronous** (they are COM on Windows, and COM has no async form), so
//! every handler hands its one call to [`off_worker`] rather than making it inline: an async
//! worker thread must never be parked on the OS. See that function for why the backends are
//! held behind an `Arc`.

use std::sync::Arc;

use body_core::{AudioControl, AudioError, Notification, Notify, NotifyError, VolumeChange};
use tonic::service::interceptor::InterceptedService;
use tonic::{Request, Response, Status};

use crate::auth::SeamTokenValidator;
use crate::generated::VolumeState as PbVolumeState;
use crate::generated::body_service_server::{BodyService, BodyServiceServer};
use crate::generated::{
    CaptureScreenReply, CaptureScreenRequest, GetVolumeRequest, InjectInputReply,
    InjectInputRequest, NotifyReply, NotifyRequest, SetVolumeRequest,
};

/// The `BodyService` implementation over the host's OS backends.
///
/// Each backend is held behind an [`Arc`] purely so a handler can lend it to the blocking
/// thread that runs its synchronous call ([`off_worker`]); nothing is shared beyond that, and
/// the service still holds no state.
pub struct OsService<A: AudioControl, N: Notify> {
    audio: Arc<A>,
    notifier: Arc<N>,
}

impl<A: AudioControl, N: Notify> OsService<A, N> {
    /// Wraps `audio` and `notifier` as the `BodyService` handlers.
    #[must_use]
    pub fn new(audio: A, notifier: N) -> Self {
        Self {
            audio: Arc::new(audio),
            notifier: Arc::new(notifier),
        }
    }
}

#[tonic::async_trait]
impl<A: AudioControl + 'static, N: Notify + 'static> BodyService for OsService<A, N> {
    async fn get_volume(
        &self,
        _request: Request<GetVolumeRequest>,
    ) -> Result<Response<PbVolumeState>, Status> {
        let audio = Arc::clone(&self.audio);
        let state = off_worker(move || audio.get_volume(), audio_error_to_status).await?;
        Ok(Response::new(PbVolumeState {
            level: state.level,
            muted: state.muted,
        }))
    }

    async fn set_volume(
        &self,
        request: Request<SetVolumeRequest>,
    ) -> Result<Response<PbVolumeState>, Status> {
        let SetVolumeRequest { level, mute } = request.into_inner();
        let change = VolumeChange::new(level, mute);
        let audio = Arc::clone(&self.audio);
        let state = off_worker(move || audio.set_volume(change), audio_error_to_status).await?;
        Ok(Response::new(PbVolumeState {
            level: state.level,
            muted: state.muted,
        }))
    }

    async fn capture_screen(
        &self,
        _request: Request<CaptureScreenRequest>,
    ) -> Result<Response<CaptureScreenReply>, Status> {
        Err(Status::unimplemented("screen capture lands in Slice 10"))
    }

    async fn inject_input(
        &self,
        _request: Request<InjectInputRequest>,
    ) -> Result<Response<InjectInputReply>, Status> {
        Err(Status::unimplemented(
            "input injection lands in a later slice",
        ))
    }

    /// Shows a fired reminder on the host (ADR-0025 decision 6). `shown=false` is a state
    /// report the brain reads exactly like a failure (the reminder stays deliverable for the
    /// overlay's pull path), so it stays in the reply rather than becoming a status.
    async fn notify(
        &self,
        request: Request<NotifyRequest>,
    ) -> Result<Response<NotifyReply>, Status> {
        let NotifyRequest {
            title,
            body,
            reminder_id,
            tainted,
        } = request.into_inner();
        let notification = Notification::new(&title, &body, &reminder_id, tainted);
        let notifier = Arc::clone(&self.notifier);
        let shown =
            off_worker(move || notifier.show(&notification), notify_error_to_status).await?;
        Ok(Response::new(NotifyReply { shown }))
    }
}

/// Runs one synchronous OS call on tokio's blocking pool and awaits its answer, mapping a
/// backend failure with `to_status` (ADR-0023's deferred `spawn_blocking`).
///
/// Both OS ports are sync because the OS is: Core Audio and the toast manager are COM, which
/// has no async form, and a COM call can park its thread for as long as the audio stack or the
/// notification service takes. Called inline, that parks an **async worker**, and the runtime
/// serving `BodyService` is the same one the overlay's own seam calls run on, so one slow
/// endpoint would stall work that has nothing to do with it. Handing the call to the blocking
/// pool costs a thread hop and buys back the guarantee that nothing else waits on the OS.
///
/// The closure must own what it touches (`'static`), which is why the backends live behind an
/// `Arc` the handler clones. Nothing COM-shaped crosses a thread: the real backends are a unit
/// struct and an app-id string, and each resolves its own interface *inside* the closure, so
/// the COM pointers are created and dropped on the one thread that uses them.
///
/// A panicking backend arrives here as a join failure rather than a value. It answers
/// `Internal` like any other backend fault, because the alternative (letting the panic escape
/// the handler) tears down the connection the brain is holding.
async fn off_worker<T, E>(
    call: impl FnOnce() -> Result<T, E> + Send + 'static,
    to_status: impl FnOnce(&E) -> Status,
) -> Result<T, Status>
where
    T: Send + 'static,
    E: Send + 'static,
{
    match tokio::task::spawn_blocking(call).await {
        Ok(Ok(value)) => Ok(value),
        Ok(Err(error)) => Err(to_status(&error)),
        Err(join) => Err(Status::internal(format!("the OS call failed: {join}"))),
    }
}

/// Maps an [`AudioError`] to the outbound gRPC [`Status`] the brain reads. This is the inverse of
/// `status::status_to_error`. A missing endpoint is `Unavailable` (transient, like a dead
/// backend); a backend failure is `Internal`.
fn audio_error_to_status(error: &AudioError) -> Status {
    match error {
        AudioError::NoEndpoint(detail) => {
            Status::unavailable(format!("no audio endpoint: {detail}"))
        }
        AudioError::Backend(detail) => Status::internal(format!("audio backend error: {detail}")),
    }
}

/// Maps a [`NotifyError`] to the outbound gRPC [`Status`], on the same split as the volume
/// mapping: a missing notification service is `Unavailable` (transient), a backend failure is
/// `Internal`. Either way the brain treats the push as failed and leaves the reminder
/// deliverable, so the mapping costs it nothing to read but keeps its logs honest.
fn notify_error_to_status(error: &NotifyError) -> Status {
    match error {
        NotifyError::Unavailable(detail) => {
            Status::unavailable(format!("no notification service: {detail}"))
        }
        NotifyError::Backend(detail) => {
            Status::internal(format!("notification backend error: {detail}"))
        }
    }
}

/// Builds the `BodyService` server over `audio` and `notifier`, fronted by the seam-token
/// validator (ADR-0016/0023): an empty `token` makes the validator a pass-through, so a
/// tokenless deployment is byte-for-byte the tokenless server. The ungated Tauri shell serves
/// the result.
pub fn body_service<A: AudioControl + 'static, N: Notify + 'static>(
    audio: A,
    notifier: N,
    token: &str,
) -> InterceptedService<BodyServiceServer<OsService<A, N>>, SeamTokenValidator> {
    BodyServiceServer::with_interceptor(
        OsService::new(audio, notifier),
        SeamTokenValidator::new(token),
    )
}
