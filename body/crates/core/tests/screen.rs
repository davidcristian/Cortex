//! Behavioral tests for `body_core::os::screen` and its `screen_policy` and `screen_target`
//! siblings: the request resolution `CaptureRequest`
//! applies to a proto3 hint, the frame validation `RawFrame` enforces, the crop a resolved
//! target names (whole display, a window, one hanging off an edge, one off the display
//! altogether), the downscale/encode/
//! bound ladder `Capture::from_bgra` runs (identity, box-filtered, and the `TooLarge` rung),
//! the encoder's own rejects, `DeniedScreenCapture`, and a contract-style check that
//! `ScreenCapture` works as a generic bound through a fake.
//!
//! Every size claim is checked by decoding the produced PNG back with an independent decoder
//! rather than by trusting the value's own accessors, because the accessors are what the
//! policy writes and the bytes are what the seam ships.

use std::fmt::Debug;
use std::sync::{Mutex, PoisonError};

use body_core::os::screen::{
    CAPTURE_RECEIPT_BODY_DISPLAY, CAPTURE_RECEIPT_BODY_WINDOW, CAPTURE_RECEIPT_ID,
    CAPTURE_RECEIPT_TITLE,
};
use body_core::os::screen_policy::{
    CAPTURE_MIME, DEFAULT_MAX_EDGE, MAX_CAPTURE_BYTES, MAX_EDGE_CEILING, MAX_SHRINK_ATTEMPTS,
    encode_png,
};
use body_core::{
    Capture, CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, DeniedScreenCapture,
    RawFrame, ScreenCapture, TargetRect,
};

/// Unwraps a fixture's result. `unwrap` itself is denied outside `#[test]` bodies, and these
/// helpers run outside one.
fn ok<T, E: Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("the fixture failed: {error:?}"))
}

/// A fake `ScreenCapture` backend: answers a scripted frame or failure and records the
/// requests it was handed (the port is `Send + Sync`, so the interior mutability is a `Mutex`).
struct FakeScreen {
    frame: Result<CapturedFrame, CaptureError>,
    seen: Mutex<Vec<CaptureRequest>>,
}

impl FakeScreen {
    fn answering(frame: RawFrame) -> Self {
        Self {
            frame: Ok(CapturedFrame::display(frame)),
            seen: Mutex::new(Vec::new()),
        }
    }

    fn failing(error: CaptureError) -> Self {
        Self {
            frame: Err(error),
            seen: Mutex::new(Vec::new()),
        }
    }

