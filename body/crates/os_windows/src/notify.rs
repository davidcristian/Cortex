//! The Windows [`Notify`] backend: a native toast (`WinRT` `ToastNotificationManager`).
//!
//! A thin adapter (AGENTS.md gate 3): it resolves the toast notifier for the app identity,
//! asks whether the user allows notifications at all, renders the notification into the
//! `ToastGeneric` template, and shows it. Every decision that carries a risk is already made in
//! `body_core` (the inert text, the taint attribution, the XML escaping), so the only branches
//! here are the ones the OS answers.
//!
//! `WinRT` projections are safe, so the toast calls need no `unsafe`. Activating a `WinRT`
//! factory does need a COM-initialized thread, and the body serves `BodyService` on tokio
//! workers that have none, so the one `unsafe` here is the same idempotent `CoInitializeEx`
//! the audio backend makes (ADR-0023's narrow authorization for this crate, extended to the
//! toast by ADR-0025).
//!
//! Host-authored and validated on Windows by the user. Like the other real backends it is
//! never built or measured in CI, since the whole crate is `cfg(windows)` and compiles to
//! nothing on Linux.
//!
//! [`Notify`]: body_core::Notify
#![allow(unsafe_code)] // ADR-0025: WinRT activation needs a COM-initialized thread.

use body_core::os::escape_xml;
use body_core::{Notification, Notify, NotifyError};
use windows::Data::Xml::Dom::XmlDocument;
use windows::UI::Notifications::{
    NotificationSetting, ToastNotification, ToastNotificationManager,
};
use windows::Win32::System::Com::{COINIT_MULTITHREADED, CoInitializeEx};
use windows::core::{Error as WinError, HSTRING};

/// The Windows toast backend. Stateless apart from the app identity it shows under, so a
/// notification-settings change between calls is picked up (the one hard rule: the body
/// server holds no state).
pub struct WindowsNotify {
    app_id: String,
}

impl WindowsNotify {
    /// Creates the backend for `app_id`, the `AppUserModelID` the toast is attributed to.
    ///
    /// An unpackaged app must own a Start Menu shortcut carrying this identity or Windows
    /// refuses to show its toasts; the shell reads the value from the environment so a dev
    /// run can borrow a registered identity instead (see `docs/runbooks/scheduling.md`).
    #[must_use]
    pub fn new(app_id: &str) -> Self {
        Self {
            app_id: String::from(app_id),
        }
    }
}

impl Notify for WindowsNotify {
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError> {
        // The same split the volume backend maps its COM failures on: a notification service
        // that cannot be reached at all is transient, and anything else is a backend fault.
        let unreachable = |error: WinError| NotifyError::Unavailable(error.message());
        let failed = |error: WinError| NotifyError::Backend(error.message());
        unsafe {
            // Idempotent per thread: a prior initialization returns a non-fatal status, which
            // is ignored.
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        }
        let notifier =
            ToastNotificationManager::CreateToastNotifierWithId(&HSTRING::from(&self.app_id))
                .map_err(unreachable)?;
        // The user or a policy can switch notifications off, which is an answer rather than a
        // failure: the reminder stays deliverable and the overlay's pull path shows it.
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

/// Renders the notification into a `ToastGeneric` payload: the title, the message, and (for a
/// reminder the brain does not trust) the fixed provenance line, each escaped so injected
/// text lands as characters rather than markup.
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
