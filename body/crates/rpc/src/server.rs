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
pub struct OsService<A: AudioControl, N: Notify> {
    audio: A,
    notifier: N,
}

impl<A: AudioControl, N: Notify> OsService<A, N> {
    /// Wraps `audio` and `notifier` as the `BodyService` handlers.
    #[must_use]
    pub const fn new(audio: A, notifier: N) -> Self {
        Self { audio, notifier }
    }
}

#[tonic::async_trait]
impl<A: AudioControl + 'static, N: Notify + 'static> BodyService for OsService<A, N> {
    async fn get_volume(
        &self,
        _request: Request<GetVolumeRequest>,
    ) -> Result<Response<PbVolumeState>, Status> {
        let state = self
            .audio
            .get_volume()
            .map_err(|error| audio_error_to_status(&error))?;
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
        let state = self
            .audio
            .set_volume(VolumeChange::new(level, mute))
            .map_err(|error| audio_error_to_status(&error))?;
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
        let shown = self
            .notifier
            .show(&Notification::new(&title, &body, &reminder_id, tainted))
            .map_err(|error| notify_error_to_status(&error))?;
        Ok(Response::new(NotifyReply { shown }))
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
