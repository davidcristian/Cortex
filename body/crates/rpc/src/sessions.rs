//! Session translation for `BrainSeamClient`, forming the unary session half of the
//! `body_core::BrainTransport` port (ADR-0021).
//!
//! The calls backing the overlay's chat list / switcher / cycling and the list controls: the
//! read-only `ListSessions` and `GetSessionMessages`, and the user-driven writes `RenameSession`,
//! `DeleteSession`, and `SetSessionPinned`. Thin translation only. Map the request, await the unary
//! reply, map each row to its typed core value; a non-OK gRPC status maps the same way `health`
//! does (via [`crate::status::status_to_error`]).

use body_core::{SessionMessage, SessionSummary, TransportError};

use crate::client::SeamChannel;
use crate::generated::brain_service_client::BrainServiceClient;
use crate::generated::{
    DeleteSessionRequest, GetSessionMessagesRequest, ListSessionsRequest, RenameSessionRequest,
    SetSessionPinnedRequest,
};
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
            pinned: summary.pinned,
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

/// Renames one chat (`BrainService.RenameSession`, ADR-0021 management addendum). A user-driven
/// catalog write: `title` is the new display label, `""` clears any override. The reply is a
/// bare acknowledgement, so on success there is nothing to map back; a non-OK gRPC status maps
/// via [`status_to_error`] (a store failure surfaces as `TransportError::Rpc` `Unavailable`).
pub(crate) async fn rename_session(
    mut client: BrainServiceClient<SeamChannel>,
    session_id: String,
    title: String,
) -> Result<(), TransportError> {
    client
        .rename_session(RenameSessionRequest { session_id, title })
        .await
        .map_err(|status| status_to_error(&status))?;
    Ok(())
}

/// Deletes one chat (`BrainService.DeleteSession`, ADR-0021 management addendum). A user-driven
/// destructive write: the brain hard-deletes the transcript and cascades to the session's private
/// memories. The reply is a bare acknowledgement, so on success there is nothing to map back; a
/// non-OK gRPC status maps via [`status_to_error`] (a store/memory failure surfaces as `Unavailable`).
pub(crate) async fn delete_session(
    mut client: BrainServiceClient<SeamChannel>,
    session_id: String,
) -> Result<(), TransportError> {
    client
        .delete_session(DeleteSessionRequest { session_id })
        .await
        .map_err(|status| status_to_error(&status))?;
    Ok(())
}

/// Pins or unpins one chat (`BrainService.SetSessionPinned`, ADR-0021 pinning addendum). A
/// user-driven catalog write: `pinned` is the target state, and a pinned chat is unioned into
/// `ListSessions` regardless of recency. The reply is a bare acknowledgement, so on success there
/// is nothing to map back; a non-OK gRPC status maps via [`status_to_error`] (a store failure
/// surfaces as `TransportError::Rpc` `Unavailable`).
pub(crate) async fn set_session_pinned(
    mut client: BrainServiceClient<SeamChannel>,
    session_id: String,
    pinned: bool,
) -> Result<(), TransportError> {
    client
        .set_session_pinned(SetSessionPinnedRequest { session_id, pinned })
        .await
        .map_err(|status| status_to_error(&status))?;
    Ok(())
}
