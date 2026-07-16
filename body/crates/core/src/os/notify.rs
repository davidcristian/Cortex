//! The notification port: proactive delivery on the host (ADR-0025), the second OS action
//! the brain drives over `BodyService` after [`AudioControl`](super::AudioControl).
//!
//! Pure, like the rest of the core. [`Notification`] carries the text a backend renders and
//! owns the rule that makes it **inert**; [`escape_xml`] is the escaper a markup-templated
//! backend needs (a Windows toast is an XML document); [`Notify`] is the trait the
//! per-platform crates implement.
//!
//! Why the value sanitizes rather than each backend: a fired reminder's text is the one
//! string the body renders that **no output guardrail inspected** (ADR-0015 filters streamed
//! replies, not store rows), so it may carry whatever an attacker got into the brain's
//! context, and the `tainted` bit says only that the brain knows it. Making the text
//! harmless at construction means no backend can forget to, and a backend that never
//! interprets markup pays nothing for it.

/// The longest raw title or body a [`Notification`] keeps, in characters.
///
/// Longer text is truncated with a trailing ellipsis rather than refused: an oversized
/// payload is rejected by the OS as a whole, which would turn a long reminder into no
/// reminder, and the bias this seam has chosen everywhere else is that an irregularity
/// degrades an occurrence and never deletes one.
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
///
/// Constructed only through [`Notification::new`], so an existing value is always safe to
/// render: the title and body carry no control characters (a toast template is a document,
/// and a raw control byte makes it unparseable rather than merely ugly) and are bounded by
/// [`MAX_TEXT_CHARS`]. Markup escaping is a *renderer's* concern, not the value's, because
/// the right escape differs per backend, so it stays with [`escape_xml`] for the backends
/// that template markup.
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

/// Makes one line of untrusted text inert: every control character becomes a space (a
/// replacement, not a deletion, so two words never fuse across a stripped newline), and the
/// result is bounded at [`MAX_TEXT_CHARS`] with a trailing ellipsis marking the cut. Working
/// in `char`s keeps the bound honest for non-ASCII text and can never split a code point.
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
/// The five predefined XML entities, so injected reminder text lands in a toast template as
/// characters rather than markup. Pure and gated here because the backend that needs it (the
/// Windows toast) is `cfg(windows)` and never measured in CI: leaving the escape there would
/// leave the seam's data-not-instructions posture resting on untested code.
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
/// until built, per ADR-0011). The sibling of [`AudioControl`](super::AudioControl), and the
/// push half of reminder delivery: the brain's ticker calls `BodyService.Notify`, the body
/// server translates it onto this port, and a shown notification *is* delivery.
///
/// `Send + Sync` for the same reason as [`AudioControl`](super::AudioControl): the body's
/// `BodyService` server holds the backend across async tasks. Backends are stateless, so
/// nothing here violates the one hard rule.
pub trait Notify: Send + Sync {
    /// Shows `notification` on the host.
    ///
    /// Answers whether the OS displayed it. `Ok(false)` is a **state report**, not a failure:
    /// the host is reachable and declined, typically because the user turned notifications
    /// off. It rides the `Ok` channel for the same reason the brain's ack answer does, and
    /// the caller treats it exactly like an error anyway (the reminder stays deliverable and
    /// the overlay's pull path surfaces it on the next open).
    ///
    /// # Errors
    ///
    /// [`NotifyError`] if no notification service is available or the backend fails.
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError>;
}
