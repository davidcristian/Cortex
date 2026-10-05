#![cfg(target_os = "linux")]

use body_core::{
    CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, RawFrame, ScreenCapture,
};
use os_linux::TargetRouter;

/// A capture that answers with a 1 by 1 frame of its own colour.
struct Painted(u8);

impl ScreenCapture for Painted {
    fn capture(&self, _request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        let frame = RawFrame::new(1, 1, vec![self.0, 0, 0, 255])
            .unwrap_or_else(|error| panic!("a 1 by 1 frame failed: {error:?}"));
        Ok(CapturedFrame::display(frame))
    }
}

fn colour(router: &TargetRouter<Painted, Painted>, target: CaptureTarget) -> u8 {
    let captured = router.capture(&CaptureRequest::targeted(0, 0, target));
    captured.map_or(0, |frame| frame.frame().pixels()[0])
}

#[test]
fn a_focus_request_goes_to_the_focus_capture_and_a_display_request_to_the_display_one() {
    let router = TargetRouter::new(Painted(7), Painted(9));

    assert_eq!(colour(&router, CaptureTarget::Focus), 7);
    assert_eq!(colour(&router, CaptureTarget::Display), 9);
}
