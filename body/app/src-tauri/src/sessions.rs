//! The read-only session IPC commands (ADR-0021): list recent chats and load one
//! chat's history for the overlay's switcher / cycling (`bridge/tauriBridge.ts`).
//!
//! Thin glue. Connect the resilient read transport (`seam::connect`, a
//! `RetryingTransport` over `body_rpc`; ADR-0024), make the unary call, and map each row to a
//! camelCase wire struct the overlay's `SessionSummary` / `SessionMessage` types expect. All
//! seam logic lives in `body_rpc`; the retry/backoff logic in `body_core`.

use body_core::{BrainTransport, SessionMessage, SessionSummary};
use serde::Serialize;

/// The overlay's `SessionSummary` (camelCase, matches `bridge/types.ts`).
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireSummary {
    session_id: String,
    title: String,
    preview: String,
    last_activity_unix_ms: i64,
}

impl From<SessionSummary> for WireSummary {
    fn from(summary: SessionSummary) -> Self {
        Self {
            session_id: summary.session_id,
            title: summary.title,
            preview: summary.preview,
            last_activity_unix_ms: summary.last_activity_unix_ms,
        }
    }
}

/// The overlay's `SessionMessage` (camelCase, matches `bridge/types.ts`).
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireMessage {
    role: String,
    text: String,
    turn_id: String,
    at_unix_ms: i64,
}

impl From<SessionMessage> for WireMessage {
    fn from(message: SessionMessage) -> Self {
        Self {
            role: message.role,
            text: message.text,
            turn_id: message.turn_id,
            at_unix_ms: message.at_unix_ms,
        }
    }
}

/// Lists recent chats newest-active first (`BrainService.ListSessions`). A transient
/// unreachable brain is retried with backoff by the resilient transport (ADR-0024) before
/// the error surfaces to the overlay bridge's `.catch`.
#[tauri::command]
pub async fn list_sessions(limit: i32) -> Result<Vec<WireSummary>, String> {
    let client = crate::seam::connect()?;
    let sessions = client
        .list_sessions(limit)
        .await
        .map_err(|error| error.to_string())?;
    Ok(sessions.into_iter().map(Into::into).collect())
}

/// Loads one session's persisted history (`BrainService.GetSessionMessages`).
#[tauri::command]
pub async fn session_messages(session_id: String) -> Result<Vec<WireMessage>, String> {
    let client = crate::seam::connect()?;
    let messages = client
        .session_messages(&session_id)
        .await
        .map_err(|error| error.to_string())?;
    Ok(messages.into_iter().map(Into::into).collect())
}

/// Renames one chat (`BrainService.RenameSession`, ADR-0021 management addendum): the overlay's
/// user-driven relabel of a chat in its list. `title` is the new display label; `""` clears any
/// custom/brain-generated title so the switcher falls back to the derived one. A write, so the
/// resilient transport makes exactly one attempt (`SeamMethod::RenameSession` is not repeatable);
/// a transient failure surfaces to the overlay bridge's `.catch` rather than risking a re-label.
#[tauri::command]
pub async fn rename_session(session_id: String, title: String) -> Result<(), String> {
    let client = crate::seam::connect()?;
    client
        .rename_session(&session_id, &title)
        .await
        .map_err(|error| error.to_string())
}

/// Deletes one chat (`BrainService.DeleteSession`, ADR-0021 management addendum): the overlay's
/// user-driven destructive removal, fired only after an overlay-local confirm. The brain
/// hard-deletes the transcript and cascades to the chat's private memories. A destructive write, so
/// the resilient transport makes exactly one attempt (`SeamMethod::DeleteSession` is not
/// repeatable); a transient failure surfaces to the overlay bridge's `.catch` rather than risking a
/// silent second destroy.
#[tauri::command]
pub async fn delete_session(session_id: String) -> Result<(), String> {
    let client = crate::seam::connect()?;
    client
        .delete_session(&session_id)
        .await
        .map_err(|error| error.to_string())
}
