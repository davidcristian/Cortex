//! Typed core mirrors of the session-catalog and reminder wire values (ADR-0021/0025).
//!
//! The pure data the [`crate::transport::BrainTransport`] port carries for the overlay's chat
//! list / switcher / cycling and its reminder pull path, split out of `transport.rs` so the port
//! trait and its data types each stay under the line cap. No tonic, no network: the concrete gRPC
//! adapter in `body/crates/rpc` maps these onto the proto messages.

/// One recent chat as the overlay's switcher shows it. This is the typed core mirror
/// of the proto `SessionSummary` (ADR-0021).
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
    /// Whether the user pinned this chat (ADR-0021 pinning addendum). A pinned chat is
    /// unioned into the listing regardless of recency and sorts above the recency group,
    /// so the switcher renders it grouped at the top with a pin indicator.
    pub pinned: bool,
}

/// One persisted message in a session's history. This is the typed core mirror of the
/// proto `SessionMessage` (ADR-0021).
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

/// One fired-but-undelivered reminder awaiting the overlay (ADR-0025). This is the
/// typed core mirror of the proto `DueReminder`.
///
/// `text` is user-authored in the ordinary case but may be attacker-influenced when
/// `tainted` (a reminder scheduled out of untrusted content, ADR-0013), so a surface
/// renders it as inert text and never as markup, a link, or an instruction. The
/// provenance bit rides along so that surface can badge it rather than guess.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DueReminder {
    /// The reminder's id, which is what [`crate::transport::BrainTransport::ack_reminder`] acks.
    pub reminder_id: String,
    /// What to remind the user of; display-only, and inert (see the type docs).
    pub text: String,
    /// When it became deliverable, as unix-milliseconds.
    pub fired_at_unix_ms: i64,
    /// Whether the series recurs (a one-shot is gone once acked).
    pub recurring: bool,
    /// Untrusted provenance: the text came from content the brain does not trust.
    pub tainted: bool,
    /// The chat this reminder was created in; empty for a session-less caller.
    pub session_id: String,
}
