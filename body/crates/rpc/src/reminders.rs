//! Reminder pull-delivery translation for `BrainSeamClient`, the ADR-0025 half of the
//! `body_core::BrainTransport` port.
//!
//! The overlay's pull path: `ListDueReminders` reads what has fired and is still
//! awaiting delivery, `AckReminder` clears one the user dismissed. Thin translation
//! only, exactly as [`crate::sessions`] does it: map the request, await the unary
//! reply, map each row to its typed core value, and let a non-OK gRPC status become a
//! [`TransportError`] through the [`SeamCall`] the client hands in. A brain with no
//! schedule backend answers an empty list and `acked=false` rather than a status, so
//! nothing here special-cases it.

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

/// Marks one reminder delivered (`BrainService.AckReminder`). `false` is the brain reporting
/// that there was nothing to clear, which is a state rather than a failure.
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
