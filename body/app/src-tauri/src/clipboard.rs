//! The `clipboard_picture` IPC command: the clipboard's picture for a paste the webview gave the
//! page no file for, its bytes still encoded so the overlay's reader stays the one decoder.

use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use body_core::{ClipboardError, ClipboardPicture, PastedPicture};
use serde::Serialize;

/// The overlay's `WirePicture` (matches `bridge/clipboard.ts`): base64, as IPC results are JSON.
/// A paste answers one and a drop a list.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WirePicture {
    data_base64: String,
    mime_type: &'static str,
}

/// Whether the shell's GTK display is Wayland, read on the main thread at setup.
#[derive(Clone, Copy, Default)]
pub struct Display {
    #[cfg(target_os = "linux")]
    wayland: bool,
}

impl Display {
    /// The overlay window's display: Wayland when GDK runs the shell as a Wayland client.
    #[cfg(target_os = "linux")]
    pub fn of(handle: &tauri::AppHandle) -> Self {
        use gtk::glib::prelude::ObjectExt;
        use gtk::prelude::WidgetExt;
        use tauri::Manager;

        let window = handle.get_webview_window(crate::OVERLAY_LABEL);
        let gtk = window.and_then(|window| window.gtk_window().ok());
        let wayland = gtk.is_some_and(|gtk| gtk.display().type_().name() == "GdkWaylandDisplay");
        Self { wayland }
    }

    /// No other platform has a second clipboard reader.
    #[cfg(not(target_os = "linux"))]
    pub fn of(_: &tauri::AppHandle) -> Self {
        Self::default()
    }
}

/// Reads the clipboard's picture off the async runtime, as a read waits on the clipboard's owner.
#[tauri::command]
pub async fn clipboard_picture(
    display: tauri::State<'_, Display>,
) -> Result<Option<WirePicture>, String> {
    let display = *display;
    let read = tauri::async_runtime::spawn_blocking(move || picture(display)).await;
    read.map_err(|error| error.to_string())?
        .map(|found| found.map(wire))
        .map_err(|error: ClipboardError| error.to_string())
}

pub(crate) fn wire(picture: PastedPicture) -> WirePicture {
    WirePicture {
        data_base64: STANDARD.encode(picture.data),
        mime_type: picture.mime_type,
    }
}

/// The Wayland clipboard for a Wayland-client shell, else the X selection, through `XWayland` on
/// a Wayland session that runs one.
#[cfg(target_os = "linux")]
fn picture(display: Display) -> Result<Option<PastedPicture>, ClipboardError> {
    use os_linux::{LinuxClipboardPicture, WaylandSelection, X11Selection};

    if display.wayland {
        let selection = match wayland() {
            Ok(connection) => WaylandSelection::new(connection),
            Err(error) => WaylandSelection::absent(&error),
        };
        return LinuxClipboardPicture::new(selection).picture();
    }
    let selection = match os_linux::x11rb::connect(None) {
        Ok((connection, screen)) => X11Selection::new(connection, screen),
        Err(error) => X11Selection::absent(&error),
    };
    LinuxClipboardPicture::new(selection).picture()
}

/// Connects where GDK does: `WAYLAND_DISPLAY`, else `wayland-0`, under `XDG_RUNTIME_DIR` unless
/// the name is absolute. `Connection::connect_to_env` fails when the variable is unset.
#[cfg(target_os = "linux")]
fn wayland() -> Result<os_linux::wayland_client::Connection, os_linux::wayland_client::ConnectError>
{
    use os_linux::wayland_client::{ConnectError, Connection};
    use std::path::PathBuf;

    let name = std::env::var_os("WAYLAND_DISPLAY").unwrap_or_else(|| "wayland-0".into());
    let mut path = PathBuf::from(name);
    if path.is_relative() {
        let runtime = std::env::var_os("XDG_RUNTIME_DIR").ok_or(ConnectError::NoCompositor)?;
        path = PathBuf::from(runtime).join(path);
    }
    let stream = std::os::unix::net::UnixStream::connect(path);
    Connection::from_socket(stream.map_err(|_| ConnectError::NoCompositor)?)
}

/// WebView2 gives the page a pasted picture as a file, so the shell has none to add.
#[cfg(not(target_os = "linux"))]
fn picture(_: Display) -> Result<Option<PastedPicture>, ClipboardError> {
    body_core::NoClipboardPicture.picture()
}
