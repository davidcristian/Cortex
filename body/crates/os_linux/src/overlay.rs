//! Keeps the overlay out of a capture whose picture cannot leave a window out, as on Wayland.

use std::sync::{Arc, Mutex, MutexGuard, PoisonError};
use std::time::{Duration, Instant};

use body_core::{CaptureError, CaptureRequest, CapturedFrame, ScreenCapture};

/// How long a capture stays refused after the overlay is hidden, so that a compositor's close
/// animation has left the screen: about three times picom's default fade.
pub const OVERLAY_SETTLE: Duration = Duration::from_secs(1);

/// What the shell reports about the overlay window as it shows and hides it.
#[derive(Debug, Default)]
pub struct OverlayWatch {
    seen: Mutex<Seen>,
}

#[derive(Clone, Copy, Debug, Default)]
struct Seen {
    shown: bool,
    shows: u64,
    hidden_at: Option<Instant>,
}

impl OverlayWatch {
    /// Records that the overlay is about to be shown; the shell calls it before showing it.
    pub fn showing(&self) {
        let mut seen = self.lock();
        seen.shown = true;
        seen.shows = seen.shows.wrapping_add(1);
    }

    /// Records that the overlay was hidden; the shell calls it only after a hide succeeded.
    pub fn hidden(&self) {
        let mut seen = self.lock();
        seen.shown = false;
        seen.hidden_at = Some(Instant::now());
    }

    fn seen(&self) -> Seen {
        *self.lock()
    }

    fn lock(&self) -> MutexGuard<'_, Seen> {
        self.seen.lock().unwrap_or_else(PoisonError::into_inner)
    }
}

/// A capture refused while the overlay is shown or settling, and discarded when it was shown
/// during the call.
pub struct HiddenOverlayCapture<S> {
    inner: S,
    watch: Arc<OverlayWatch>,
    settle: Duration,
}

impl<S> HiddenOverlayCapture<S> {
    /// Wraps `inner`, refusing for `settle` after each hide that `watch` records.
    #[must_use]
    pub const fn new(inner: S, watch: Arc<OverlayWatch>, settle: Duration) -> Self {
        Self {
            inner,
            watch,
            settle,
        }
    }
}

impl<S: ScreenCapture> ScreenCapture for HiddenOverlayCapture<S> {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        let before = self.watch.seen();
        let settling = before
            .hidden_at
            .is_some_and(|hidden| hidden.elapsed() < self.settle);
        if before.shown || settling {
            return Err(refused());
        }
        let frame = self.inner.capture(request)?;
        if self.watch.seen().shows != before.shows {
            return Err(refused());
        }
        Ok(frame)
    }
}

fn refused() -> CaptureError {
    CaptureError::Backend(String::from(
        "the overlay is or was just on screen, and this picture cannot leave it out",
    ))
}
