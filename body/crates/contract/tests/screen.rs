use body_contract::FakeScreen;
use body_contract::screen::{ScreenSubject, run};
use body_core::{CaptureError, RawFrame, ScreenCapture, TargetRect};

struct Fake;

impl ScreenSubject for Fake {
    fn showing(&self, frame: RawFrame) -> Box<dyn ScreenCapture> {
        Box::new(FakeScreen::answering(frame))
    }

    fn pointing_at(&self, frame: RawFrame, window: TargetRect) -> Option<Box<dyn ScreenCapture>> {
        Some(Box::new(FakeScreen::showing(frame, window)))
    }

    fn without_display(&self) -> Box<dyn ScreenCapture> {
        Box::new(FakeScreen::failing(CaptureError::NoDisplay(String::from(
            "lid shut",
        ))))
    }

    fn broken(&self) -> Box<dyn ScreenCapture> {
        Box::new(FakeScreen::failing(CaptureError::Backend(String::from(
            "BitBlt failed",
        ))))
    }
}

#[test]
fn the_fake_meets_every_screen_check() {
    run(&Fake);
}
