//! What one outgoing seam call carries: the metadata it is sent with, and the deadline the body
//! told the brain about it.

use std::time::Duration;

use body_core::TransportError;
use tonic::metadata::{Ascii, MetadataValue};
use tonic::service::Interceptor;
use tonic::service::interceptor::InterceptedService;
use tonic::transport::Channel;
use tonic::{Request, Status};

use crate::generated::brain_service_client::BrainServiceClient;
use crate::status::announced_status_to_error;

/// The metadata key the seam token travels under (ADR-0016; lowercase per gRPC). Declared again
/// in `auth.rs` and once more in the brain's `cortex_seam`; `scripts/crosscheck.py` ties all
/// three, so a rename here that misses either of the others fails the gate rather than the seam.
const SEAM_TOKEN_HEADER: &str = "x-cortex-seam-token";

/// The service every seam call runs over: tonic's [`Channel`] fronted by the
/// token interceptor (which is a pass-through when no token is configured).
pub(crate) type SeamChannel = InterceptedService<Channel, SeamTokenInterceptor>;

/// Attaches the shared seam token to every outgoing request (ADR-0016), and this call's
/// announced deadline when it has one (ADR-0024 courtesy-header addendum).
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
            // Writes `grpc-timeout` and nothing else. The channel's own `GrpcTimeout` layer sits
            // below this one and parses the header back off the request, so this also arms a
            // local clock: see `announcing` for why that clock must never be the first to fire.
            request.set_timeout(announced);
        }
        Ok(request)
    }
}

/// The longest deadline this transport will announce, and the reason this adapter filters at all.
/// About 27.8 hours, which is the top of `grpc-timeout`'s millisecond rung.
const MAX_ANNOUNCED_DEADLINE_MS: u64 = 99_999_999;

/// One unary call in flight: the client that carries its announcement, and the announcement.
pub(crate) struct SeamCall {
    client: BrainServiceClient<SeamChannel>,
    announced: Option<Duration>,
}

impl SeamCall {
    /// Builds one call over `channel`, sending `token` and announcing as much of `deadline` as the
    /// header can carry.
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

    /// The generated client for this call. Cloned because every generated method takes `&mut
    /// self`; clones share the channel, so this costs a pair of `Option`s and an `Arc` bump.
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

/// The part of `deadline` this transport may actually announce: itself, or nothing when the
/// header cannot carry it in an order-preserving unit ([`MAX_ANNOUNCED_DEADLINE_MS`]).
fn announceable(deadline: Option<Duration>) -> Option<Duration> {
    let ceiling = Duration::from_millis(MAX_ANNOUNCED_DEADLINE_MS);
    deadline.filter(|announced| *announced <= ceiling)
}
