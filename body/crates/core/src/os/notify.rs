//! The notification port: how the brain shows the user a native notification.

/// The longest raw title or body a [`Notification`] keeps, in characters. Longer text is truncated
/// rather than refused, because the OS rejects an oversized payload whole.
pub const MAX_TEXT_CHARS: usize = 200;

/// The provenance line a backend renders beneath a reminder the brain does not trust.
///
/// The string is fixed and written by the body, so the warning about untrusted text is never
/// built out of that text.
pub const UNTRUSTED_ATTRIBUTION: &str = "from an untrusted source";

/// Why showing a native notification failed.
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
pub enum NotifyError {
    /// No notification service is reachable (no notifier for the app identity, the OS service is
    /// not running).
    #[error("no notification service is available: {0}")]
    Unavailable(String),
    /// The notification backend refused or failed the call.
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

    /// The notification's message, inert.
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

/// Makes one line of untrusted text inert: every control character becomes a space, and the
/// result is bounded at [`MAX_TEXT_CHARS`] with a trailing ellipsis marking the cut. A control
/// character is replaced rather than deleted so two words never fuse across a stripped newline.
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

/// The port a notification backend implements. Only `os_windows` is real; the others are stubs.
pub trait Notify: Send + Sync {
    /// Shows `notification`, and reports whether the OS displayed it rather than declining it.
    ///
    /// # Errors
    ///
    /// [`NotifyError`] if no notification service is available or the backend fails.
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError>;
}
