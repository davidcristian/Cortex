//! The `CaptureScreen` half of the body's `BodyService` server (ADR-0029): request
//! translation, the pure-core policy call, the body-authored receipt, and the wire mapping.
//!
//! A thin adapter, like the rest of this crate. Nothing here decides how big a picture may be
//! or how it is encoded; `body_core::Capture::from_bgra` owns all of that and is gated where
//! CI can see it. What lives here is what genuinely cannot: the clock read that timestamps the
//! frame, and the ordering that fires the receipt on the same thread that took the picture.
//!
//! Split out of [`crate::server`] so that file stays a table of one-line handlers with room
//! for `InjectInput` later.

use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use body_core::os::screen::{CAPTURE_RECEIPT_BODY, CAPTURE_RECEIPT_ID, CAPTURE_RECEIPT_TITLE};
use body_core::{Capture, CaptureError, CaptureRequest, Notification, Notify, ScreenCapture};
use tonic::Status;

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
    receipts: bool,
) -> Result<CaptureScreenReply, Status> {
    let request = CaptureRequest::bounded(max_edge, max_bytes);
    let screen = Arc::clone(screen);
    let notifier = Arc::clone(notifier);
    let (capture, captured_at_unix_ms) = off_worker(
        move || {
            let frame = screen.capture(&request)?;
            let taken = Capture::from_bgra(&frame, &request)?;
            let at = unix_millis();
            announce(&notifier, receipts);
            Ok::<_, CaptureError>((taken, at))
        },
        capture_error_to_status,
    )
    .await?;
    Ok(CaptureScreenReply {
        image: Some(blob(&capture, captured_at_unix_ms)),
    })
}

/// Tells the user their screen was read, from fixed body-owned strings.
///
/// **Best effort, and deliberately so.** By the time this runs the pixels have already been
/// read, so refusing to answer because the notification service is down would not un-take the
/// picture; it would only trade a working capability for no privacy gain, on a host that still
/// has the kill switch and the overlay indicator. The receipt is untainted because the body
/// wrote every word of it: a notice describing untrusted content may never be built from that
/// content.
fn announce<N: Notify>(notifier: &Arc<N>, receipts: bool) {
    if receipts {
        let receipt = Notification::new(
            CAPTURE_RECEIPT_TITLE,
            CAPTURE_RECEIPT_BODY,
            CAPTURE_RECEIPT_ID,
            false,
        );
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

/// Maps a [`CaptureError`] to the outbound gRPC [`Status`] the brain reads, on the same split
/// the volume and notification mappings use. Every code here is chosen so the brain can
/// classify it: a laptop with its lid shut is `FailedPrecondition` (host state, and it works
/// again once the state is fixed), a host that switched capture off is `PermissionDenied` (a
/// standing answer the brain should not retry into), a picture that stays too big even after
/// the shrink ladder is `ResourceExhausted` (it was taken, and it will not fit), and a backend
/// fault is `Internal`.
///
/// **Nothing here says `Unavailable`.** tonic synthesizes that code client-side when a channel
/// cannot connect, and the brain's grpc-python client cannot tell a synthesized status from a
/// sent one, so a body spending it on a shut lid would be indistinguishable from a body that is
/// not running at all. Leaving it unspent makes `Unavailable` on this seam mean exactly one
/// thing: the call never arrived.
fn capture_error_to_status(error: &CaptureError) -> Status {
    match error {
        CaptureError::NoDisplay(detail) => {
            Status::failed_precondition(format!("no display: {detail}"))
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