    fn seen(&self) -> Vec<CaptureRequest> {
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

impl ScreenCapture for FakeScreen {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(*request);
        self.frame.clone()
    }
}

/// Captures through a generic bound, the way the `BodyService` server does.
fn capture_via<S: ScreenCapture>(
    backend: &S,
    request: &CaptureRequest,
) -> Result<CapturedFrame, CaptureError> {
    backend.capture(request)
}

/// The whole display, which is what an untargeted request answers.
fn whole(frame: RawFrame) -> CapturedFrame {
    CapturedFrame::display(frame)
}

/// The display with a window resolved inside it, in the OS's own left/top/right/bottom form.
fn window(frame: RawFrame, left: i32, top: i32, right: i32, bottom: i32) -> CapturedFrame {
    CapturedFrame::window(frame, TargetRect::new(left, top, right, bottom))
}

/// A frame whose pixels are a deterministic function of position, so an averaged output pixel
/// has a value a test can predict.
fn gradient(width: u32, height: u32) -> RawFrame {
    let mut pixels = Vec::with_capacity((width * height * 4) as usize);
    for y in 0..height {
        for x in 0..width {
            let blue = u8::try_from((x + y) % 256).unwrap_or(0);
            pixels.extend_from_slice(&[blue, 0x20, 0x40, 0x00]);
        }
    }
    ok(RawFrame::new(width, height, pixels))
}

/// A frame of one flat colour, in BGRA order.
fn flat(width: u32, height: u32, blue: u8, green: u8, red: u8) -> RawFrame {
    let pixels = [blue, green, red, 0x00].repeat((width * height) as usize);
    ok(RawFrame::new(width, height, pixels))
}

/// A frame of incompressible noise, which is what a photographic or video-filled screen costs.
fn noise(width: u32, height: u32) -> RawFrame {
    let mut state = 0x2545_F491_4F6C_DD1D_u64;
    let mut pixels = Vec::with_capacity((width * height * 4) as usize);
    for _ in 0..(width * height) {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        pixels.extend_from_slice(&state.to_le_bytes()[..4]);
    }
    ok(RawFrame::new(width, height, pixels))
}

/// Decodes a PNG back to `(width, height, rgb bytes)` with the decoder half of the same crate,
/// so a test never reads a dimension out of the value that produced it.
fn decode(data: &[u8]) -> (u32, u32, Vec<u8>) {
    let decoder = png::Decoder::new(std::io::Cursor::new(data));
    let mut reader = ok(decoder.read_info());
    let size = reader
        .output_buffer_size()
        .unwrap_or_else(|| panic!("the decoder reported no buffer size"));
    let mut buffer = vec![0; size];
    let info = ok(reader.next_frame(&mut buffer));
    assert_eq!(info.color_type, png::ColorType::Rgb);
    assert_eq!(info.bit_depth, png::BitDepth::Eight);
    buffer.truncate(info.buffer_size());
    (info.width, info.height, buffer)
}

#[test]
fn a_zero_max_edge_means_the_default_and_a_huge_one_is_clamped() {
    assert_eq!(CaptureRequest::new(0).max_edge(), 1600);
    assert_eq!(CaptureRequest::new(0).max_edge(), DEFAULT_MAX_EDGE);
    assert_eq!(CaptureRequest::new(640).max_edge(), 640);
    assert_eq!(CaptureRequest::new(u32::MAX).max_edge(), 4096);
    assert_eq!(CaptureRequest::new(u32::MAX).max_edge(), MAX_EDGE_CEILING);
    assert_eq!(CaptureRequest::new(MAX_EDGE_CEILING).max_edge(), 4096);
}

#[test]
fn the_byte_ceiling_is_six_mebibytes_and_the_ladder_has_two_rungs() {
    assert_eq!(MAX_CAPTURE_BYTES, 6_291_456);
    assert_eq!(MAX_SHRINK_ATTEMPTS, 2);
    assert_eq!(CAPTURE_MIME, "image/png");
}

#[test]
fn the_capture_receipt_strings_are_fixed_and_body_authored() {
    assert_eq!(CAPTURE_RECEIPT_TITLE, "Screen captured");
    assert_eq!(
        CAPTURE_RECEIPT_BODY_DISPLAY,
        "A picture of your screen was sent to the assistant."
    );
    assert_eq!(
        CAPTURE_RECEIPT_BODY_WINDOW,
        "A picture of one window was sent to the assistant."
    );
    assert_eq!(CAPTURE_RECEIPT_ID, "screen-capture");
    // Neither sentence may name what was captured: a window title is attacker-chosen text.
    for sentence in [CAPTURE_RECEIPT_BODY_DISPLAY, CAPTURE_RECEIPT_BODY_WINDOW] {
        assert!(!sentence.contains('{'), "{sentence} looks like a template");
    }
}

#[test]
fn a_request_carries_what_it_was_pointed_at_and_defaults_to_the_display() {
    assert_eq!(CaptureRequest::new(0).target(), CaptureTarget::Display);
    assert_eq!(
        CaptureRequest::bounded(0, 0).target(),
        CaptureTarget::Display
    );
    assert_eq!(
        CaptureRequest::targeted(0, 0, CaptureTarget::Focus).target(),
        CaptureTarget::Focus
    );
    assert_ne!(
        CaptureRequest::targeted(800, 0, CaptureTarget::Focus),
        CaptureRequest::new(800),
        "the target is part of the request, not a note beside it"
    );
}

#[test]
fn a_frame_with_no_pixels_is_refused() {
    let error = RawFrame::new(0, 4, vec![0; 0]).unwrap_err();
    assert_eq!(
        error,
        CaptureError::Backend(String::from("the frame is 0x4, which has no pixels"))
    );
    let error = RawFrame::new(4, 0, vec![0; 0]).unwrap_err();
    assert_eq!(
        error,
        CaptureError::Backend(String::from("the frame is 4x0, which has no pixels"))
    );
}

#[test]
fn a_frame_whose_buffer_is_the_wrong_size_is_refused() {
    let error = RawFrame::new(2, 2, vec![0; 15]).unwrap_err();
    assert_eq!(
        error,
        CaptureError::Backend(String::from(
            "the frame is 2x2 but carries 15 bytes, not 16"
        ))
    );
}

#[test]
fn a_frame_keeps_the_pixels_it_was_given() {
    let frame = flat(2, 3, 0x11, 0x22, 0x33);
    assert_eq!((frame.width(), frame.height()), (2, 3));
    assert_eq!(frame.pixels().len(), 24);
    assert_eq!(&frame.pixels()[..4], &[0x11, 0x22, 0x33, 0x00]);
}

#[test]
fn a_frame_inside_the_bound_crosses_unscaled_with_its_colours_intact() {
    let frame = flat(8, 5, 0x11, 0x22, 0x33);
    let capture = Capture::from_bgra(&whole(frame), &CaptureRequest::new(1600)).unwrap();

    assert_eq!(capture.mime_type(), "image/png");
    assert_eq!((capture.width(), capture.height()), (8, 5));
    assert_eq!((capture.source_width(), capture.source_height()), (8, 5));
    assert_eq!(
        &capture.data()[..8],
        &[0x89, b'P', b'N', b'G', 13, 10, 26, 10]
    );

    let (width, height, rgb) = decode(capture.data());
    assert_eq!((width, height), (8, 5));
    // BGRA in, RGB out: the alpha byte is dropped and the channels are reordered.
    assert_eq!(&rgb[..3], &[0x33, 0x22, 0x11]);
    assert_eq!(rgb.len(), 8 * 5 * 3);
}

#[test]
fn an_oversized_frame_is_box_filtered_down_to_the_requested_edge() {
    let frame = gradient(40, 20);
    let capture = Capture::from_bgra(&whole(frame), &CaptureRequest::new(10)).unwrap();

    assert_eq!((capture.width(), capture.height()), (10, 5));
    assert_eq!((capture.source_width(), capture.source_height()), (40, 20));

    let (width, height, rgb) = decode(capture.data());
    assert_eq!((width, height), (10, 5));
    // The top-left output pixel averages the source 4x4 block whose blue values are
    // (x + y) for x,y in 0..4: mean 3. Green and red are flat.
    assert_eq!(&rgb[..3], &[0x40, 0x20, 3]);
    // The second output column covers x in 4..8, so its blue mean is 3 + 4.
    assert_eq!(&rgb[3..6], &[0x40, 0x20, 7]);
}

#[test]
fn a_tall_frame_keeps_its_aspect_ratio_and_never_loses_an_edge() {
    let frame = gradient(3, 300);
    let capture = Capture::from_bgra(&whole(frame), &CaptureRequest::new(30)).unwrap();
    let (width, height, _) = decode(capture.data());
    // 3 * 30 / 300 floors to zero, and an image with no width is not an image.
    assert_eq!((width, height), (1, 30));
    assert_eq!((capture.width(), capture.height()), (1, 30));
}

#[test]
fn a_window_target_crops_to_the_window_and_still_reports_the_display() {
    // The trap this pins: three consumers read `source_*` as the size of the SCREEN (the wire's
    // ImageBlob, the brain's own capture value, and the "downscaled from WxH" clause the model
    // reads). A crop that flowed through as a smaller frame would silently make all three
    // describe the window as though it were the display.
    let capture = Capture::from_bgra(
        &window(gradient(40, 20), 10, 5, 20, 15),
        &CaptureRequest::new(1600),
    )
    .unwrap();

    assert_eq!((capture.width(), capture.height()), (10, 10));
    assert_eq!((capture.source_width(), capture.source_height()), (40, 20));
    assert!(!capture.covers_display());

    let (width, height, rgb) = decode(capture.data());
    assert_eq!((width, height), (10, 10));
    // The window is inside the capture edge, so it crosses pixel for pixel: the top-left output
    // pixel is source (10, 5), whose blue is x + y.
    assert_eq!(&rgb[..3], &[0x40, 0x20, 15]);
    // The last column of the first row is source (19, 5), and the first column of the last row
    // is source (10, 14). Both are inside the window and neither is anywhere near the display's
    // own corner, which is what says the crop moved the origin rather than just the size.
    assert_eq!(&rgb[27..30], &[0x40, 0x20, 24]);
    assert_eq!(&rgb[270..273], &[0x40, 0x20, 24]);
}

#[test]
fn a_window_hanging_off_the_display_is_cropped_to_the_part_that_is_on_it() {
    // Off the top left: a window dragged past the origin reports negative edges, which clamp.
    let capture = Capture::from_bgra(
        &window(gradient(40, 20), -10, -5, 15, 8),
        &CaptureRequest::new(1600),
    )
    .unwrap();
    let (width, height, rgb) = decode(capture.data());
    assert_eq!((width, height), (15, 8));
    assert_eq!(&rgb[..3], &[0x40, 0x20, 0]);

    // Off the bottom right: the far edges clamp to the display's own size.
    let capture = Capture::from_bgra(
        &window(gradient(40, 20), 30, 12, 400, 600),
        &CaptureRequest::new(1600),
    )
    .unwrap();
    let (width, height, rgb) = decode(capture.data());
    assert_eq!((width, height), (10, 8));
    assert_eq!(&rgb[..3], &[0x40, 0x20, 42]);
    assert_eq!((capture.source_width(), capture.source_height()), (40, 20));
}

#[test]
fn a_window_with_nothing_on_the_display_is_refused_rather_than_widened() {
    // Wholly off the display, which is what a window on a second monitor looks like from here.
    let error = Capture::from_bgra(
        &window(gradient(40, 20), 100, 100, 200, 200),
        &CaptureRequest::new(1600),
    )
    .unwrap_err();
    assert_eq!(
        error,
        CaptureError::NoTarget(String::from(
            "the target window at TargetRect { left: 100, top: 100, right: 200, bottom: 200 } \
             has nothing inside the 40x20 display"
        )),
        "a target off the display must fail, never fall back to the whole screen"
    );

    // An empty rectangle, in each axis separately: a window collapsed to a line.
    let flat_column = Capture::from_bgra(
        &window(gradient(40, 20), 5, 5, 5, 15),
        &CaptureRequest::new(1600),
    )
    .unwrap_err();
    let flat_row = Capture::from_bgra(
        &window(gradient(40, 20), 5, 5, 15, 5),
        &CaptureRequest::new(1600),
    )
    .unwrap_err();
    for error in [flat_column, flat_row] {
        let CaptureError::NoTarget(detail) = error else {
            panic!("expected an empty target to be refused, got {error:?}");
        };
        assert!(
            detail.ends_with("has nothing inside the 40x20 display"),
            "{detail}"
        );
    }
}

#[test]
fn a_window_that_covers_the_display_reports_a_screen_capture() {
    // A maximised window's frame can reach past every edge. What crosses the seam is then the
    // whole display, so the receipt must say screen rather than window: the sentence describes
    // what was sent, not what was asked for.
    let capture = Capture::from_bgra(
        &window(gradient(40, 20), -8, -8, 48, 28),
        &CaptureRequest::new(1600),
    )
    .unwrap();
    assert!(capture.covers_display());
    assert_eq!((capture.width(), capture.height()), (40, 20));

    let whole_display =
        Capture::from_bgra(&whole(gradient(40, 20)), &CaptureRequest::new(1600)).unwrap();
    assert!(whole_display.covers_display());
    assert_eq!(capture, whole_display, "the two are the same picture");

    // Reaching every edge but the top is not covering the display: a window docked across the
    // full width still leaves whatever is above it out of the picture.
    let docked = Capture::from_bgra(
        &window(gradient(40, 20), 0, 5, 40, 20),
        &CaptureRequest::new(1600),
    )
    .unwrap();
    assert!(!docked.covers_display());
    assert_eq!((docked.width(), docked.height()), (40, 15));
}

#[test]
fn an_oversized_window_is_box_filtered_from_its_own_pixels_only() {
    // The left half of the display, shrunk by two. Every averaged pixel must come from that
    // half: if the filter read the whole frame and cropped afterwards, the same output size
    // would carry the wrong colours.
    let capture = Capture::from_bgra(
        &window(gradient(40, 20), 0, 0, 20, 20),
        &CaptureRequest::new(10),
    )
    .unwrap();
    let (width, height, rgb) = decode(capture.data());
    assert_eq!((width, height), (10, 10));
    // Output (0, 0) averages source blues 0, 1, 1, 2 over the 2x2 block at the origin.
    assert_eq!(&rgb[..3], &[0x40, 0x20, 1]);
    // Output (1, 0) averages x in 2..4 and y in 0..2: blues 2, 3, 3, 4.
    assert_eq!(&rgb[3..6], &[0x40, 0x20, 3]);
    assert_eq!((capture.source_width(), capture.source_height()), (40, 20));
    assert!(!capture.covers_display());
}

#[test]
fn a_capture_that_stays_over_its_ceiling_is_refused_after_the_ladder_runs_out() {
    // A ceiling no PNG header can fit under, so all three rungs (32, 16, 8) overshoot.
    let frame = noise(32, 32);
    let error = Capture::from_bgra(&whole(frame), &CaptureRequest::bounded(32, 40)).unwrap_err();
    let CaptureError::TooLarge(bytes) = error else {
        panic!("expected the ladder to give up, got {error:?}");
    };
    // The reported size is the last rung reached, which is the smallest of the three.
    let smallest = encode_png(8, 8, &[0x40; 8 * 8 * 3]).unwrap().len();
    assert!(bytes > 40, "reported {bytes} bytes");
    assert!(
        bytes < smallest * 4,
        "reported {bytes} bytes, which is not the last rung"
    );
}

#[test]
fn a_caller_may_tighten_the_byte_ceiling_but_never_loosen_it() {
    assert_eq!(CaptureRequest::new(0).max_bytes(), MAX_CAPTURE_BYTES);
    assert_eq!(CaptureRequest::bounded(0, 0).max_bytes(), MAX_CAPTURE_BYTES);
    assert_eq!(CaptureRequest::bounded(0, 99).max_bytes(), 99);
    assert_eq!(
        CaptureRequest::bounded(0, u32::MAX).max_bytes(),
        MAX_CAPTURE_BYTES,
        "a caller asking for more than the seam allows gets the seam's own ceiling"
    );
}

#[test]
fn a_one_pixel_wide_frame_keeps_its_only_column_while_its_height_shrinks() {
    // The width is already 1 and cannot shrink, so only one of the two identity conditions
    // holds and the box filter still has to run.
    let frame = gradient(1, 40);
    let capture = Capture::from_bgra(&whole(frame), &CaptureRequest::new(10)).unwrap();
    let (width, height, rgb) = decode(capture.data());
    assert_eq!((width, height), (1, 10));
    assert_eq!(rgb.len(), 30);
    // The first output row averages source rows 0..4, whose blue values are 0, 1, 2, 3.
    assert_eq!(&rgb[..3], &[0x40, 0x20, 1]);
}

#[test]
fn the_ladder_shrinks_until_the_encoding_fits() {
    // 1800x1800 of noise is over the ceiling; 900x900 is not. The ladder must return the
    // second rung rather than the first or an error.
    let frame = noise(1800, 1800);
    let capture = Capture::from_bgra(&whole(frame), &CaptureRequest::new(1800)).unwrap();
    assert_eq!((capture.width(), capture.height()), (900, 900));
    assert_eq!(
        (capture.source_width(), capture.source_height()),
        (1800, 1800)
    );
    assert!(
        capture.data().len() <= MAX_CAPTURE_BYTES,
        "the ladder returned {} bytes",
        capture.data().len()
    );
    let (width, height, _) = decode(capture.data());
    assert_eq!((width, height), (900, 900));
}

#[test]
fn the_encoder_refuses_a_buffer_that_is_not_the_image() {
    let error = encode_png(2, 2, &[0; 11]).unwrap_err();
    let CaptureError::Backend(detail) = error else {
        panic!("expected a backend error");
    };
    assert!(detail.starts_with("PNG encoding failed: "), "{detail}");
}

#[test]
fn the_encoder_refuses_an_image_with_no_pixels() {
    let error = encode_png(0, 1, &[]).unwrap_err();
    let CaptureError::Backend(detail) = error else {
        panic!("expected a backend error");
    };
    assert!(detail.starts_with("PNG encoding failed: "), "{detail}");
}

#[test]
fn a_denied_backend_answers_disabled_whatever_it_is_asked() {
    let request = CaptureRequest::new(0);
    assert_eq!(
        capture_via(&DeniedScreenCapture, &request).unwrap_err(),
        CaptureError::Disabled
    );
    assert_eq!(
        DeniedScreenCapture
            .capture(&CaptureRequest::new(4096))
            .unwrap_err(),
        CaptureError::Disabled
    );
}

#[test]
fn a_backend_receives_the_resolved_request_through_the_port() {
    let backend = FakeScreen::answering(flat(4, 4, 1, 2, 3));
    let captured = capture_via(&backend, &CaptureRequest::new(0)).unwrap();
    assert_eq!(
        (captured.frame().width(), captured.frame().height()),
        (4, 4)
    );
    assert_eq!(captured, CapturedFrame::display(flat(4, 4, 1, 2, 3)));
    assert_eq!(
        backend.seen(),
        vec![CaptureRequest::new(DEFAULT_MAX_EDGE)],
        "the backend must see the resolved edge, not the raw zero"
    );
}

#[test]
fn a_backend_is_told_what_to_point_at() {
    let backend = FakeScreen::answering(flat(4, 4, 1, 2, 3));
    let request = CaptureRequest::targeted(800, 0, CaptureTarget::Focus);
    drop(capture_via(&backend, &request).unwrap());
    assert_eq!(
        backend.seen(),
        vec![request],
        "only the backend can resolve a target, so it has to be told there is one"
    );
    assert_eq!(backend.seen()[0].target(), CaptureTarget::Focus);
}

#[test]
fn a_failing_backend_reports_its_reason_through_the_port() {
    let backend = FakeScreen::failing(CaptureError::NoDisplay(String::from("lid shut")));
    assert_eq!(
        capture_via(&backend, &CaptureRequest::new(0)).unwrap_err(),
        CaptureError::NoDisplay(String::from("lid shut"))
    );
}

#[test]
fn every_capture_error_reads_as_itself() {
    assert_eq!(
        CaptureError::NoDisplay(String::from("none")).to_string(),
        "no display is available to capture: none"
    );
    assert_eq!(
        CaptureError::Disabled.to_string(),
        "screen capture is disabled on this host"
    );
    assert_eq!(
        CaptureError::Backend(String::from("gdi")).to_string(),
        "the screen-capture backend failed: gdi"
    );
    assert_eq!(
        CaptureError::TooLarge(7).to_string(),
        "the capture is too large for the seam even downscaled: 7 bytes"
    );
    assert_eq!(
        CaptureError::NoTarget(String::from("a bare desktop")).to_string(),
        "there is no window to capture: a bare desktop"
    );
}
