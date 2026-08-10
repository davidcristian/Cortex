//! The body-side `BodyService` server: the brain's OS-action calls, translated to the
//! `body_core` OS ports (ADR-0023) in the first brain→body direction of the seam.

use std::sync::Arc;

use body_core::{
    AudioControl, AudioError, Notification, Notify, NotifyError, ScreenCapture, VolumeChange,
};
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
pub struct OsService<A: AudioControl, N: Notify, S: ScreenCapture> {
    audio: Arc<A>,
    notifier: Arc<N>,
    screen: Arc<S>,
    receipts: bool,
}

impl<A: AudioControl, N: Notify, S: ScreenCapture> OsService<A, N, S> {
    /// Wraps `audio`, `notifier`, and `screen` as the `BodyService` handlers.
    ///
    /// `receipts` is the host's `CORTEX_HOST_CAPTURE_NOTIFY` switch, resolved by the shell:
    /// with it on (the default) every successful capture shows a body-authored notice.
    #[must_use]
    pub fn new(audio: A, notifier: N, screen: S, receipts: bool) -> Self {
        Self {
            audio: Arc::new(audio),
            notifier: Arc::new(notifier),
            screen: Arc::new(screen),
            receipts,
        }
    }
}

#[tonic::async_trait]
impl<A: AudioControl + 'static, N: Notify + 'static, S: ScreenCapture + 'static> BodyService
    for OsService<A, N, S>
{
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

    /// Reads the display, or the window the request pointed at, for the cortex (ADR-0029). The
    /// pixels never touch this file: the whole crop, downscale, encode, and byte-ceiling policy
    /// is pure core, and the receipt that tells the user it happened is body-authored.
    async fn capture_screen(
        &self,
        request: Request<CaptureScreenRequest>,
    ) -> Result<Response<CaptureScreenReply>, Status> {
        let CaptureScreenRequest {
            max_edge,
            max_bytes,
            target,
        } = request.into_inner();
        let reply = crate::screen::capture(
            &self.screen,
            &self.notifier,
            max_edge,
            max_bytes,
            target,
            self.receipts,
        )
        .await?;
        Ok(Response::new(reply))
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
pub(crate) async fn off_worker<T, E>(
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

/// Maps an [`AudioError`] to the outbound gRPC [`Status`] the brain reads.
fn audio_error_to_status(error: &AudioError) -> Status {
    match error {
        AudioError::NoEndpoint(detail) => {
            Status::failed_precondition(format!("no audio endpoint: {detail}"))
        }
        AudioError::Backend(detail) => Status::internal(format!("audio backend error: {detail}")),
    }
}

/// Maps a [`NotifyError`] to the outbound gRPC [`Status`], on the same split as the volume mapping:
/// no notification service is `FailedPrecondition` (host state), a backend failure is `Internal`.
fn notify_error_to_status(error: &NotifyError) -> Status {
    match error {
        NotifyError::Unavailable(detail) => {
            Status::failed_precondition(format!("no notification service: {detail}"))
        }
        NotifyError::Backend(detail) => {
            Status::internal(format!("notification backend error: {detail}"))
        }
    }
}

/// Builds the `BodyService` server over `audio`, `notifier`, and `screen`, fronted by the
/// seam-token validator (ADR-0016/0023): an empty `token` makes the validator a pass-through, so a
/// tokenless deployment is byte-for-byte the tokenless server.
pub fn body_service<A: AudioControl + 'static, N: Notify + 'static, S: ScreenCapture + 'static>(
    audio: A,
    notifier: N,
    screen: S,
    receipts: bool,
    token: &str,
) -> InterceptedService<BodyServiceServer<OsService<A, N, S>>, SeamTokenValidator> {
    BodyServiceServer::with_interceptor(
        OsService::new(audio, notifier, screen, receipts),
        SeamTokenValidator::new(token),
    )
}
