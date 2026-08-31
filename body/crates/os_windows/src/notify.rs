//! The Windows [`Notify`] backend: a native toast (`WinRT` `ToastNotificationManager`).
#![allow(unsafe_code)] // Activating a WinRT factory needs a COM-initialized thread.

use body_core::os::escape_xml;
use body_core::{Notification, Notify, NotifyError};
use windows::Data::Xml::Dom::XmlDocument;
use windows::UI::Notifications::{
    NotificationSetting, ToastNotification, ToastNotificationManager,
};
use windows::Win32::System::Com::{COINIT_MULTITHREADED, CoInitializeEx};
use windows::core::{Error as WinError, HSTRING};

/// The Windows toast backend.
pub struct WindowsNotify {
    app_id: String,
}

impl WindowsNotify {
    /// Creates the backend for `app_id`, the `AppUserModelID` the toast is attributed to.
    ///
    /// Windows shows an unpackaged app's toasts only when a Start Menu shortcut has this
    /// identity; see `docs/runbooks/scheduling.md`.
    #[must_use]
    pub fn new(app_id: &str) -> Self {
        Self {
            app_id: String::from(app_id),
        }
    }
}

impl Notify for WindowsNotify {
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError> {
        let unreachable = |error: WinError| NotifyError::Unavailable(error.message());
        let failed = |error: WinError| NotifyError::Backend(error.message());
        unsafe {
            // Initializing COM again on this thread returns a non-fatal status, which is ignored.
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        }
        let notifier =
            ToastNotificationManager::CreateToastNotifierWithId(&HSTRING::from(&self.app_id))
                .map_err(unreachable)?;
        if notifier.Setting().map_err(failed)? != NotificationSetting::Enabled {
            return Ok(false);
        }
        let document = XmlDocument::new().map_err(failed)?;
        document
            .LoadXml(&HSTRING::from(&toast_xml(notification)))
            .map_err(failed)?;
        let toast = ToastNotification::CreateToastNotification(&document).map_err(failed)?;
        notifier.Show(&toast).map_err(failed)?;
        Ok(true)
    }
}

/// Renders the notification into a `ToastGeneric` payload: the title, the message, and, for a
/// reminder the brain does not trust, the fixed provenance line. Each is escaped, so injected
/// text shows as characters rather than markup.
fn toast_xml(notification: &Notification) -> String {
    let title = escape_xml(notification.title());
    let body = escape_xml(notification.body());
    let attribution = notification
        .attribution()
        .map(|line| {
            format!(
                r#"<text placement="attribution">{}</text>"#,
                escape_xml(line)
            )
        })
        .unwrap_or_default();
    format!(
        r#"<toast><visual><binding template="ToastGeneric"><text>{title}</text><text>{body}</text>{attribution}</binding></visual></toast>"#
    )
}
