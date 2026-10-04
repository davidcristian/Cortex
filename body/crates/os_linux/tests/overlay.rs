#![cfg(target_os = "linux")]

use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;

use body_core::{
    CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, RawFrame, ScreenCapture,
};
use os_linux::{HiddenOverlayCapture, OverlayWatch};

const HOUR: Duration = Duration::from_hours(1);

#[derive(Clone, Copy)]
enum During {
    Nothing,
    Show,
    ShowAndHide,
    Fail,
}

struct FakeCapture {
    watch: Arc<OverlayWatch>,
    during: During,
    calls: Arc<AtomicUsize>,
}

impl ScreenCapture for FakeCapture {
    fn capture(&self, _request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        match self.during {
            During::Nothing => {}
            During::Show => self.watch.showing(),
            During::ShowAndHide => {
                self.watch.showing();
                self.watch.hidden();
            }
            During::Fail => return Err(CaptureError::NoDisplay(String::from("gone"))),
        }
        let frame = RawFrame::new(1, 1, vec![1, 2, 3, 255])
            .unwrap_or_else(|error| panic!("a 1 by 1 frame failed: {error:?}"));
        Ok(CapturedFrame::display(frame))
    }
}

fn guarded(
    watch: &Arc<OverlayWatch>,
    during: During,
    settle: Duration,
) -> (HiddenOverlayCapture<FakeCapture>, Arc<AtomicUsize>) {
    let calls = Arc::new(AtomicUsize::new(0));
    let fake = FakeCapture {
        watch: Arc::clone(watch),
        during,
        calls: Arc::clone(&calls),
    };
    (
        HiddenOverlayCapture::new(fake, Arc::clone(watch), settle),
        calls,
    )
}

fn display() -> CaptureRequest {
    CaptureRequest::targeted(0, 0, CaptureTarget::Display)
}

fn refused(result: Result<CapturedFrame, CaptureError>) {
    match result {
        Err(CaptureError::Backend(message)) => assert!(message.contains("overlay"), "{message}"),
        other => panic!("expected the overlay refusal, got {other:?}"),
    }
}

#[test]
fn a_capture_passes_through_when_the_overlay_was_never_shown() {
    let watch = Arc::new(OverlayWatch::default());

    let captured = guarded(&watch, During::Nothing, HOUR).0.capture(&display());

    let captured = captured.unwrap_or_else(|error| panic!("the capture failed: {error:?}"));
    assert_eq!(captured.frame().pixels(), [1, 2, 3, 255]);
}

#[test]
fn a_capture_is_refused_without_a_picture_while_the_overlay_is_shown() {
    let watch = Arc::new(OverlayWatch::default());
    watch.showing();
    let (capture, calls) = guarded(&watch, During::Nothing, Duration::ZERO);

    refused(capture.capture(&display()));
    assert_eq!(calls.load(Ordering::SeqCst), 0);
}

#[test]
fn a_capture_is_refused_while_a_hidden_overlay_settles() {
    let watch = Arc::new(OverlayWatch::default());
    watch.showing();
    watch.hidden();
    let (capture, calls) = guarded(&watch, During::Nothing, HOUR);

    refused(capture.capture(&display()));
    assert_eq!(calls.load(Ordering::SeqCst), 0);
}

#[test]
fn a_capture_passes_once_the_hidden_overlay_has_settled() {
    let watch = Arc::new(OverlayWatch::default());
    watch.showing();
    watch.hidden();

    let captured = guarded(&watch, During::Nothing, Duration::ZERO)
        .0
        .capture(&display());

    assert!(captured.is_ok(), "{captured:?}");
}

#[test]
fn a_picture_taken_while_the_overlay_was_shown_is_discarded() {
    let watch = Arc::new(OverlayWatch::default());
    let (capture, calls) = guarded(&watch, During::Show, Duration::ZERO);

    refused(capture.capture(&display()));
    assert_eq!(calls.load(Ordering::SeqCst), 1);
}

#[test]
fn a_picture_is_discarded_when_the_overlay_was_shown_and_hidden_during_the_call() {
    let watch = Arc::new(OverlayWatch::default());

    refused(
        guarded(&watch, During::ShowAndHide, Duration::ZERO)
            .0
            .capture(&display()),
    );
}

#[test]
fn a_failed_capture_keeps_its_own_error() {
    let watch = Arc::new(OverlayWatch::default());

    let result = guarded(&watch, During::Fail, Duration::ZERO)
        .0
        .capture(&display());

    assert!(
        matches!(result, Err(CaptureError::NoDisplay(ref text)) if text == "gone"),
        "{result:?}"
    );
}
