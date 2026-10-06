#![cfg(target_os = "linux")]

use std::io::Write;
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use body_core::ClipboardPicture;
use os_linux::wayland_client::Connection;
use os_linux::{LinuxClipboardPicture, SelectionRead, WaylandSelection};

const PNG: &str = "image/png";

/// A `wl-copy` serving the clipboard, stopped when dropped so a failed test leaves no owner.
struct Copying(Child);

impl Drop for Copying {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn copy(picture: &[u8]) -> Copying {
    let mut copying = Command::new("wl-copy")
        .args(["--foreground", "--type", PNG])
        .stdin(Stdio::piped())
        .spawn()
        .unwrap_or_else(|error| panic!("wl-copy: {error}"));
    let mut input = copying.stdin.take().unwrap_or_else(|| panic!("no stdin"));
    input
        .write_all(picture)
        .unwrap_or_else(|error| panic!("{error}"));
    drop(input);
    Copying(copying)
}

fn selection() -> WaylandSelection {
    WaylandSelection::new(Connection::connect_to_env().unwrap_or_else(|error| panic!("{error}")))
}

#[test]
#[ignore = "needs a compositor with a data control protocol on WAYLAND_DISPLAY and wl-copy"]
fn reads_a_picture_wl_copy_put_on_the_clipboard() {
    let picture: Vec<u8> = (0..300_000_u32)
        .map(|index| index.to_le_bytes()[0])
        .collect();
    let copying = copy(&picture);
    let deadline = Instant::now() + Duration::from_secs(5);
    while !selection()
        .offered()
        .is_ok_and(|types| types.iter().any(|name| name == PNG))
    {
        assert!(
            Instant::now() < deadline,
            "wl-copy's selection never listed {PNG}"
        );
        thread::sleep(Duration::from_millis(50));
    }
    let read = LinuxClipboardPicture::new(selection()).picture();
    drop(copying);
    let found = read.unwrap_or_else(|error| panic!("{error:?}"));
    let found = found.unwrap_or_else(|| panic!("no picture"));
    assert_eq!((found.mime_type, found.data.len()), (PNG, picture.len()));
    assert!(found.data == picture);
}
