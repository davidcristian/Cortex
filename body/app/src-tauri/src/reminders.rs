//! The reminder pull-delivery IPC commands: list what has fired and is still awaiting
//! delivery, and ack what the overlay showed (`bridge/tauriBridge.ts`).

use body_core::{BrainTransport, DueReminder};
use serde::Serialize;

/// The overlay's `DueReminder` (camelCase, matches `bridge/types.ts`).
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireReminder {
    reminder_id: String,
    text: String,
    fired_at_unix_ms: i64,
    recurring: bool,
    tainted: bool,
    session_id: String,
}

impl From<DueReminder> for WireReminder {
    fn from(reminder: DueReminder) -> Self {
        Self {
            reminder_id: reminder.reminder_id,
            text: reminder.text,
            fired_at_unix_ms: reminder.fired_at_unix_ms,
            recurring: reminder.recurring,
            tainted: reminder.tainted,
            session_id: reminder.session_id,
        }
    }
}

/// Lists fired-but-undelivered reminders across every session (`BrainService.ListDueReminders`).
#[tauri::command]
pub async fn list_due_reminders() -> Result<Vec<WireReminder>, String> {
    let client = crate::brain::connect()?;
    let reminders = client
        .list_due_reminders()
        .await
        .map_err(|error| error.to_string())?;
    Ok(reminders.into_iter().map(Into::into).collect())
}

/// Marks the fire a card showed delivered (`BrainService.AckReminder`), named by the card's
/// `firedAtUnixMs`.
#[tauri::command]
pub async fn ack_reminder(reminder_id: String, fired_at_unix_ms: i64) -> Result<bool, String> {
    let client = crate::brain::connect()?;
    client
        .ack_reminder(&reminder_id, fired_at_unix_ms)
        .await
        .map_err(|error| error.to_string())
}
