//! The read-only session IPC commands: list recent chats and load one chat's history for
//! the overlay's switcher / cycling (`bridge/tauriBridge.ts`).

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
    pinned: bool,
}

impl From<SessionSummary> for WireSummary {
    fn from(summary: SessionSummary) -> Self {
        Self {
            session_id: summary.session_id,
            title: summary.title,
            preview: summary.preview,
            last_activity_unix_ms: summary.last_activity_unix_ms,
            pinned: summary.pinned,
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

/// Lists recent chats newest-active first (`BrainService.ListSessions`).
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

/// Renames one chat (`BrainService.RenameSession`): the overlay's user-driven
/// relabel of a chat in its list.
#[tauri::command]
pub async fn rename_session(session_id: String, title: String) -> Result<(), String> {
    let client = crate::seam::connect()?;
    client
        .rename_session(&session_id, &title)
        .await
        .map_err(|error| error.to_string())
}

/// Deletes one chat (`BrainService.DeleteSession`): the overlay's user-driven
/// destructive removal, fired only after an overlay-local confirm.
#[tauri::command]
pub async fn delete_session(session_id: String) -> Result<(), String> {
    let client = crate::seam::connect()?;
    client
        .delete_session(&session_id)
        .await
        .map_err(|error| error.to_string())
}

/// Sets or clears the `pinned` mark on one chat, from the overlay's toggle.
#[tauri::command]
pub async fn set_session_pinned(session_id: String, pinned: bool) -> Result<(), String> {
    let client = crate::seam::connect()?;
    client
        .set_session_pinned(&session_id, pinned)
        .await
        .map_err(|error| error.to_string())
}
