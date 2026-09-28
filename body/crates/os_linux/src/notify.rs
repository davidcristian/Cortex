//! The Linux [`Notify`] backend's logic, over the freedesktop notification service.

use body_core::os::escape_xml;
use body_core::{Notification, Notify, NotifyError};

/// The capability a server lists when it renders a subset of markup in the body.
const BODY_MARKUP: &str = "body-markup";

/// D-Bus error names that mean no notification server owns the well-known name.
const NO_SERVER: [&str; 2] = [
    "org.freedesktop.DBus.Error.ServiceUnknown",
    "org.freedesktop.DBus.Error.NameHasNoOwner",
];

/// One `Notify` call's text: the application name, the summary line and the body.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BusMessage {
    /// The application the server attributes the notification to.
    pub app_name: String,
    /// The one-line heading, plain text by the specification.
    pub summary: String,
    /// The message, already escaped when the server renders markup.
    pub body: String,
}

/// A failed bus call: the D-Bus error name when the server replied with one, and its text.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BusError {
    /// The error name of a D-Bus error reply, or `None` for a transport or decoding failure.
    pub name: Option<String>,
    /// What went wrong, as the bus or the server wrote it.
    pub message: String,
}

/// The two calls the backend makes on `org.freedesktop.Notifications`.
pub trait NotificationBus: Send + Sync {
    /// The server's capability strings (`GetCapabilities`).
    ///
    /// # Errors
    ///
    /// [`BusError`] when the call fails or its reply cannot be read.
    fn capabilities(&self) -> Result<Vec<String>, BusError>;

    /// Sends one `Notify` call and returns the id the server assigned.
    ///
    /// # Errors
    ///
    /// [`BusError`] when the call fails or its reply cannot be read.
    fn notify(&self, message: &BusMessage) -> Result<u32, BusError>;
}

/// The Linux notification backend over any [`NotificationBus`].
pub struct LinuxNotify<B> {
    app_name: String,
    bus: B,
}

impl<B: NotificationBus> LinuxNotify<B> {
    /// Creates the backend, attributing each notification to `app_name`.
    #[must_use]
    pub fn new(app_name: &str, bus: B) -> Self {
        Self {
            app_name: String::from(app_name),
            bus,
        }
    }
}

impl<B: NotificationBus> Notify for LinuxNotify<B> {
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError> {
        let capabilities = self.bus.capabilities().map_err(classify)?;
        let markup = capabilities.iter().any(|name| name == BODY_MARKUP);
        let message = BusMessage {
            app_name: self.app_name.clone(),
            summary: String::from(notification.title()),
            body: render_body(notification, markup),
        };
        self.bus.notify(&message).map_err(classify)?;
        // The specification has no way for a server to decline, so an accepted call was shown.
        Ok(true)
    }
}

/// Renders the body: the message, then for an untrusted reminder the fixed provenance line.
///
/// `inert` text holds no newline, so the one before the provenance line cannot be forged.
fn render_body(notification: &Notification, markup: bool) -> String {
    let escape = |text: &str| {
        if markup {
            escape_xml(text)
        } else {
            String::from(text)
        }
    };
    let mut body = escape(notification.body());
    if let Some(line) = notification.attribution() {
        body.push('\n');
        body.push_str(&escape(line));
    }
    body
}

/// Maps a failed bus call to the port's error: no server is `Unavailable`, the rest `Backend`.
fn classify(error: BusError) -> NotifyError {
    match error.name {
        Some(name) if NO_SERVER.contains(&name.as_str()) => NotifyError::Unavailable(error.message),
        _ => NotifyError::Backend(error.message),
    }
}
