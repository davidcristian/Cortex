//! The `dropped_pictures` IPC command: the pictures among the files of the window's last native
//! drop, read from the paths that drop gave and never from a path the page names.

use body_core::{DropBox, dropped_pictures as pictures_of};
use tauri::{DragDropEvent, Manager, State, Window, WindowEvent};

use crate::clipboard::{WirePicture, wire};

/// Keeps the paths of a native drop on the overlay window for the next `dropped_pictures` call.
pub fn keep(window: &Window, event: &WindowEvent) {
    if let WindowEvent::DragDrop(DragDropEvent::Drop { paths, .. }) = event {
        window.state::<DropBox>().keep(paths);
    }
}

/// Reads the last drop's pictures off the async runtime, once, since a read waits on the disk.
#[tauri::command]
pub async fn dropped_pictures(drop: State<'_, DropBox>) -> Result<Vec<WirePicture>, String> {
    let dropped = drop.take();
    let read = tauri::async_runtime::spawn_blocking(move || pictures_of(dropped, &reader()));
    let pictures = read.await.map_err(|error| error.to_string())?;
    Ok(pictures.into_iter().map(wire).collect())
}

#[cfg(target_os = "linux")]
fn reader() -> impl Fn(&std::path::Path, usize) -> Option<Vec<u8>> {
    os_linux::read_dropped_file
}

/// Only the Linux window turns the native drop handler on, so no other platform keeps a path.
#[cfg(not(target_os = "linux"))]
fn reader() -> impl Fn(&std::path::Path, usize) -> Option<Vec<u8>> {
    |_: &std::path::Path, _: usize| None
}
