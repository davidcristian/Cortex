//! System-tray wiring: a tray icon whose menu shows the overlay or quits.

use body_core::HotkeyChord;
use tauri::AppHandle;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;

/// Builds the tray icon, whose tooltip names `chord`, and its menu.
pub fn build(handle: &AppHandle, chord: &HotkeyChord) -> tauri::Result<()> {
    let show = MenuItem::with_id(handle, "show", "Show overlay", true, None::<&str>)?;
    let quit = MenuItem::with_id(handle, "quit", "Quit Cortex", true, None::<&str>)?;
    let menu = Menu::with_items(handle, &[&show, &quit])?;
    let mut builder = TrayIconBuilder::with_id("cortex-tray")
        .tooltip(chord.tray_tooltip())
        .menu(&menu)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => crate::toggle_overlay(app),
            "quit" => app.exit(0),
            _ => {}
        });
    if let Some(icon) = handle.default_window_icon().cloned() {
        builder = builder.icon(icon);
    }
    builder.build(handle)?;
    Ok(())
}
