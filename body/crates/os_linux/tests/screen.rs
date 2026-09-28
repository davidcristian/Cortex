#![cfg(target_os = "linux")]

use std::sync::{Arc, Mutex, PoisonError};

use body_core::{CaptureError, CaptureRequest, CaptureTarget, ScreenCapture};
use os_linux::{GrabError, LinuxScreenCapture, RootGrab, RootImage};

const MASKS: (u32, u32, u32) = (0x00ff_0000, 0x0000_ff00, 0x0000_00ff);

/// A fake root window that answers one scripted grab and counts the calls.
struct FakeRoot {
    answer: Result<RootImage, GrabError>,
    calls: Arc<Mutex<usize>>,
}

impl RootGrab for FakeRoot {
    fn grab(&self) -> Result<RootImage, GrabError> {
        *self.calls.lock().unwrap_or_else(PoisonError::into_inner) += 1;
        self.answer.clone()
    }
}

fn image(lsb_first: bool, data: Vec<u8>) -> RootImage {
    RootImage {
        width: 2,
        height: 1,
        depth: 24,
        bits_per_pixel: 32,
        lsb_first,
        masks: MASKS,
        data,
    }
}

fn counted(
    answer: Result<RootImage, GrabError>,
) -> (LinuxScreenCapture<FakeRoot>, Arc<Mutex<usize>>) {
    let calls = Arc::new(Mutex::new(0));
    let root = FakeRoot {
        answer,
        calls: Arc::clone(&calls),
    };
    (LinuxScreenCapture::new(root), calls)
}

fn backend(answer: Result<RootImage, GrabError>) -> LinuxScreenCapture<FakeRoot> {
    counted(answer).0
}

fn display() -> CaptureRequest {
    CaptureRequest::new(0)
}

#[test]
fn a_least_significant_byte_first_image_is_already_bgra() {
    let capture = backend(Ok(image(true, vec![1, 2, 3, 9, 4, 5, 6, 9])));

    let frame = capture
        .capture(&display())
        .unwrap_or_else(|error| panic!("{error:?}"));

    assert_eq!(frame.frame().pixels(), &[1, 2, 3, 9, 4, 5, 6, 9]);
    assert_eq!((frame.frame().width(), frame.frame().height()), (2, 1));
}

#[test]
fn a_most_significant_byte_first_image_is_reordered_to_bgra() {
    let capture = backend(Ok(image(false, vec![9, 3, 2, 1, 9, 6, 5, 4])));

    let frame = capture
        .capture(&display())
        .unwrap_or_else(|error| panic!("{error:?}"));

    assert_eq!(frame.frame().pixels(), &[1, 2, 3, 9, 4, 5, 6, 9]);
}

#[test]
fn a_depth_32_root_is_read() {
    let mut deep = image(true, vec![0; 8]);
    deep.depth = 32;

    assert!(backend(Ok(deep)).capture(&display()).is_ok());
}

#[test]
fn a_whole_display_capture_has_no_window() {
    let frame = backend(Ok(image(true, vec![0; 8])))
        .capture(&display())
        .unwrap_or_else(|error| panic!("{error:?}"));

    assert_eq!(
        frame,
        body_core::CapturedFrame::display(frame.frame().clone())
    );
}

#[test]
fn a_layout_other_than_eight_bit_rgb_in_32_bits_is_refused() {
    let layouts = [
        (16, 32, MASKS),
        (24, 24, MASKS),
        (24, 32, (0x0000_00ff, 0x0000_ff00, 0x00ff_0000)),
        (24, 32, (0, 0, 0)),
    ];
    for (depth, bits_per_pixel, masks) in layouts {
        let mut odd = image(true, vec![0; 8]);
        odd.depth = depth;
        odd.bits_per_pixel = bits_per_pixel;
        odd.masks = masks;

        let captured = backend(Ok(odd)).capture(&display());

        let Err(CaptureError::Backend(reason)) = captured else {
            panic!("expected a refusal of {depth}/{bits_per_pixel}/{masks:x?}, got {captured:?}");
        };
        assert!(
            reason.contains(&format!("depth {depth} at {bits_per_pixel} bits")),
            "{reason}"
        );
    }
}

#[test]
fn a_short_buffer_is_a_backend_failure() {
    let captured = backend(Ok(image(true, vec![0; 4]))).capture(&display());

    assert!(
        matches!(captured, Err(CaptureError::Backend(_))),
        "{captured:?}"
    );
}

#[test]
fn no_server_is_no_display() {
    let captured = backend(Err(GrabError::NoDisplay(String::from(
        "DISPLAY is not set",
    ))))
    .capture(&display());

    assert_eq!(
        captured,
        Err(CaptureError::NoDisplay(String::from("DISPLAY is not set")))
    );
}

#[test]
fn a_failed_read_is_a_backend_failure() {
    let captured = backend(Err(GrabError::Failed(String::from("BadMatch")))).capture(&display());

    assert_eq!(
        captured,
        Err(CaptureError::Backend(String::from("BadMatch")))
    );
}

#[test]
fn a_window_target_is_refused_without_reading_the_screen() {
    let (capture, calls) = counted(Ok(image(true, vec![0; 8])));

    let captured = capture.capture(&CaptureRequest::targeted(0, 0, CaptureTarget::Focus));

    assert_eq!(
        captured,
        Err(CaptureError::Backend(String::from(
            "capturing one window is not implemented on X11"
        )))
    );
    assert_eq!(*calls.lock().unwrap_or_else(PoisonError::into_inner), 0);
}
