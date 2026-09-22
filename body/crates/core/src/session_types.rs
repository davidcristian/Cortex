//! Typed core mirrors of the session-catalog and reminder wire values.

/// One recent chat as the overlay's switcher shows it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionSummary {
    /// The chat's session id (its identity for loading history / cycling).
    pub session_id: String,
    /// Derived title: the first user message, one line, truncated.
    pub title: String,
    /// Derived one-line preview: the last message's text, truncated.
    pub preview: String,
    /// Last-activity time as unix-milliseconds, for a relative timestamp.
    pub last_activity_unix_ms: i64,
    /// Whether the user hoisted this chat.
    pub hoisted: bool,
}

/// One persisted message in a session's history.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionMessage {
    /// `"user"` or `"assistant"` are the only persisted roles.
    pub role: String,
    /// The message text.
    pub text: String,
    /// The turn this message belongs to (user turn + its assistant reply share it).
    pub turn_id: String,
    /// Authoring time as unix-milliseconds.
    pub at_unix_ms: i64,
}

/// One fired-but-undelivered reminder awaiting the overlay.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DueReminder {
    /// The reminder's id, which is what [`crate::transport::BrainTransport::ack_reminder`] acks.
    pub reminder_id: String,
    /// What to remind the user of; display-only, and inert (see the type docs).
    pub text: String,
    /// When it became deliverable, as unix-milliseconds; the ack names the fire by it.
    pub fired_at_unix_ms: i64,
    /// Whether the series recurs (a one-shot is gone once acked).
    pub recurring: bool,
    /// Untrusted provenance: the text came from content the brain does not trust.
    pub tainted: bool,
    /// The chat this reminder was created in; empty for a session-less caller.
    pub session_id: String,
}
