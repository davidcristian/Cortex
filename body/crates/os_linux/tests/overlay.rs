#![cfg(target_os = "linux")]

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::thread;
use std::time::Duration;

use body_core::{
    CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, RawFrame, ScreenCapture,
};
use os_linux::{HiddenOverlayCapture, HideSignal, OverlayWatch};

const HOUR: Duration = Duration::from_hours(1);
/// Time for a reader thread to start and block before the test acts, as the portal tests allow.
const SETTLE_IN: Duration = Duration::from_millis(200);

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

#[test]
fn a_hide_not_yet_seen_is_returned_at_once_even_when_stopped() {
    let watch = OverlayWatch::default();
    watch.showing();
    watch.hidden();
    watch.showing();
    watch.hidden();

    assert_eq!(watch.next_hide(0, &AtomicBool::new(true)), Some(2));
    assert_eq!(watch.next_hide(1, &AtomicBool::new(false)), Some(2));
}

#[test]
fn a_hide_already_seen_or_followed_by_a_show_is_not_returned() {
    let stopped = AtomicBool::new(true);
    let watch = OverlayWatch::default();
    assert_eq!(watch.next_hide(0, &stopped), None);
    watch.hidden();
    assert_eq!(watch.next_hide(1, &stopped), None);

    watch.showing();

    assert_eq!(watch.next_hide(0, &stopped), None);
}

#[test]
fn a_waiting_reader_is_woken_by_the_next_hide() {
    let watch = OverlayWatch::default();
    let stop = AtomicBool::new(false);

    let hide = thread::scope(|scope| {
        let waiting = scope.spawn(|| watch.next_hide(0, &stop));
        thread::sleep(SETTLE_IN);
        watch.showing();
        watch.hidden();
        waiting.join()
    });

    assert_eq!(hide.ok(), Some(Some(1)));
}

#[test]
fn a_waiting_reader_is_woken_to_stop() {
    let watch = OverlayWatch::default();
    let stop = AtomicBool::new(false);

    let hide = thread::scope(|scope| {
        let waiting = scope.spawn(|| watch.next_hide(0, &stop));
        thread::sleep(SETTLE_IN);
        stop.store(true, Ordering::SeqCst);
        watch.wake();
        waiting.join()
    });

    assert_eq!(hide.ok(), Some(None));
}
