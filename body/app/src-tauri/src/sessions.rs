//! The read-only session IPC commands (ADR-0021): list recent chats and load one
//! chat's history for the overlay's switcher / cycling (`bridge/tauriBridge.ts`).
//!
//! Thin glue. Connect a `BrainSeamClient` (gated `body_rpc`), make the unary call,
//! and map each row to a camelCase wire struct the overlay's `SessionSummary` /
//! `SessionMessage` types expect. All seam logic lives in `body_rpc`.

use body_core::{BrainTransport, SessionMessage, SessionSummary};
use body_rpc::BrainSeamClient;
use serde::Serialize;

/// Default brain seam address (matches `body_rpc`); override with `CORTEX_BRAIN_ADDR`.
const DEFAULT_ADDR: &str = "http://127.0.0.1:50051";

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

/// Connects a seam client, reading the address + optional token from the env
/// (the same knobs `converse` uses; ADR-0016). A dial failure surfaces as the
/// command's `Err`, which the overlay bridge's `.catch` handles.
async fn connect() -> Result<BrainSeamClient, String> {
    let addr = std::env::var("CORTEX_BRAIN_ADDR").unwrap_or_else(|_| DEFAULT_ADDR.to_owned());
    let token = std::env::var("CORTEX_SEAM_TOKEN")
        .ok()
        .filter(|token| !token.is_empty());
    BrainSeamClient::connect_with_token(&addr, token.as_deref())
        .await
        .map_err(|error| error.to_string())
}

/// Lists recent chats newest-active first (`BrainService.ListSessions`).
#[tauri::command]
pub async fn list_sessions(limit: i32) -> Result<Vec<WireSummary>, String> {
    let client = connect().await?;
    let sessions = client
        .list_sessions(limit)
        .await
        .map_err(|error| error.to_string())?;
    Ok(sessions.into_iter().map(Into::into).collect())
}

/// Loads one session's persisted history (`BrainService.GetSessionMessages`).
#[tauri::command]
pub async fn session_messages(session_id: String) -> Result<Vec<WireMessage>, String> {
    let client = connect().await?;
    let messages = client
        .session_messages(&session_id)
        .await
        .map_err(|error| error.to_string())?;
    Ok(messages.into_iter().map(Into::into).collect())
}
