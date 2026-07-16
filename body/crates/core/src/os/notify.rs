//! The notification port: proactive delivery on the host (ADR-0025), the second OS action
//! the brain drives over `BodyService` after [`AudioControl`](super::AudioControl).

pub const MAX_TEXT_CHARS: usize = 200;

/// The provenance line a backend renders beneath a reminder the brain does not trust.
///
/// Fixed and body-authored: the badge that describes untrusted text may never itself be
/// built from that text.
pub const UNTRUSTED_ATTRIBUTION: &str = "from an untrusted source";

/// Why showing a native notification failed. See [`Notify`].
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
pub enum NotifyError {
    /// No notification service is reachable (no notifier for the app identity, the OS
    /// service is not running). `0` is a backend detail.
    #[error("no notification service is available: {0}")]
    Unavailable(String),
    /// The notification backend refused or failed the call. `0` is a backend detail.
    #[error("the notification backend failed: {0}")]
    Backend(String),
}

/// One notification the body shows, with its text already inert.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Notification {
    title: String,
    body: String,
    reminder_id: String,
    tainted: bool,
}

impl Notification {
    /// Builds a notification from the wire values, making `title` and `body` inert.
    ///
    /// `reminder_id` is brain-minted correlation, never user or model text, so it is kept
    /// verbatim for logs and for a backend that wants to replace its own earlier toast.
    #[must_use]
    pub fn new(title: &str, body: &str, reminder_id: &str, tainted: bool) -> Self {
        Self {
            title: inert(title),
            body: inert(body),
            reminder_id: String::from(reminder_id),
            tainted,
        }
    }

    /// The notification's heading, inert.
    #[must_use]
    pub fn title(&self) -> &str {
        &self.title
    }

    /// The notification's message, inert. For a reminder this is the stored text.
    #[must_use]
    pub fn body(&self) -> &str {
        &self.body
    }

    /// The reminder this notification delivers, for correlation.
    #[must_use]
    pub fn reminder_id(&self) -> &str {
        &self.reminder_id
    }

    /// Whether the brain marked the text as untrusted in provenance.
    #[must_use]
    pub const fn tainted(&self) -> bool {
        self.tainted
    }

    /// The provenance line to render, or `None` when the brain trusts the text.
    #[must_use]
    pub const fn attribution(&self) -> Option<&'static str> {
        if self.tainted {
            Some(UNTRUSTED_ATTRIBUTION)
        } else {
            None
        }
    }
}

/// Makes one line of untrusted text inert: every control character becomes a space (a replacement,
/// not a deletion, so two words never fuse across a stripped newline), and the result is bounded at
/// [`MAX_TEXT_CHARS`] with a trailing ellipsis marking the cut.
fn inert(raw: &str) -> String {
    let mut text: String = raw
        .chars()
        .take(MAX_TEXT_CHARS)
        .map(|character| {
            if character.is_control() {
                ' '
            } else {
                character
            }
        })
        .collect();
    if raw.chars().nth(MAX_TEXT_CHARS).is_some() {
        text.push('…');
    }
    text
}

/// Escapes `text` for an XML text node or a quoted attribute value.
#[must_use]
pub fn escape_xml(text: &str) -> String {
    let mut escaped = String::with_capacity(text.len());
    for character in text.chars() {
        match character {
            '&' => escaped.push_str("&amp;"),
            '<' => escaped.push_str("&lt;"),
            '>' => escaped.push_str("&gt;"),
            '"' => escaped.push_str("&quot;"),
            '\'' => escaped.push_str("&apos;"),
            other => escaped.push(other),
        }
    }
    escaped
}

/// The port a notification backend implements (`os_windows` real; other platforms are stubs until
/// built, per ADR-0011).
pub trait Notify: Send + Sync {
    /// Shows `notification` on the host.
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError>;
}
