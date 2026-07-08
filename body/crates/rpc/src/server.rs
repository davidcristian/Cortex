//! The body-side `BodyService` server: the brain's OS-action calls, translated to the
//! `body_core` OS ports (ADR-0023) in the first brain→body direction of the seam.
//!
//! A thin adapter (AGENTS.md): [`VolumeService`] implements the generated `BodyService` trait
//! over an injected [`AudioControl`] backend. `get_volume`/`set_volume` map the wire messages
//! onto the port (the clamp lives in `body_core::VolumeChange`); `capture_screen`/`inject_input`
//! answer `Unimplemented` until their slices. No business logic, no state: volume is read from
//! the OS on demand (the one hard rule). The bind/serve lifecycle lives in the ungated Tauri
//! shell; this crate holds only the coverable translation plus the seam-token validator
//! ([`crate::auth`]).

use body_core::{AudioControl, AudioError, VolumeChange};
use tonic::service::interceptor::InterceptedService;
use tonic::{Request, Response, Status};

use crate::auth::SeamTokenValidator;
use crate::generated::VolumeState as PbVolumeState;
use crate::generated::body_service_server::{BodyService, BodyServiceServer};
use crate::generated::{
    CaptureScreenReply, CaptureScreenRequest, GetVolumeRequest, InjectInputReply,
    InjectInputRequest, SetVolumeRequest,
};

/// The `BodyService` implementation over an [`AudioControl`] backend.
pub struct VolumeService<A: AudioControl> {
    audio: A,
}

impl<A: AudioControl> VolumeService<A> {
    /// Wraps `audio` as the `BodyService` volume handlers.
    #[must_use]
    pub const fn new(audio: A) -> Self {
        Self { audio }
    }
}

#[tonic::async_trait]
impl<A: AudioControl + 'static> BodyService for VolumeService<A> {
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
}

/// Maps an [`AudioError`] to the outbound gRPC [`Status`] the brain reads. This is the inverse of
/// `client::status_to_error`. A missing endpoint is `Unavailable` (transient, like a dead
/// backend); a backend failure is `Internal`.
fn audio_error_to_status(error: &AudioError) -> Status {
    match error {
        AudioError::NoEndpoint(detail) => {
            Status::unavailable(format!("no audio endpoint: {detail}"))
        }
        AudioError::Backend(detail) => Status::internal(format!("audio backend error: {detail}")),
    }
}

/// Builds the `BodyService` server over `audio`, fronted by the seam-token validator
/// (ADR-0016/0023): an empty `token` makes the validator a pass-through, so a tokenless
/// deployment is byte-for-byte the tokenless server. The ungated Tauri shell serves the result.
pub fn body_service<A: AudioControl + 'static>(
    audio: A,
    token: &str,
) -> InterceptedService<BodyServiceServer<VolumeService<A>>, SeamTokenValidator> {
    BodyServiceServer::with_interceptor(VolumeService::new(audio), SeamTokenValidator::new(token))
}
