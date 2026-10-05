//! Sends each capture request to the capture of its target.

use body_core::{CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, ScreenCapture};

/// A capture that sends a focus request to one capture and a display request to another.
pub struct TargetRouter<F, D> {
    focus: F,
    display: D,
}

impl<F, D> TargetRouter<F, D> {
    /// Sends focus requests to `focus` and display requests to `display`.
    #[must_use]
    pub const fn new(focus: F, display: D) -> Self {
        Self { focus, display }
    }
}

impl<F: ScreenCapture, D: ScreenCapture> ScreenCapture for TargetRouter<F, D> {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        route(request.target(), &self.focus, &self.display).capture(request)
    }
}

// Not generic, so that the branch is counted once for every pair of captures.
fn route<'a>(
    target: CaptureTarget,
    focus: &'a dyn ScreenCapture,
    display: &'a dyn ScreenCapture,
) -> &'a dyn ScreenCapture {
    match target {
        CaptureTarget::Focus => focus,
        CaptureTarget::Display => display,
    }
}
