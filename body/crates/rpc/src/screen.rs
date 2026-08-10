//! The `CaptureScreen` half of the body's `BodyService` server (ADR-0029): request
//! translation, the pure-core policy call, the body-authored receipt, and the wire mapping.

use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use body_core::os::screen::{
    CAPTURE_RECEIPT_BODY_DISPLAY, CAPTURE_RECEIPT_BODY_WINDOW, CAPTURE_RECEIPT_ID,
    CAPTURE_RECEIPT_TITLE,
};
use body_core::{
    Capture, CaptureError, CaptureRequest, CaptureTarget, Notification, Notify, ScreenCapture,
};
use tonic::Status;

use crate::generated::CaptureTarget as PbCaptureTarget;
use crate::generated::{CaptureScreenReply, ImageBlob};
use crate::server::off_worker;

/// Takes one capture and answers the wire reply.
pub(crate) async fn capture<S: ScreenCapture + 'static, N: Notify + 'static>(
    screen: &Arc<S>,
    notifier: &Arc<N>,
    max_edge: u32,
    max_bytes: u32,
    target: i32,
    receipts: bool,
) -> Result<CaptureScreenReply, Status> {
    let request = CaptureRequest::targeted(max_edge, max_bytes, resolve_target(target));
    let screen = Arc::clone(screen);
    let notifier = Arc::clone(notifier);
    let (capture, captured_at_unix_ms) = off_worker(
        move || {
            let frame = screen.capture(&request)?;
            let taken = Capture::from_bgra(&frame, &request)?;
            let at = unix_millis();
            announce(&notifier, &taken, receipts);
            Ok::<_, CaptureError>((taken, at))
        },
        capture_error_to_status,
    )
    .await?;
    Ok(CaptureScreenReply {
        resolved_target: encoded_target(&capture).into(),
        image: Some(blob(&capture, captured_at_unix_ms)),
    })
}

/// Says on the reply which of the two things the picture is, so the brain can describe it
/// honestly instead of calling a crop a shrunk screen.
fn encoded_target(capture: &Capture) -> PbCaptureTarget {
    if capture.covers_display() {
        PbCaptureTarget::Display
    } else {
        PbCaptureTarget::Focus
    }
}

/// Reads the wire's target enum as one of the two things the body knows how to point at.
fn resolve_target(target: i32) -> CaptureTarget {
    match PbCaptureTarget::try_from(target) {
        Ok(PbCaptureTarget::Focus) => CaptureTarget::Focus,
        Ok(PbCaptureTarget::Display) | Err(_) => CaptureTarget::Display,
    }
}

/// Tells the user what was read, from fixed body-owned strings.
fn announce<N: Notify>(notifier: &Arc<N>, taken: &Capture, receipts: bool) {
    if receipts {
        let body = if taken.covers_display() {
            CAPTURE_RECEIPT_BODY_DISPLAY
        } else {
            CAPTURE_RECEIPT_BODY_WINDOW
        };
        let receipt = Notification::new(CAPTURE_RECEIPT_TITLE, body, CAPTURE_RECEIPT_ID, false);
        drop(notifier.show(&receipt));
    }
}

/// Wall-clock milliseconds since the Unix epoch, or zero if the host clock is set before it.
/// A capture with no honest timestamp reports none rather than a fiction.
fn unix_millis() -> i64 {
    let since_epoch = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    i64::try_from(since_epoch.as_millis()).unwrap_or(i64::MAX)
}

/// Maps a bounded [`Capture`] onto the wire message. Every field the proto declares is filled
/// from the value, including the source size the brain shows the model so it knows it is
/// looking at a shrunk view of a larger screen.
fn blob(capture: &Capture, captured_at_unix_ms: i64) -> ImageBlob {
    ImageBlob {
        data: capture.data().to_vec(),
        mime_type: String::from(capture.mime_type()),
        width: capture.width(),
        height: capture.height(),
        source_width: capture.source_width(),
        source_height: capture.source_height(),
        captured_at_unix_ms,
    }
}

/// Maps a [`CaptureError`] to the outbound gRPC [`Status`] the brain reads, on the same split the
/// volume and notification mappings use.
fn capture_error_to_status(error: &CaptureError) -> Status {
    match error {
        CaptureError::NoDisplay(detail) => {
            Status::failed_precondition(format!("no display: {detail}"))
        }
        CaptureError::NoTarget(detail) => {
            Status::failed_precondition(format!("no capture target: {detail}"))
        }
        CaptureError::Disabled => {
            Status::permission_denied("screen capture is disabled on this host")
        }
        CaptureError::Backend(detail) => {
            Status::internal(format!("screen capture backend error: {detail}"))
        }
        CaptureError::TooLarge(bytes) => Status::resource_exhausted(format!(
            "the capture is too large for the seam: {bytes} bytes"
        )),
    }
}
