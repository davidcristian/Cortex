//! A live check of the screenshot portal, `#[ignore]`d so it never runs in CI or counts toward
//! coverage. It needs a session bus where `org.freedesktop.portal.Desktop` serves `Screenshot`.
#![cfg(target_os = "linux")]

use std::path::{Path, PathBuf};
use std::sync::{Mutex, PoisonError};

use body_core::{CaptureRequest, ScreenCapture};
use os_linux::zbus::blocking::Connection;
use os_linux::{DbusPortal, LinuxPortalCapture, PortalError, PortalReply, ScreenshotPortal};

/// The real adapter, with every file path the backend reads written down.
struct Recorded {
    portal: DbusPortal,
    read: Mutex<Vec<PathBuf>>,
}

impl ScreenshotPortal for &Recorded {
    fn sender(&self) -> Result<String, PortalError> {
        self.portal.sender()
    }

    fn screenshot(&self, handle: &str, token: &str) -> Result<PortalReply, PortalError> {
        self.portal.screenshot(handle, token)
    }

    fn read(&self, path: &Path) -> Result<Vec<u8>, PortalError> {
        self.read
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(path.to_path_buf());
        self.portal.read(path)
    }

    fn remove(&self, path: &Path) -> Result<(), PortalError> {
        self.portal.remove(path)
    }
}

#[test]
#[ignore = "needs a session bus with a desktop portal that serves Screenshot"]
fn the_portal_captures_the_display_twice_and_leaves_no_file() {
    let recorded = Recorded {
        portal: DbusPortal::new(Connection::session().unwrap()),
        read: Mutex::new(Vec::new()),
    };
    let backend = LinuxPortalCapture::new(&recorded);

    let first = backend.capture(&CaptureRequest::new(0)).unwrap();
    let second = backend.capture(&CaptureRequest::new(0)).unwrap();

    for captured in [&first, &second] {
        let frame = captured.frame();
        let centre = (frame.height() / 2 * frame.width() + frame.width() / 2) as usize * 4;
        eprintln!(
            "portal picture {}x{}, centre pixel blue, green, red {:?}",
            frame.width(),
            frame.height(),
            &frame.pixels()[centre..centre + 3]
        );
    }
    assert_eq!(first.frame().width(), second.frame().width());
    assert_eq!(first.frame().height(), second.frame().height());
    let read = recorded.read.lock().unwrap();
    assert_eq!(read.len(), 2);
    for path in read.iter() {
        assert!(!path.exists(), "{} was left behind", path.display());
    }
}
