//! Session translation for `BrainRpcClient`, forming the unary session half of the
//! `body_core::BrainTransport` port.

use body_core::{SessionMessage, SessionSummary, TransportError};

use crate::call::RpcCall;
use crate::generated::{
    DeleteSessionRequest, GetSessionMessagesRequest, ListSessionsRequest, RenameSessionRequest,
    SetSessionHoistedRequest,
};

/// Lists recent chats newest-active first (`BrainService.ListSessions`).
pub(crate) async fn list_sessions(
    call: RpcCall,
    limit: i32,
) -> Result<Vec<SessionSummary>, TransportError> {
    let mut client = call.client();
    let reply = client
        .list_sessions(ListSessionsRequest { limit })
        .await
        .map_err(|status| call.error(&status))?
        .into_inner();
    Ok(reply
        .sessions
        .into_iter()
        .map(|summary| SessionSummary {
            session_id: summary.session_id,
            title: summary.title,
            preview: summary.preview,
            last_activity_unix_ms: summary.last_activity_unix_ms,
            hoisted: summary.hoisted,
        })
        .collect())
}

/// Loads one session's persisted history in append order (`BrainService.GetSessionMessages`).
pub(crate) async fn session_messages(
    call: RpcCall,
    session_id: String,
) -> Result<Vec<SessionMessage>, TransportError> {
    let mut client = call.client();
    let reply = client
        .get_session_messages(GetSessionMessagesRequest { session_id })
        .await
        .map_err(|status| call.error(&status))?
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

/// Renames one chat (`BrainService.RenameSession`).
pub(crate) async fn rename_session(
    call: RpcCall,
    session_id: String,
    title: String,
) -> Result<(), TransportError> {
    call.client()
        .rename_session(RenameSessionRequest { session_id, title })
        .await
        .map_err(|status| call.error(&status))?;
    Ok(())
}

/// Deletes one chat (`BrainService.DeleteSession`).
pub(crate) async fn delete_session(
    call: RpcCall,
    session_id: String,
) -> Result<(), TransportError> {
    call.client()
        .delete_session(DeleteSessionRequest { session_id })
        .await
        .map_err(|status| call.error(&status))?;
    Ok(())
}

/// Hoists or lowers one chat (`BrainService.SetSessionHoisted`).
pub(crate) async fn set_session_hoisted(
    call: RpcCall,
    session_id: String,
    hoisted: bool,
) -> Result<(), TransportError> {
    call.client()
        .set_session_hoisted(SetSessionHoistedRequest {
            session_id,
            hoisted,
        })
        .await
        .map_err(|status| call.error(&status))?;
    Ok(())
}
