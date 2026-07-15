//! [`BrainSeamClient`] is the gRPC adapter behind `body_core::BrainTransport`.
//!
//! A thin translation layer only (AGENTS.md): every failure to reach the
//! brain, whether a bad address, a refused dial, or a transport failure after the
//! channel connected (tonic surfaces those as statuses synthesized from a
//! client-local `tonic::transport::Error`), maps to
//! [`TransportError::Connection`]; non-OK statuses genuinely reported by the
//! brain map to [`TransportError::Rpc`]. No business logic and no retries: the
//! bounded-retry policy lives in `body_core`'s `RetryingTransport` decorator
//! over this adapter (ADR-0024), and [`BrainSeamClient::connect_lazy_with_token`]
//! gives it a reconnecting channel to retry over.

use body_core::{
    BrainTransport, ConfirmDecision, DueReminder, SeamHealth, SessionMessage, SessionSummary,
    TransportError, TurnEvent,
};
use futures_core::Stream;
use tonic::metadata::{Ascii, MetadataValue};
use tonic::service::Interceptor;
use tonic::service::interceptor::InterceptedService;
use tonic::transport::Channel;
use tonic::{Request, Status};

use crate::generated::HealthRequest;
use crate::generated::brain_service_client::BrainServiceClient;
use crate::status::{error_chain, status_to_error};

/// The metadata key the seam token travels under (ADR-0016; lowercase per gRPC).
const SEAM_TOKEN_HEADER: &str = "x-cortex-seam-token";

/// The service every seam call runs over: tonic's [`Channel`] fronted by the
/// token interceptor (which is a pass-through when no token is configured).
pub(crate) type SeamChannel = InterceptedService<Channel, SeamTokenInterceptor>;

/// Attaches the shared seam token to every outgoing request (ADR-0016).
///
/// Deliberately NOT `Debug`: it holds the secret, and tonic's
/// `InterceptedService` debug-prints interceptors by type name only. The
/// token cannot reach a log through a `{:?}` of the client either.
#[derive(Clone)]
pub(crate) struct SeamTokenInterceptor {
    token: Option<MetadataValue<Ascii>>,
}

impl Interceptor for SeamTokenInterceptor {
    fn call(&mut self, mut request: Request<()>) -> Result<Request<()>, Status> {
        if let Some(token) = &self.token {
            request
                .metadata_mut()
                .insert(SEAM_TOKEN_HEADER, token.clone());
        }
        Ok(request)
    }
}

/// gRPC client for `BrainService`, connected over a tonic [`Channel`].
///
/// Cheap to clone: clones share the underlying HTTP/2 connection.
#[derive(Clone, Debug)]
pub struct BrainSeamClient {
    inner: BrainServiceClient<SeamChannel>,
}

impl BrainSeamClient {
    /// Connects to the brain at `addr`, e.g. `http://127.0.0.1:50051`
    /// (the `CORTEX_BRAIN_ADDR` default, see `docs/modules/body-rpc.md`),
    /// sending no seam token. This suits a brain with auth disabled.
    ///
    /// # Errors
    ///
    /// Returns [`TransportError::Connection`] when `addr` is not a valid URI
    /// or the endpoint cannot be reached; the message folds the full cause
    /// chain, e.g. `transport error: tcp connect error: Connection refused
    /// (os error 111)`.
    pub async fn connect(addr: &str) -> Result<Self, TransportError> {
        Self::connect_with_token(addr, None).await
    }

    /// Like [`BrainSeamClient::connect`], additionally attaching `token` as
    /// `x-cortex-seam-token` metadata on every call when `Some`. This is the shared
    /// secret a `CORTEX_SEAM_TOKEN`-protected brain requires (ADR-0016). The
    /// caller reads it from env; it is never logged here.
    ///
    /// # Errors
    ///
    /// [`TransportError::Connection`] as for `connect`, and also when `token`
    /// is not valid ASCII metadata (gRPC cannot carry it).
    pub async fn connect_with_token(
        addr: &str,
        token: Option<&str>,
    ) -> Result<Self, TransportError> {
        let token = parse_seam_token(token)?;
        let channel = endpoint(addr)?
            .connect()
            .await
            .map_err(|err| TransportError::Connection(error_chain(&err)))?;
        Ok(Self::with_token(channel, token))
    }

    /// Like [`BrainSeamClient::connect_with_token`], but over a **lazy** channel
    /// (`Channel::connect_lazy`): construction never dials, so it only fails on a
    /// bad URI or a non-ASCII token (never on reachability), and each RPC
    /// (re)establishes the connection on demand. This is the channel the
    /// `RetryingTransport` decorator retries over: a call against a briefly-down
    /// brain fails [`TransportError::Connection`], the decorator backs off, and
    /// tonic reconnects transparently when the brain returns (ADR-0024).
    ///
    /// # Errors
    ///
    /// [`TransportError::Connection`] when `addr` is not a valid URI or `token`
    /// is not valid ASCII metadata.
    pub fn connect_lazy_with_token(
        addr: &str,
        token: Option<&str>,
    ) -> Result<Self, TransportError> {
        let token = parse_seam_token(token)?;
        Ok(Self::with_token(endpoint(addr)?.connect_lazy(), token))
    }

    /// Wraps a ready channel in the client with the token interceptor attached.
    fn with_token(channel: Channel, token: Option<MetadataValue<Ascii>>) -> Self {
        Self {
            inner: BrainServiceClient::with_interceptor(channel, SeamTokenInterceptor { token }),
        }
    }
}

/// Parses the optional seam token into gRPC-safe ASCII metadata (ADR-0016), or
/// [`TransportError::Connection`] if it is not valid ASCII the wire can carry.
fn parse_seam_token(token: Option<&str>) -> Result<Option<MetadataValue<Ascii>>, TransportError> {
    token
        .map(|value| {
            value.parse::<MetadataValue<Ascii>>().map_err(|err| {
                TransportError::Connection(format!("invalid seam token: {}", error_chain(&err)))
            })
        })
        .transpose()
}

/// Builds the tonic endpoint for `addr`, mapping an invalid URI to
/// [`TransportError::Connection`]. Shared by the eager and lazy constructors.
fn endpoint(addr: &str) -> Result<tonic::transport::Endpoint, TransportError> {
    Channel::from_shared(addr.to_owned())
        .map_err(|err| TransportError::Connection(error_chain(&err)))
}

impl BrainTransport for BrainSeamClient {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        let reply = self
            .inner
            .clone()
            .health(HealthRequest {})
            .await
            .map_err(|status| status_to_error(&status))?
            .into_inner();
        Ok(SeamHealth {
            ready: reply.ready,
            detail: reply.detail,
        })
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        crate::converse::converse_turn(
            self.inner.clone(),
            session_id.to_owned(),
            text.to_owned(),
            decisions,
        )
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        crate::sessions::list_sessions(self.inner.clone(), limit).await
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        crate::sessions::session_messages(self.inner.clone(), session_id.to_owned()).await
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        crate::reminders::list_due_reminders(self.inner.clone()).await
    }

    async fn ack_reminder(&self, reminder_id: &str) -> Result<bool, TransportError> {
        crate::reminders::ack_reminder(self.inner.clone(), reminder_id.to_owned()).await
    }
}
