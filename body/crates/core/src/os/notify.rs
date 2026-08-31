//! The notification port: proactive delivery on the host (ADR-0025), the second OS action
//! the brain drives over `BodyService` after [`AudioControl`](super::AudioControl).
//!
//! Pure, like the rest of the core. [`Notification`] carries the text a backend renders and
//! makes it inert at construction; [`escape_xml`] is the escaper a markup-templated backend
//! needs, since a Windows toast is an XML document; [`Notify`] is the trait the per-platform
//! crates implement.
//!
//! The value sanitizes rather than each backend, because a fired reminder's text is the one
//! string the body renders that no output guardrail inspected (ADR-0015 filters streamed
//! replies, not store rows). It may carry whatever an attacker got into the brain's context,
//! and the `tainted` bit says only that the brain knows it. Sanitizing at construction means
//! no backend can forget to, and a backend that never interprets markup pays nothing for it.

/// The longest raw title or body a [`Notification`] keeps, in characters.
///
/// Longer text is truncated with a trailing ellipsis rather than refused, because the OS
/// rejects an oversized payload as a whole and a long reminder would become no reminder.
pub const MAX_TEXT_CHARS: usize = 200;

/// The provenance line a backend renders beneath a reminder the brain does not trust.
///
/// The string is fixed and body-authored, so the badge describing untrusted text is never
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
///
/// Constructed only through [`Notification::new`], so an existing value is always safe to
/// render: the title and body carry no control characters and are bounded by
/// [`MAX_TEXT_CHARS`]. Control characters are removed because a toast template is a document
/// that a raw control byte makes unparseable. Markup escaping stays with the renderer in
/// [`escape_xml`] rather than happening here, because the right escape differs per backend.
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

/// Makes one line of untrusted text inert: every control character becomes a space, and the
/// result is bounded at [`MAX_TEXT_CHARS`] with a trailing ellipsis marking the cut. A
/// control character is replaced rather than deleted so two words never fuse across a
/// stripped newline, and counting in `char`s keeps the bound right for non-ASCII text and
/// cannot split a code point.
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
///
/// It replaces the five predefined XML entities, so injected reminder text lands in a toast
/// template as characters rather than markup. It is pure and gated here because the backend
/// that needs it, the Windows toast, is `cfg(windows)` and never measured in CI, so keeping
/// the escape there would leave the seam's data-not-instructions posture on untested code.
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

/// The port a notification backend implements (`os_windows` real; other platforms are stubs
/// until built, per ADR-0011). It is the sibling of [`AudioControl`](super::AudioControl) and
/// the push half of reminder delivery: the brain's ticker calls `BodyService.Notify`, the body
/// server translates it onto this port, and showing the notification is what delivers it.
///
/// `Send + Sync` for the same reason as [`AudioControl`](super::AudioControl): the body's
/// `BodyService` server holds the backend across async tasks. Backends are stateless, so
/// nothing here violates the one hard rule.
pub trait Notify: Send + Sync {
    /// Shows `notification` on the host.
    ///
    /// Returns whether the OS displayed it. `Ok(false)` reports a state rather than a
    /// failure: the host is reachable and declined, typically because the user turned
    /// notifications off. It is carried on the `Ok` channel for the same reason the brain's
    /// ack answer is, and the caller handles it like an error anyway, since the reminder
    /// stays deliverable and the overlay's pull path surfaces it on the next open.
    ///
    /// # Errors
    ///
    /// [`NotifyError`] if no notification service is available or the backend fails.
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError>;
}
