//! The Cortex body: the host-native Tauri shell.

mod body_server;
mod brain;
mod clipboard;
mod confirm;
mod converse;
mod dropped;
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
/// The event a press sends while the window is shown, for the overlay to hide or open by its mode.
const TOGGLE_EVENT: &str = "cortex:toggle";

/// Builds and runs the Tauri application.
pub fn run() {
    tauri::Builder::default()
        .manage(confirm::ConfirmRoute::default())
        .manage(body_core::DropBox::default())
        .on_window_event(dropped::keep)
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
            clipboard::clipboard_picture,
            dropped::dropped_pictures,
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
            link::check_link,
            set_overlay_shown
        ])
        .run(tauri::generate_context!())
        .expect("error while running the Cortex body");
}

/// Shows and summons a hidden overlay, or hands a press over a shown one to the overlay, which
/// hides its panel or opens its orb or preview and then hides the window itself.
pub(crate) fn toggle_overlay(handle: &AppHandle) {
    let Some(window) = handle.get_webview_window(OVERLAY_LABEL) else {
        return;
    };
    if window.is_visible().unwrap_or(false) {
        let _ = window.emit(TOGGLE_EVENT, ());
    } else {
        record_overlay(handle, true);
        let _ = window.show();
        let _ = window.set_focus();
        let _ = window.emit(ACTIVATE_EVENT, ());
    }
}

/// Shows or hides the overlay window as the overlay's mode asks, without taking focus.
#[tauri::command]
fn set_overlay_shown(handle: AppHandle, shown: bool) {
    let Some(window) = handle.get_webview_window(OVERLAY_LABEL) else {
        return;
    };
    if shown {
        record_overlay(&handle, true);
        let _ = window.show();
    } else if window.hide().is_ok() {
        record_overlay(&handle, false);
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
