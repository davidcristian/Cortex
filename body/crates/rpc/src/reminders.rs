//! Reminder pull-delivery translation for `BrainSeamClient`, the ADR-0025 half of the
//! `body_core::BrainTransport` port.
//!
//! The overlay's pull path: `ListDueReminders` reads what has fired and is still
//! awaiting delivery, `AckReminder` clears one the user dismissed. Thin translation
//! only, exactly as [`crate::sessions`] does it: map the request, await the unary
//! reply, map each row to its typed core value, and let a non-OK gRPC status become a
//! [`TransportError`] through [`crate::status::status_to_error`]. A brain with no
//! schedule backend answers an empty list and `acked=false` rather than a status, so
//! nothing here special-cases it.

use body_core::{DueReminder, TransportError};

use crate::client::SeamChannel;
use crate::generated::brain_service_client::BrainServiceClient;
use crate::generated::{AckReminderRequest, ListDueRemindersRequest};
use crate::status::status_to_error;

/// Lists fired-but-undelivered reminders across every session
/// (`BrainService.ListDueReminders`).
pub(crate) async fn list_due_reminders(
    mut client: BrainServiceClient<SeamChannel>,
) -> Result<Vec<DueReminder>, TransportError> {
    let reply = client
        .list_due_reminders(ListDueRemindersRequest {})
        .await
        .map_err(|status| status_to_error(&status))?
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
    mut client: BrainServiceClient<SeamChannel>,
    reminder_id: String,
) -> Result<bool, TransportError> {
    let reply = client
        .ack_reminder(AckReminderRequest { reminder_id })
        .await
        .map_err(|status| status_to_error(&status))?
        .into_inner();
    Ok(reply.acked)
}
