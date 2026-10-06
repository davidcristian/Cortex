//! The `clipboard_picture` IPC command: the clipboard's picture for a paste the webview gave the
//! page no file for, its bytes still encoded so the overlay's reader stays the one decoder.

use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use body_core::{ClipboardError, ClipboardPicture, PastedPicture};
use serde::Serialize;

/// The overlay's `WirePicture` (matches `bridge/clipboard.ts`): base64, as IPC results are JSON.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WirePicture {
    data_base64: String,
    mime_type: &'static str,
}

/// Reads the clipboard's picture off the async runtime, as a read waits on the clipboard's owner.
#[tauri::command]
pub async fn clipboard_picture() -> Result<Option<WirePicture>, String> {
    let read = tauri::async_runtime::spawn_blocking(|| backend().picture()).await;
    read.map_err(|error| error.to_string())?
        .map(|found| found.map(wire))
        .map_err(|error: ClipboardError| error.to_string())
}

fn wire(picture: PastedPicture) -> WirePicture {
    WirePicture {
        data_base64: STANDARD.encode(picture.data),
        mime_type: picture.mime_type,
    }
}

/// The X selection on Linux, through `XWayland` on a Wayland session that runs one.
#[cfg(target_os = "linux")]
fn backend() -> impl ClipboardPicture {
    use os_linux::{LinuxClipboardPicture, X11Selection};

    let selection = match os_linux::x11rb::connect(None) {
        Ok((connection, screen)) => X11Selection::new(connection, screen),
        Err(error) => X11Selection::absent(&error),
    };
    LinuxClipboardPicture::new(selection)
}

/// WebView2 gives the page a pasted picture as a file, so the shell has none to add.
#[cfg(not(target_os = "linux"))]
fn backend() -> impl ClipboardPicture {
    body_core::NoClipboardPicture
}
