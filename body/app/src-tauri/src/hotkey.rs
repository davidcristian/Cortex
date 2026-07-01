//! Global-hotkey wiring: register the configured chord and toggle the overlay on
//! each press. Windows-only for now (ADR-0011); other platforms are a no-op until
//! their `Hotkey` backends land.

use tauri::AppHandle;

/// Registers the global hotkey (`CORTEX_HOTKEY`, default `ctrl+alt+space`) to
/// toggle the overlay. Best-effort: a failure is logged, not fatal. The tray
/// still summons the overlay.
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
    // Keep the backend (its OS registration + message loop) alive for the app's
    // lifetime; there is exactly one chord and it is never re-registered.
    Box::leak(Box::new(backend));
}

/// Non-Windows stub: no global hotkey until that platform's backend lands.
#[cfg(not(windows))]
pub fn register(_handle: &AppHandle) {
    eprintln!("cortex: global hotkey is not implemented on this platform yet");
}

/// The chord from `CORTEX_HOTKEY`, or the default if unset or unparseable.
#[cfg(windows)]
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
