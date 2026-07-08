//! Session-read translation for `BrainSeamClient`, forming the unary half of the
//! `body_core::BrainTransport` port (ADR-0021).
//!
//! Two read-only calls backing the overlay's chat list / switcher / cycling:
//! `ListSessions` and `GetSessionMessages`. Thin translation only. Map the
//! request, await the unary reply, map each row to its typed core value; a
//! non-OK gRPC status maps the same way `health` does (via
//! [`crate::status::status_to_error`]).

use body_core::{SessionMessage, SessionSummary, TransportError};

use crate::client::SeamChannel;
use crate::generated::brain_service_client::BrainServiceClient;
use crate::generated::{GetSessionMessagesRequest, ListSessionsRequest};
use crate::status::status_to_error;

/// Lists recent chats newest-active first (`BrainService.ListSessions`). At most
/// `limit`; `0` means the brain's default.
pub(crate) async fn list_sessions(
    mut client: BrainServiceClient<SeamChannel>,
    limit: i32,
) -> Result<Vec<SessionSummary>, TransportError> {
    let reply = client
        .list_sessions(ListSessionsRequest { limit })
        .await
        .map_err(|status| status_to_error(&status))?
        .into_inner();
    Ok(reply
        .sessions
        .into_iter()
        .map(|summary| SessionSummary {
            session_id: summary.session_id,
            title: summary.title,
            preview: summary.preview,
            last_activity_unix_ms: summary.last_activity_unix_ms,
        })
        .collect())
}

/// Loads one session's persisted history in append order
/// (`BrainService.GetSessionMessages`). An unknown session is an empty history.
pub(crate) async fn session_messages(
    mut client: BrainServiceClient<SeamChannel>,
    session_id: String,
) -> Result<Vec<SessionMessage>, TransportError> {
    let reply = client
        .get_session_messages(GetSessionMessagesRequest { session_id })
        .await
        .map_err(|status| status_to_error(&status))?
        .into_inner();
    Ok(reply
        .messages
        .into_iter()
        .map(|message| SessionMessage {
            role: message.role,
            text: message.text,
            turn_id: message.turn_id,
            at_unix_ms: message.at_unix_ms,
        })
        .collect())
}
