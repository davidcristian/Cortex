//! Opens the window chooser at a hide of the overlay, while a focus capture wants a window.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::Duration;

use body_core::{CaptureError, CaptureRequest, CapturedFrame, ScreenCapture};

use crate::screencast::{FrameReader, Grant, LinuxWindowCapture, ScreenCastPortal, choose};

/// How long a chooser opened at a hide waits for the user, as long as `SHORTCUTS_LIMIT`.
pub const CHOOSER_LIMIT: Duration = Duration::from_mins(1);

/// The overlay's hides, as the chooser thread waits for them.
pub trait HideSignal: Send + Sync {
    /// Waits until the overlay is hidden and its hide count is not `seen`, and returns the count.
    /// Returns `None` once `stop` is set and no such hide is recorded.
    fn next_hide(&self, seen: u64, stop: &AtomicBool) -> Option<u64>;

    /// Wakes every waiting [`Self::next_hide`], so that it reads its `stop` again.
    fn wake(&self);
}

/// A window capture with a thread that opens its chooser at each hide while a choice is wanted.
/// Dropping it ends the thread once any chooser it opened has closed.
pub struct WatchedWindowCapture<P, R> {
    window: Arc<LinuxWindowCapture<P, R>>,
    signal: Arc<dyn HideSignal>,
    stop: Arc<AtomicBool>,
}

impl<P, R> LinuxWindowCapture<P, R>
where
    P: ScreenCastPortal + 'static,
    R: FrameReader + 'static,
{
    /// Starts a thread that calls [`Self::choose`] with `limit` at each hide `signal` reports
    /// while [`Self::choice_wanted`] is set, one chooser at a time.
    #[must_use]
    pub fn watch_hides(
        self,
        signal: Arc<dyn HideSignal>,
        limit: Duration,
    ) -> WatchedWindowCapture<P, R> {
        let window = Arc::new(self);
        let stop = Arc::new(AtomicBool::new(false));
        let (capture, hides, stopped) =
            (Arc::clone(&window), Arc::clone(&signal), Arc::clone(&stop));
        thread::spawn(move || {
            listen(
                &capture.portal,
                &capture.grant,
                hides.as_ref(),
                &stopped,
                limit,
            );
        });
        WatchedWindowCapture {
            window,
            signal,
            stop,
        }
    }
}

impl<P, R> WatchedWindowCapture<P, R> {
    /// The window capture the thread opens the chooser of.
    #[must_use]
    pub fn window(&self) -> &LinuxWindowCapture<P, R> {
        &self.window
    }
}

impl<P: ScreenCastPortal, R: FrameReader> ScreenCapture for WatchedWindowCapture<P, R> {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        self.window.capture(request)
    }
}

impl<P, R> Drop for WatchedWindowCapture<P, R> {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        self.signal.wake();
    }
}

fn listen(
    portal: &dyn ScreenCastPortal,
    grant: &Grant,
    signal: &dyn HideSignal,
    stop: &AtomicBool,
    limit: Duration,
) {
    let mut seen = 0;
    while let Some(hides) = signal.next_hide(seen, stop) {
        seen = hides;
        if grant.wanted() {
            // A chooser whose call failed keeps nothing, as a cancelled one does.
            let _ = choose(portal, grant, limit);
        }
    }
}
