//! What one outgoing seam call carries: the metadata it is sent with, and the deadline the body
//! told the brain about it.
//!
//! Split from `client.rs` (which owns the connection and the port implementation over it) along
//! the line the courtesy `grpc-timeout` header drew through this adapter (ADR-0024
//! courtesy-header addendum). The seam token is per **connection** and a deadline is per
//! **call**, but both ride the same tonic [`Interceptor`], which is the one place every outgoing
//! request passes through; so an interceptor is now built per call, and everything that decides
//! what a single call looks like on the wire lives here.
//!
//! [`SeamCall`] is that call: a generated client whose interceptor already holds this call's
//! announcement, plus the announcement itself so the *reply* can be read in its light. Both
//! halves are needed. The request half is what the brain reads to stop working on a call nobody
//! is waiting for; the reply half is what turns a brain-sent `DEADLINE_EXCEEDED` into the
//! [`TransportError::Timeout`] the body's own clock produces, a deadline announced and a deadline
//! enforced being one event seen from two ends.
//!
//! Nothing here decides how long a call may take. That is the core's
//! `RetryPlan::announced_deadline_for`, and this module only refuses what the wire cannot carry
//! without reordering the two clocks.

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
///
/// The token is per connection and the deadline is per call, which is why an interceptor is
/// built per call rather than per client: `Request::set_timeout` is the only way to put
/// `grpc-timeout` on the wire, and this is the one place every outgoing request passes through.
///
/// Deliberately NOT `Debug`: it holds the secret, and tonic's
/// `InterceptedService` debug-prints interceptors by type name only. The
/// token cannot reach a log through a `{:?}` of the client either.
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
///
/// The header's value is at most 8 digits plus a unit, so tonic walks a ladder of units looking
/// for the most precise one that fits and **truncates** onto it (`duration_to_grpc_timeout`,
/// tonic 0.14): nanoseconds below 0.1 s, microseconds below 100 s, milliseconds up to this
/// bound, whole seconds above it, and a panic past the coarsest rung some 11,415 years out.
///
/// **The filter sits at the millisecond rung and not at the panic**, because a panic is not the
/// only way a courtesy can cost the call it is a courtesy to. Announcing arms tonic's own clock
/// from what the header **decodes** to, so the truncation is grace margin spent: under this
/// bound it costs less than a millisecond and `ANNOUNCED_DEADLINE_GRACE_MS` swallows it, and over
/// it the step is a whole second, four times that margin. With `announced = enforced + 250 ms`
/// the decoded value then falls *below* the enforced bound for 749 of every 1000 millisecond
/// values a deadline can take, by as much as 749 ms, and tonic's timer wins the race the margin
/// exists to make it lose. Its expiry classifies `Connection` (`crate::status`), which is
/// retryable, so one abandoned call would become three.
///
/// An announcement past this is dropped rather than clamped or rounded. Clamping would announce a
/// deadline *shorter* than the one the core enforces, which is that same race run on purpose;
/// rounding up onto the ladder ourselves would re-implement a private encoder free to move under
/// a version bump. Dropping costs the brain a hint and costs the call nothing, the core's own
/// bound being what actually ends it (ADR-0024 unit-ladder addendum).
///
/// A count of milliseconds rather than a [`Duration`] for the reason `ANNOUNCED_DEADLINE_GRACE_MS`
/// is one: `scripts/crosscheck.py` ties this to the contract that quotes it by reading this
/// declaration, which it can do for an integer and cannot for a constructor call.
const MAX_ANNOUNCED_DEADLINE_MS: u64 = 99_999_999;

/// One unary call in flight: the client that carries its announcement, and the announcement.
pub(crate) struct SeamCall {
    client: BrainServiceClient<SeamChannel>,
    announced: Option<Duration>,
}

impl SeamCall {
    /// Builds one call over `channel`, sending `token` and announcing as much of `deadline` as
    /// the header can carry. `deadline` is `None` for a call that announces nothing: `Converse`,
    /// whose plan gives it no deadline, or any client that was never told a plan to read one out
    /// of.
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
///
/// The comparison is against whole milliseconds, so it also refuses the sliver between the rung's
/// ceiling and the next whole millisecond, which tonic would still spell in milliseconds. That
/// sliver is unreachable from a plan: every knob the shell parses is a count of milliseconds and
/// the grace added to it is another, so an announcement always lands on a millisecond.
fn announceable(deadline: Option<Duration>) -> Option<Duration> {
    let ceiling = Duration::from_millis(MAX_ANNOUNCED_DEADLINE_MS);
    deadline.filter(|announced| *announced <= ceiling)
}
