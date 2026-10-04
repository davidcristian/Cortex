//! The `ScreenCapture` check list: what every capturing backend owes, read through the port alone.

use std::iter;
use std::mem::{Discriminant, discriminant};

use body_core::os::MAX_EDGE_CEILING;
use body_core::{
    CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, RawFrame, ScreenCapture, TargetRect,
};

/// Builds the implementation under test in each condition a check needs.
pub trait ScreenSubject {
    /// An implementation whose primary display shows `frame` with no window to point at.
    fn showing(&self, frame: RawFrame) -> Box<dyn ScreenCapture>;

    /// An implementation whose display shows `frame` and whose focus resolves to `window`.
    fn pointing_at(&self, frame: RawFrame, window: TargetRect) -> Box<dyn ScreenCapture>;

    /// An implementation with no display to capture.
    fn without_display(&self) -> Box<dyn ScreenCapture>;

    /// An implementation whose backend fails every call for any other reason.
    fn broken(&self) -> Box<dyn ScreenCapture>;
}

/// One check and its name, run against a subject.
pub type ScreenCheck = (&'static str, fn(&dyn ScreenSubject));

/// Every check a capturing backend owes, in the order a driver runs them.
pub const SCREEN_CHECKS: [ScreenCheck; 6] = named![fn(&dyn ScreenSubject);
    a_display_capture_answers_the_whole_display,
    a_focus_capture_names_the_window_on_the_whole_display,
    a_display_capture_leaves_the_focused_window_out,
    a_focus_capture_with_no_window_fails,
    no_display_fails_as_no_display,
    a_broken_backend_fails_as_a_backend_error,
];

/// Runs every check against `subject`, naming each on stderr first so a failure shows which.
pub fn run(subject: &dyn ScreenSubject) {
    for (name, check) in SCREEN_CHECKS {
        eprintln!("screen check: {name}");
        check(subject);
    }
}

/// The edges a request may ask for; the backend answers the display at its own size for each.
const EDGES: [u32; 3] = [0, 1, MAX_EDGE_CEILING];

/// The sizes of the frames a display shows, each byte of each its own value.
const SIZES: [(u32, u32); 2] = [(2, 1), (3, 3)];

/// A window the focus resolves to, on part of each frame and off the edge of the smaller one.
const WINDOW: TargetRect = TargetRect::new(1, 0, 3, 2);

fn displays() -> Vec<RawFrame> {
    let frames: Vec<RawFrame> = SIZES
        .into_iter()
        .flat_map(|(width, height)| {
            let bytes = iter::successors(Some(0_u8), |byte| Some(byte.wrapping_add(7)));
            RawFrame::new(
                width,
                height,
                bytes.take((width * height * 4) as usize).collect(),
            )
        })
        .collect();
    assert_eq!(frames.len(), SIZES.len(), "every fixture frame is a frame");
    frames
}

/// The frame's size and its blue, green and red bytes, without the fourth byte no backend promises.
fn picture(frame: &RawFrame) -> (u32, u32, Vec<u8>) {
    let colours = frame
        .pixels()
        .chunks_exact(4)
        .flat_map(|pixel| pixel.iter().take(3))
        .copied()
        .collect();
    (frame.width(), frame.height(), colours)
}

/// What a capture shows, and whether it names the window it was meant to.
type Shown = ((u32, u32, Vec<u8>), bool);

/// Which error a call failed with, without its text, which each backend writes its own way.
fn kind(result: &Result<CapturedFrame, CaptureError>) -> Option<Discriminant<CaptureError>> {
    result.as_ref().err().map(discriminant)
}

/// The error kind and what a capture shows, where `window` is the one it names or `None` for none.
fn seen(
    result: &Result<CapturedFrame, CaptureError>,
    window: Option<TargetRect>,
) -> (Option<Discriminant<CaptureError>>, Option<Shown>) {
    let shown = result.as_ref().ok().map(|captured| {
        let frame = captured.frame().clone();
        let named = window.map_or_else(
            || CapturedFrame::display(frame.clone()),
            |rect| CapturedFrame::window(frame.clone(), rect),
        );
        (picture(&frame), *captured == named)
    });
    (kind(result), shown)
}

/// What a correct capture of `frame` shows: no error, the frame's colours, and the right window.
fn whole(frame: &RawFrame) -> (Option<Discriminant<CaptureError>>, Option<Shown>) {
    (None, Some((picture(frame), true)))
}

fn request(edge: u32, target: CaptureTarget) -> CaptureRequest {
    CaptureRequest::targeted(edge, 0, target)
}

fn a_display_capture_answers_the_whole_display(subject: &dyn ScreenSubject) {
    for shown in displays() {
        let screen = subject.showing(shown.clone());
        for edge in EDGES {
            let captured = screen.capture(&request(edge, CaptureTarget::Display));
            assert_eq!(seen(&captured, None), whole(&shown));
        }
    }
}

fn a_focus_capture_names_the_window_on_the_whole_display(subject: &dyn ScreenSubject) {
    for shown in displays() {
        let screen = subject.pointing_at(shown.clone(), WINDOW);
        for edge in EDGES {
            let captured = screen.capture(&request(edge, CaptureTarget::Focus));
            assert_eq!(seen(&captured, Some(WINDOW)), whole(&shown));
        }
    }
}

fn a_display_capture_leaves_the_focused_window_out(subject: &dyn ScreenSubject) {
    for shown in displays() {
        let screen = subject.pointing_at(shown.clone(), WINDOW);
        let captured = screen.capture(&request(0, CaptureTarget::Display));
        assert_eq!(seen(&captured, None), whole(&shown));
    }
}

fn a_focus_capture_with_no_window_fails(subject: &dyn ScreenSubject) {
    for shown in displays() {
        let captured = subject
            .showing(shown)
            .capture(&request(0, CaptureTarget::Focus));
        assert_ne!(kind(&captured), None);
    }
}

fn no_display_fails_as_no_display(subject: &dyn ScreenSubject) {
    let screen = subject.without_display();
    let missing = Some(discriminant(&CaptureError::NoDisplay(String::new())));
    for edge in EDGES {
        let captured = screen.capture(&request(edge, CaptureTarget::Display));
        assert_eq!(kind(&captured), missing);
    }
}

fn a_broken_backend_fails_as_a_backend_error(subject: &dyn ScreenSubject) {
    let screen = subject.broken();
    let failed = Some(discriminant(&CaptureError::Backend(String::new())));
    assert_eq!(
        kind(&screen.capture(&request(0, CaptureTarget::Display))),
        failed
    );
}
