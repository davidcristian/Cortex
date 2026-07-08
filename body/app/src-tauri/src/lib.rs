//! The Cortex body: the host-native Tauri shell (ADR-0011 decision 5).
//!
//! Deliberately thin wiring. A global hotkey summons a hidden overlay window,
//! the overlay talks to the brain through the `converse` command, and streamed
//! `TurnEvent`s are forwarded to the webview. Every branchy decision (accelerator
//! mapping, seam translation) lives in the gated crates `body_core`/`body_rpc`;
//! this crate is excluded from the coverage gate and host-validated on Windows.

mod confirm;
mod converse;
mod hotkey;
mod sessions;
mod tray;

use tauri::{AppHandle, Emitter, Manager};

/// The overlay window's Tauri label (matches `tauri.conf.json`).
const OVERLAY_LABEL: &str = "overlay";
/// The event the overlay listens on to open (emitted on the hotkey / tray).
const ACTIVATE_EVENT: &str = "cortex:activate";

/// Builds and runs the Tauri application. A failure here (no window, no runtime)
/// is unrecoverable at process start, so it panics rather than returning.
pub fn run() {
    tauri::Builder::default()
        .manage(confirm::ConfirmRoute::default())
        .setup(|app| {
            tray::build(app.handle())?;
            hotkey::register(app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            converse::converse,
            confirm::confirm_response,
            sessions::list_sessions,
            sessions::session_messages
        ])
        .run(tauri::generate_context!())
        .expect("error while running the Cortex body");
}

/// Toggles the overlay: shows and summons it, or hides it if already visible.
/// The hotkey and the tray's "Show overlay" both route through here.
pub(crate) fn toggle_overlay(handle: &AppHandle) {
    let Some(window) = handle.get_webview_window(OVERLAY_LABEL) else {
        return;
    };
    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
    } else {
        let _ = window.show();
        let _ = window.set_focus();
        let _ = window.emit(ACTIVATE_EVENT, ());
    }
}
