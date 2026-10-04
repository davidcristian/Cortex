//! Global-hotkey wiring: register the configured chord and toggle the overlay on each press.

use tauri::AppHandle;

/// Registers the global hotkey (`CORTEX_HOTKEY`, default `ctrl+alt+space`) to toggle the overlay.
#[cfg(windows)]
pub fn register(handle: &AppHandle) {
    use body_core::Hotkey;
    use os_windows::WindowsHotkey;

    let chord = configured_chord();
    let backend = match WindowsHotkey::new() {
        Ok(backend) => backend,
        Err(error) => {
            eprintln!("cortex: hotkey manager unavailable: {error}");
            return;
        }
    };
    let activate = handle.clone();
    let callback = Box::new(move || crate::toggle_overlay(&activate));
    if let Err(error) = backend.register(&chord, callback) {
        eprintln!("cortex: could not register {chord}: {error}");
        return;
    }
    // Keep the backend, and so its OS registration and message loop, alive for the whole run.
    Box::leak(Box::new(backend));
}

/// The text a Wayland compositor shows the user for the hotkey.
#[cfg(target_os = "linux")]
const SHORTCUT_DESCRIPTION: &str = "Show or hide the Cortex overlay";

/// Registers the global hotkey through the desktop portal on a Wayland session, else as a passive
/// grab on the X display.
#[cfg(target_os = "linux")]
pub fn register(handle: &AppHandle) {
    use body_core::Hotkey;
    use os_linux::{LinuxHotkey, X11Keys};

    let chord = configured_chord();
    let activate = handle.clone();
    let callback = Box::new(move || crate::toggle_overlay(&activate));
    if std::env::var_os("WAYLAND_DISPLAY").is_some_and(|name| !name.is_empty()) {
        // A bind can wait up to SHORTCUTS_LIMIT on a compositor dialog, so it must not hold setup.
        let spawned = std::thread::Builder::new()
            .name(String::from("cortex-hotkey"))
            .spawn(move || register_portal(&chord, callback));
        if let Err(error) = spawned {
            eprintln!("cortex: could not start the hotkey registration: {error}");
        }
        return;
    }
    let keys = match os_linux::x11rb::connect(None) {
        Ok((connection, screen)) => X11Keys::new(connection, screen),
        Err(error) => X11Keys::absent(&error),
    };
    // The listener thread keeps its own handle on the connection, so the backend can be dropped.
    if let Err(error) = LinuxHotkey::new(keys).register(&chord, callback) {
        eprintln!("cortex: could not register {chord}: {error}");
    }
}

/// Binds `chord` through the `GlobalShortcuts` portal on a session bus connection of its own.
#[cfg(target_os = "linux")]
fn register_portal(chord: &body_core::HotkeyChord, callback: body_core::HotkeyCallback) {
    use body_core::Hotkey;
    use os_linux::zbus::blocking::Connection;
    use os_linux::{DbusShortcuts, LinuxPortalHotkey};

    let portal = match Connection::session() {
        Ok(connection) => DbusShortcuts::new(connection),
        Err(error) => DbusShortcuts::absent(&error),
    };
    // The listener thread keeps the portal, and so the connection its session lives on.
    let hotkey = LinuxPortalHotkey::new(portal, SHORTCUT_DESCRIPTION);
    if let Err(error) = hotkey.register(chord, callback) {
        eprintln!("cortex: could not register {chord}: {error}");
    }
}

/// Stub for a platform with no hotkey backend yet.
#[cfg(not(any(windows, target_os = "linux")))]
pub fn register(_handle: &AppHandle) {
    eprintln!("cortex: global hotkey is not implemented on this platform yet");
}

/// The chord from `CORTEX_HOTKEY`, or the default if unset or unparseable.
#[cfg(any(windows, target_os = "linux"))]
fn configured_chord() -> body_core::HotkeyChord {
    use body_core::HotkeyChord;

    let Ok(raw) = std::env::var("CORTEX_HOTKEY") else {
        return HotkeyChord::default();
    };
    HotkeyChord::parse(&raw).unwrap_or_else(|error| {
        eprintln!("cortex: invalid CORTEX_HOTKEY ({error}); using default");
        HotkeyChord::default()
    })
}
