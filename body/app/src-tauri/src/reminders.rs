//! The reminder pull-delivery IPC commands (ADR-0025): list what has fired and is still
//! awaiting delivery, and ack what the overlay showed (`bridge/tauriBridge.ts`).
//!
//! Thin glue, exactly as [`crate::sessions`] does it. Connect the resilient read transport
//! (`seam::connect`, a `RetryingTransport` over `body_rpc`; ADR-0024), make the unary call, and
//! map each row to a camelCase wire struct the overlay's `DueReminder` type expects. The retry
//! split lives in `body_core`: the list is idempotent and retried, the ack is not.
//!
//! A brain with no schedule backend answers an empty list and `acked = false` rather than an
//! error, so neither command has a mode of its own for it.

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

/// Lists fired-but-undelivered reminders across every session
/// (`BrainService.ListDueReminders`). The overlay calls this each time it opens.
#[tauri::command]
pub async fn list_due_reminders() -> Result<Vec<WireReminder>, String> {
    let client = crate::seam::connect()?;
    let reminders = client
        .list_due_reminders()
        .await
        .map_err(|error| error.to_string())?;
    Ok(reminders.into_iter().map(Into::into).collect())
}

/// Marks one reminder delivered (`BrainService.AckReminder`). `false` is the brain reporting
/// there was nothing to clear, not a failure; the overlay dismisses optimistically either way
/// and re-reads on the next open, which is what makes an unretried ack safe.
#[tauri::command]
pub async fn ack_reminder(reminder_id: String) -> Result<bool, String> {
    let client = crate::seam::connect()?;
    client
        .ack_reminder(&reminder_id)
        .await
        .map_err(|error| error.to_string())
}
