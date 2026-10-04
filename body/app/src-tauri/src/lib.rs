//! The Cortex body: the host-native Tauri shell.

mod body_server;
mod brain;
mod confirm;
mod converse;
mod hotkey;
mod link;
mod preferences;
mod reminders;
mod sessions;
mod tray;

use tauri::{AppHandle, Emitter, Manager};

/// The overlay window's Tauri label (matches `tauri.conf.json`).
const OVERLAY_LABEL: &str = "overlay";
/// The event the overlay listens on to open (emitted on the hotkey / tray).
const ACTIVATE_EVENT: &str = "cortex:activate";

/// Builds and runs the Tauri application.
pub fn run() {
    tauri::Builder::default()
        .manage(confirm::ConfirmRoute::default())
        .setup(|app| {
            #[cfg(target_os = "linux")]
            app.manage(std::sync::Arc::new(os_linux::OverlayWatch::default()));
            tray::build(app.handle())?;
            hotkey::register(app.handle());
            // The overlay must hide itself from screen capture before any capture can happen:
            // a picture of the always-on-top window would feed the model its own prior output.
            body_server::start(app.handle(), body_server::exclude_overlay(app.handle()));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            converse::converse,
            confirm::confirm_response,
            sessions::list_sessions,
            sessions::session_messages,
            sessions::rename_session,
            sessions::delete_session,
            sessions::set_session_hoisted,
            preferences::get_preferences,
            preferences::set_preference,
            reminders::list_due_reminders,
            reminders::ack_reminder,
            link::check_link
        ])
        .run(tauri::generate_context!())
        .expect("error while running the Cortex body");
}

/// Toggles the overlay: shows and summons it, or hides it if already visible.
pub(crate) fn toggle_overlay(handle: &AppHandle) {
    let Some(window) = handle.get_webview_window(OVERLAY_LABEL) else {
        return;
    };
    if window.is_visible().unwrap_or(false) {
        if window.hide().is_ok() {
            record_overlay(handle, false);
        }
    } else {
        record_overlay(handle, true);
        let _ = window.show();
        let _ = window.set_focus();
        let _ = window.emit(ACTIVATE_EVENT, ());
    }
}

/// Tells the Wayland capture guard that the overlay is about to show or has hidden.
#[cfg(target_os = "linux")]
fn record_overlay(handle: &AppHandle, shown: bool) {
    if let Some(overlay) = handle.try_state::<std::sync::Arc<os_linux::OverlayWatch>>() {
        if shown {
            overlay.showing();
        } else {
            overlay.hidden();
        }
    }
}

/// Off Linux no capture reads the overlay's state, so there is nothing to tell.
#[cfg(not(target_os = "linux"))]
fn record_overlay(_handle: &AppHandle, _shown: bool) {}
