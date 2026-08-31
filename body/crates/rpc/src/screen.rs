//! The `CaptureScreen` half of the body's `BodyService` server (ADR-0029): request
//! translation, the pure-core policy call, the body-authored receipt, and the wire mapping.
//!
//! A thin adapter, like the rest of this crate. Nothing here decides how big a picture may be,
//! how it is encoded, or which part of the screen it is, because `body_core::Capture::from_bgra`
//! owns all of that and is gated where CI can see it. What lives here is what cannot: the clock
//! read that timestamps the frame, the ordering that fires the receipt on the same thread that
//! took the picture, and the one piece of wire vocabulary with no core equivalent, an enum value
//! this body does not name, which proto3 says to read as the default.
//!
//! Split out of [`crate::server`] so that file stays a table of one-line handlers with room
//! for `InjectInput` later.

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
///
/// The blit, the encode, and the receipt all run inside a single blocking-pool hop: they are
/// three synchronous OS-adjacent steps for one user intent, and splitting them across hops
/// would let the receipt for one capture interleave with the next.
///
/// `receipts` is the resolved `CORTEX_HOST_CAPTURE_NOTIFY` switch. It is passed in rather than
/// read here because reading the environment is the host shell's job.
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

/// Says on the reply which of the two things the picture is, so the brain does not describe a
/// crop as a shrunk screen.
///
/// It reads the encoded capture rather than the request, which is the same predicate the receipt
/// is picked by ([`announce`]), so the sentence the user is shown and the sentence the model
/// reads cannot disagree about what was sent. A window filling the display answers `Display`,
/// because the picture is the whole screen.
///
/// It reports the resolved target and not the rectangle it resolved to. Coordinates would hand
/// the model back the coordinate frame this seam declined to take from it, and the target is all
/// the description needs.
fn encoded_target(capture: &Capture) -> PbCaptureTarget {
    if capture.covers_display() {
        PbCaptureTarget::Display
    } else {
        PbCaptureTarget::Focus
    }
}

/// Reads the wire's target enum as one of the two things the body knows how to point at.
///
/// A value the enum does not name reads as the whole display, which is proto3's own rule for an
/// unrecognized enum: a newer brain is asking for something this body cannot resolve, and the
/// picture it gets back is the one this seam has always sent. The arm exists because the wire
/// type is an `i32` on the far side of a network, so the value can be anything.
fn resolve_target(target: i32) -> CaptureTarget {
    match PbCaptureTarget::try_from(target) {
        Ok(PbCaptureTarget::Focus) => CaptureTarget::Focus,
        Ok(PbCaptureTarget::Display) | Err(_) => CaptureTarget::Display,
    }
}

/// Tells the user what was read, from fixed body-owned strings.
///
/// The sentence is picked by what the capture carries rather than by what the brain asked for:
/// a targeted request that came back as the whole display says so, and a window filling the
/// display reports a screen capture. Neither string ever names the window, because a title is
/// attacker-chosen text.
///
/// The notification is best effort. By the time this runs the pixels have already been read, so
/// failing the call because the notification service is down would not un-take the picture; it
/// would only lose a working capability for no privacy gain, on a host that still has the kill
/// switch and the overlay indicator. The receipt is untainted because the body wrote every word
/// of it: a notice describing untrusted content is never built from that content.
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

/// Wall-clock milliseconds since the Unix epoch, or zero if the host clock is set before it, so
/// a capture whose timestamp cannot be read reports none rather than a made-up one.
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

/// Maps a [`CaptureError`] to the outbound gRPC [`Status`] the brain reads, on the same split
/// the volume and notification mappings use. Every code here is chosen so the brain can
/// classify it: a laptop with its lid shut is `FailedPrecondition` (host state, and it works
/// again once the state is fixed), a desktop with no window worth pointing at is the same code
/// for the same reason (it works again the moment one is on screen, and the brain's own reading
/// of that code, "the host is not in a state to capture the screen", is exactly true of it), a
/// host that switched capture off is `PermissionDenied` (a standing answer the brain should not
/// retry into), a picture that stays too big even after the shrink ladder is `ResourceExhausted`
/// (it was taken, and it will not fit), and a backend fault is `Internal`.
///
/// Nothing here returns `Unavailable`. tonic synthesizes that code client-side when a channel
/// cannot connect, and the brain's grpc-python client cannot tell a synthesized status from a
/// sent one, so a body returning it for a shut lid would be indistinguishable from a body that is
/// not running at all. Leaving it unused makes `Unavailable` on this seam mean one thing: the
/// call never arrived.
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
