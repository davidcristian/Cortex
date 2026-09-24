//! [`BrainRpcClient`] is the gRPC adapter behind `body_core::BrainTransport`.
//!
//! Translation only: every failure to reach the brain becomes [`TransportError::Connection`],
//! and a non-OK status the brain reported becomes [`TransportError::Rpc`]. There are no retries.

use std::fmt;

use body_core::{
    BrainTransport, ConfirmDecision, DueReminder, RetryPlan, RpcHealth, RpcMethod, SessionMessage,
    SessionSummary, TransportError, TurnEvent,
};
use futures_core::Stream;
use tonic::metadata::{Ascii, MetadataValue};
use tonic::transport::Channel;

use crate::call::RpcCall;
use crate::generated::HealthRequest;
use crate::status::error_chain;

/// gRPC client for `BrainService`, connected over a tonic [`Channel`].
#[derive(Clone)]
pub struct BrainRpcClient {
    channel: Channel,
    token: Option<MetadataValue<Ascii>>,
    plan: Option<RetryPlan>,
}

/// The token is a shared secret and must never reach a log, so this prints whether it is present
/// and never its value.
impl fmt::Debug for BrainRpcClient {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("BrainRpcClient")
            .field("channel", &self.channel)
            .field("token", &self.token.as_ref().map(|_| "<redacted>"))
            .field("plan", &self.plan)
            .finish()
    }
}

impl BrainRpcClient {
    /// Connects to the brain at `addr`, for example `http://127.0.0.1:50051`, sending no token.
    ///
    /// # Errors
    ///
    /// [`TransportError::Connection`] when `addr` is not a valid URI or cannot be reached.
    pub async fn connect(addr: &str) -> Result<Self, TransportError> {
        Self::connect_with_token(addr, None).await
    }

    /// Like [`BrainRpcClient::connect`], also sending `token` as `x-cortex-seam-token` metadata.
    ///
    /// # Errors
    ///
    /// As `connect`, and also when `token` is not valid ASCII metadata.
    pub async fn connect_with_token(
        addr: &str,
        token: Option<&str>,
    ) -> Result<Self, TransportError> {
        let token = parse_rpc_token(token)?;
        let channel = endpoint(addr)?
            .connect()
            .await
            .map_err(|err| TransportError::Connection(error_chain(&err)))?;
        Ok(Self::with_token(channel, token))
    }

    /// As `connect_with_token`, over a lazy channel that reconnects on each call.
    ///
    /// # Errors
    ///
    /// [`TransportError::Connection`] for a bad URI or a token that is not valid ASCII metadata.
    pub fn connect_lazy_with_token(
        addr: &str,
        token: Option<&str>,
    ) -> Result<Self, TransportError> {
        let token = parse_rpc_token(token)?;
        Ok(Self::with_token(endpoint(addr)?.connect_lazy(), token))
    }

    /// Announces each call's deadline to the brain as `grpc-timeout`, read per method out of
    /// `plan`, which must be the same plan the retry decorator above this client enforces.
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

    /// One call's generated client, whose interceptor holds the shared token and this method's
    /// announced deadline, paired with that announcement for the reply mapping.
    fn call(&self, method: RpcMethod) -> RpcCall {
        RpcCall::new(
            self.channel.clone(),
            self.token.clone(),
            self.plan
                .and_then(|plan| plan.announced_deadline_for(method)),
        )
    }
}

/// Parses the optional token into ASCII metadata, or [`TransportError::Connection`] when it is
/// not valid ASCII.
fn parse_rpc_token(token: Option<&str>) -> Result<Option<MetadataValue<Ascii>>, TransportError> {
    token
        .map(|value| {
            value.parse::<MetadataValue<Ascii>>().map_err(|err| {
                TransportError::Connection(format!("invalid token: {}", error_chain(&err)))
            })
        })
        .transpose()
}

/// Builds the tonic endpoint for `addr`, mapping an invalid URI to [`TransportError::Connection`].
fn endpoint(addr: &str) -> Result<tonic::transport::Endpoint, TransportError> {
    Channel::from_shared(addr.to_owned())
        .map_err(|err| TransportError::Connection(error_chain(&err)))
}

impl BrainTransport for BrainRpcClient {
    async fn health(&self) -> Result<RpcHealth, TransportError> {
        let call = self.call(RpcMethod::Health);
        let reply = call
            .client()
            .health(HealthRequest {})
            .await
            .map_err(|status| call.error(&status))?
            .into_inner();
        Ok(RpcHealth {
            ready: reply.ready,
            detail: reply.detail,
            notes: reply.notes.into_iter().map(|note| note.text).collect(),
        })
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        crate::converse::converse_turn(
            self.call(RpcMethod::Converse).client(),
            session_id.to_owned(),
            text.to_owned(),
            decisions,
        )
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        crate::sessions::list_sessions(self.call(RpcMethod::ListSessions), limit).await
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        crate::sessions::session_messages(
            self.call(RpcMethod::SessionMessages),
            session_id.to_owned(),
        )
        .await
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        crate::reminders::list_due_reminders(self.call(RpcMethod::ListDueReminders)).await
    }

    async fn ack_reminder(
        &self,
        reminder_id: &str,
        fired_at_unix_ms: i64,
    ) -> Result<bool, TransportError> {
        crate::reminders::ack_reminder(
            self.call(RpcMethod::AckReminder),
            reminder_id.to_owned(),
            fired_at_unix_ms,
        )
        .await
    }

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        crate::sessions::rename_session(
            self.call(RpcMethod::RenameSession),
            session_id.to_owned(),
            title.to_owned(),
        )
        .await
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        crate::sessions::delete_session(self.call(RpcMethod::DeleteSession), session_id.to_owned())
            .await
    }

    async fn set_session_hoisted(
        &self,
        session_id: &str,
        hoisted: bool,
    ) -> Result<(), TransportError> {
        crate::sessions::set_session_hoisted(
            self.call(RpcMethod::SetSessionHoisted),
            session_id.to_owned(),
            hoisted,
        )
        .await
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        crate::preferences::get_preferences(self.call(RpcMethod::GetPreferences)).await
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        crate::preferences::set_preference(
            self.call(RpcMethod::SetPreference),
            key.to_owned(),
            value.to_owned(),
        )
        .await
    }
}
