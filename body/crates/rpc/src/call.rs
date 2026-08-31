//! What one outgoing call sends: its metadata, and the deadline the body told the brain about.
//!
//! The token is per connection and a deadline is per call, but both travel through the same
//! tonic interceptor, so one interceptor is built per call.

use std::time::Duration;

use body_core::TransportError;
use tonic::metadata::{Ascii, MetadataValue};
use tonic::service::Interceptor;
use tonic::service::interceptor::InterceptedService;
use tonic::transport::Channel;
use tonic::{Request, Status};

use crate::generated::brain_service_client::BrainServiceClient;
use crate::status::announced_status_to_error;

/// The metadata key the shared token travels under. Declared again in `auth.rs` and in the
/// brain's `cortex_seam`.
const SEAM_TOKEN_HEADER: &str = "x-cortex-seam-token";

/// The service every call runs over: tonic's [`Channel`] fronted by the token interceptor,
/// which passes calls through when no token is configured.
pub(crate) type SeamChannel = InterceptedService<Channel, SeamTokenInterceptor>;

/// Attaches the shared token to every outgoing request, and this call's announced deadline when
/// it has one. It must not derive `Debug`, because it holds the secret.
#[derive(Clone)]
pub(crate) struct SeamTokenInterceptor {
    token: Option<MetadataValue<Ascii>>,
    announced: Option<Duration>,
}

impl Interceptor for SeamTokenInterceptor {
    fn call(&mut self, mut request: Request<()>) -> Result<Request<()>, Status> {
        if let Some(token) = &self.token {
            request
                .metadata_mut()
                .insert(SEAM_TOKEN_HEADER, token.clone());
        }
        if let Some(announced) = self.announced {
            // This writes `grpc-timeout` and also starts a local clock, because the channel's
            // own timeout layer parses the header back off the request.
            request.set_timeout(announced);
        }
        Ok(request)
    }
}

/// The longest deadline this transport will announce: about 27.8 hours, the top of the
/// millisecond step of `grpc-timeout`, whose value is at most 8 digits plus a unit. Above it the
/// next step is whole seconds, whose truncation would cost more than the grace margin.
const MAX_ANNOUNCED_DEADLINE_MS: u64 = 99_999_999;

/// One unary call in flight: the client that sends the announcement, and the announcement.
pub(crate) struct SeamCall {
    client: BrainServiceClient<SeamChannel>,
    announced: Option<Duration>,
}

impl SeamCall {
    /// Builds one call over `channel`, sending `token` and announcing `deadline` when the header
    /// can hold it.
    pub(crate) fn new(
        channel: Channel,
        token: Option<MetadataValue<Ascii>>,
        deadline: Option<Duration>,
    ) -> Self {
        let announced = announceable(deadline);
        Self {
            client: BrainServiceClient::with_interceptor(
                channel,
                SeamTokenInterceptor { token, announced },
            ),
            announced,
        }
    }

    /// The generated client for this call.
    pub(crate) fn client(&self) -> BrainServiceClient<SeamChannel> {
        self.client.clone()
    }

    /// Maps a non-OK status from this call through [`announced_status_to_error`], which is where
    /// the announcement decides whether a `DEADLINE_EXCEEDED` is the body's own expired deadline
    /// coming back to it.
    pub(crate) fn error(&self, status: &Status) -> TransportError {
        announced_status_to_error(status, self.announced)
    }
}

/// The part of `deadline` this transport may announce: itself, or nothing when the header cannot
/// hold it in a unit that keeps the two clocks in order ([`MAX_ANNOUNCED_DEADLINE_MS`]).
fn announceable(deadline: Option<Duration>) -> Option<Duration> {
    let ceiling = Duration::from_millis(MAX_ANNOUNCED_DEADLINE_MS);
    deadline.filter(|announced| *announced <= ceiling)
}
