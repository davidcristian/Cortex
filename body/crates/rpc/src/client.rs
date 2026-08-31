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
//!
//! The deadline is announced here and enforced in the core (ADR-0024 courtesy-header addendum).
//! A client told which `RetryPlan` the decorator above it runs ([`BrainSeamClient::announcing`])
//! puts each call's `grpc-timeout` on the wire, so a brain still working on a call the body has
//! abandoned can stop. The header is a courtesy rather than a second enforcement point, and it
//! is longer than the bound the core keeps by the plan's grace margin, because tonic arms a
//! clock of its own from that same header and the core's bound has to expire first. The client
//! is therefore rebuilt per call ([`SeamCall`]), which is the only way a per-call value reaches
//! an interceptor built once per connection, and it is why the channel and the token are held
//! here rather than folded into one generated client.

use std::fmt;

use body_core::{
    BrainTransport, ConfirmDecision, DueReminder, RetryPlan, SeamHealth, SeamMethod,
    SessionMessage, SessionSummary, TransportError, TurnEvent,
};
use futures_core::Stream;
use tonic::metadata::{Ascii, MetadataValue};
use tonic::transport::Channel;

use crate::call::SeamCall;
use crate::generated::HealthRequest;
use crate::status::error_chain;

/// gRPC client for `BrainService`, connected over a tonic [`Channel`].
///
/// Cheap to clone: clones share the underlying HTTP/2 connection. The generated client is built
/// per call instead of held, because the token interceptor also carries that call's announced
/// deadline (see the module docs), so what is held is the channel, the token, and the plan the
/// announcement is read out of.
#[derive(Clone)]
pub struct BrainSeamClient {
    channel: Channel,
    token: Option<MetadataValue<Ascii>>,
    plan: Option<RetryPlan>,
}

/// The token is a shared secret (ADR-0016) and the only field here that must never reach a log,
/// so this prints whether it is present and never its value. It is written out rather than
/// derived for that reason, since the derive printed the `MetadataValue` itself.
impl fmt::Debug for BrainSeamClient {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("BrainSeamClient")
            .field("channel", &self.channel)
            .field("token", &self.token.as_ref().map(|_| "<redacted>"))
            .field("plan", &self.plan)
            .finish()
    }
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

    /// Like [`BrainSeamClient::connect_with_token`], but over a lazy channel
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

    /// Announces each call's deadline to the brain as `grpc-timeout`, read per method out of
    /// `plan` (ADR-0024 courtesy-header addendum). Without this the client sends no header at
    /// all, which is what every constructor above returns.
    ///
    /// `plan` must be the same plan the `RetryingTransport` above this client enforces, and the
    /// shell's `seam::connect()` passes one value to both for that reason. The header is the
    /// plan's `announced_deadline_for`, which is strictly longer than the `deadline_for` the core
    /// keeps, so the two clocks the announcement starts are ordered: the core's own bound expires
    /// first and the call fails `TransportError::Timeout`, which is terminal. Were tonic's to
    /// expire first the call would fail `TransportError::Connection`, which is retryable and
    /// would amplify load against a brain already too slow to answer.
    #[must_use]
    pub const fn announcing(mut self, plan: RetryPlan) -> Self {
        self.plan = Some(plan);
        self
    }

    /// Wraps a ready channel in the client, announcing nothing until [`Self::announcing`] says
    /// otherwise.
    const fn with_token(channel: Channel, token: Option<MetadataValue<Ascii>>) -> Self {
        Self {
            channel,
            token,
            plan: None,
        }
    }

    /// One call's generated client, whose interceptor carries the seam token and this method's
    /// announced deadline, paired with that announcement for the reply mapping ([`SeamCall`]).
    fn call(&self, method: SeamMethod) -> SeamCall {
        SeamCall::new(
            self.channel.clone(),
            self.token.clone(),
            self.plan
                .and_then(|plan| plan.announced_deadline_for(method)),
        )
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
        let call = self.call(SeamMethod::Health);
        let reply = call
            .client()
            .health(HealthRequest {})
            .await
            .map_err(|status| call.error(&status))?
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
        // The one method that announces nothing, because it is the one the plan gives no
        // deadline: a turn is long by design, and a header would hand tonic a clock to end it
        // with. Its statuses therefore map through the classifier that reads no announcement.
        crate::converse::converse_turn(
            self.call(SeamMethod::Converse).client(),
            session_id.to_owned(),
            text.to_owned(),
            decisions,
        )
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        crate::sessions::list_sessions(self.call(SeamMethod::ListSessions), limit).await
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        crate::sessions::session_messages(
            self.call(SeamMethod::SessionMessages),
            session_id.to_owned(),
        )
        .await
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        crate::reminders::list_due_reminders(self.call(SeamMethod::ListDueReminders)).await
    }

    async fn ack_reminder(&self, reminder_id: &str) -> Result<bool, TransportError> {
        crate::reminders::ack_reminder(self.call(SeamMethod::AckReminder), reminder_id.to_owned())
            .await
    }

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        crate::sessions::rename_session(
            self.call(SeamMethod::RenameSession),
            session_id.to_owned(),
            title.to_owned(),
        )
        .await
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        crate::sessions::delete_session(self.call(SeamMethod::DeleteSession), session_id.to_owned())
            .await
    }

    async fn set_session_pinned(
        &self,
        session_id: &str,
        pinned: bool,
    ) -> Result<(), TransportError> {
        crate::sessions::set_session_pinned(
            self.call(SeamMethod::SetSessionPinned),
            session_id.to_owned(),
            pinned,
        )
        .await
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        crate::preferences::get_preferences(self.call(SeamMethod::GetPreferences)).await
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        crate::preferences::set_preference(
            self.call(SeamMethod::SetPreference),
            key.to_owned(),
            value.to_owned(),
        )
        .await
    }
}
