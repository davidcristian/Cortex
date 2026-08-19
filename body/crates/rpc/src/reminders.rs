//! Reminder pull-delivery translation for `BrainSeamClient`, the ADR-0025 half of the
//! `body_core::BrainTransport` port.

use body_core::{DueReminder, TransportError};

use crate::call::SeamCall;
use crate::generated::{AckReminderRequest, ListDueRemindersRequest};

/// Lists fired-but-undelivered reminders across every session
/// (`BrainService.ListDueReminders`).
pub(crate) async fn list_due_reminders(call: SeamCall) -> Result<Vec<DueReminder>, TransportError> {
    let mut client = call.client();
    let reply = client
        .list_due_reminders(ListDueRemindersRequest {})
        .await
        .map_err(|status| call.error(&status))?
        .into_inner();
    Ok(reply
        .reminders
        .into_iter()
        .map(|reminder| DueReminder {
            reminder_id: reminder.reminder_id,
            text: reminder.text,
            fired_at_unix_ms: reminder.fired_at_unix_ms,
            recurring: reminder.recurring,
            tainted: reminder.tainted,
            session_id: reminder.session_id,
        })
        .collect())
}

/// Marks one reminder delivered (`BrainService.AckReminder`). `false` is the brain
/// reporting there was nothing to clear, not a failure.
pub(crate) async fn ack_reminder(
    call: SeamCall,
    reminder_id: String,
) -> Result<bool, TransportError> {
    let mut client = call.client();
    let reply = client
        .ack_reminder(AckReminderRequest { reminder_id })
        .await
        .map_err(|status| call.error(&status))?
        .into_inner();
    Ok(reply.acked)
}
