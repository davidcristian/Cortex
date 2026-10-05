//! A live check of the Wayland window capture, `#[ignore]`d so it never runs in CI or counts toward
//! coverage. It needs a session bus whose `ScreenCast` portal offers a window source,
//! `gst-launch-1.0` with the `pipewiresrc` element on `PATH`, and someone to choose a covered window.
#![cfg(target_os = "linux")]

use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use body_core::{Capture, CaptureError, CaptureRequest, CaptureTarget, ScreenCapture};
use os_linux::zbus::blocking::Connection;
use os_linux::{
    CHOOSER_LIMIT, DbusScreenCast, FRAME_LIMIT, GST_LAUNCH_PROGRAM, GstLaunch, LinuxWindowCapture,
    NO_WINDOW, OverlayWatch, offers_window,
};

#[test]
#[ignore = "needs a ScreenCast portal with a window source and a person choosing a window"]
fn a_hide_opens_the_chooser_and_the_chosen_window_is_read_alone() {
    let connection = Connection::session().unwrap_or_else(|error| panic!("{error}"));
    assert_eq!(
        offers_window(&DbusScreenCast::new(connection.clone())),
        Ok(true)
    );
    let watch = Arc::new(OverlayWatch::default());
    watch.showing();
    let capture = LinuxWindowCapture::new(
        DbusScreenCast::new(connection),
        GstLaunch::new(GST_LAUNCH_PROGRAM, FRAME_LIMIT),
    )
    .watch_hides(Arc::clone(&watch) as _, CHOOSER_LIMIT);
    let focus = CaptureRequest::targeted(1568, 4 << 20, CaptureTarget::Focus);

    let first = capture.capture(&focus).map(|_| ());
    assert_eq!(first, Err(CaptureError::NoTarget(String::from(NO_WINDOW))));
    assert!(capture.window().choice_wanted());
    eprintln!("hiding the overlay: choose a window that another window covers");
    watch.hidden();

    let deadline = Instant::now() + CHOOSER_LIMIT;
    let captured = loop {
        thread::sleep(Duration::from_millis(500));
        match capture.capture(&focus) {
            Err(CaptureError::NoTarget(_)) if Instant::now() < deadline => {}
            other => break other.unwrap_or_else(|error| panic!("{error}")),
        }
    };
    let frame = captured.frame();
    let centre = (frame.height() / 2 * frame.width() + frame.width() / 2) as usize * 4;
    let colour = &frame.pixels()[centre..centre + 4];
    let same = frame
        .pixels()
        .chunks_exact(4)
        .filter(|p| *p == colour)
        .count();
    eprintln!(
        "window {}x{}, centre pixel blue, green, red {:?}, {same} pixels that colour",
        frame.width(),
        frame.height(),
        &colour[..3]
    );
    let encoded = Capture::from_bgra(&captured, &focus).unwrap_or_else(|error| panic!("{error}"));
    assert!(!encoded.covers_display());
    assert_eq!((encoded.source_width(), encoded.source_height()), (0, 0));
    assert_eq!(encoded.target_width(), frame.width());
}
