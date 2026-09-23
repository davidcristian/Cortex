//! The screen-capture port: the trait, the raw pixels that cross it, the failures it reports,
//! the refusing backend a switched-off host uses, and the fixed text of the receipt the body
//! shows afterwards.

use crate::os::screen_policy::CaptureRequest;
use crate::os::screen_target::CapturedFrame;

/// The heading of the receipt shown after a capture.
///
/// The receipt text is fixed and written by the body, so a brain acting on injected
/// instructions cannot word the notice about its own capture.
pub const CAPTURE_RECEIPT_TITLE: &str = "Screen captured";

/// The message of the body-authored capture receipt when the whole display was sent.
pub const CAPTURE_RECEIPT_BODY_DISPLAY: &str =
    "A picture of your screen was sent to the assistant.";

/// The message of the same receipt when only one window was sent.
pub const CAPTURE_RECEIPT_BODY_WINDOW: &str = "A picture of one window was sent to the assistant.";

/// The correlation id on the capture receipt.
pub const CAPTURE_RECEIPT_ID: &str = "screen-capture";

/// Why a screen capture failed.
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
pub enum CaptureError {
    /// No display to capture (no attached monitor, a headless session).
    #[error("no display is available to capture: {0}")]
    NoDisplay(String),
    /// Screen capture is switched off on this host, so no picture was taken.
    #[error("screen capture is disabled on this host")]
    Disabled,
    /// The OS capture backend refused or failed the call, or handed back a frame that is not a
    /// frame.
    #[error("the screen-capture backend failed: {0}")]
    Backend(String),
    /// A targeted capture found nothing to point at: no window on this desktop passed the
    /// resolution rules, or the one that did lies entirely off the captured display.
    #[error("there is no window to capture: {0}")]
    NoTarget(String),
    /// The capture still exceeded [`MAX_CAPTURE_BYTES`] after the shrink ladder ran out.
    #[error("the capture is too large to send to the brain even downscaled: {0} bytes")]
    TooLarge(usize),
}

/// Raw pixels exactly as an OS backend read them: 4 bytes per pixel, blue, green, red, then one
/// byte the backend does not promise anything about, in top-down row order. GDI leaves that
/// byte undefined, so treating it as transparency would make whole captures invisible.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RawFrame {
    width: u32,
    height: u32,
    pixels: Vec<u8>,
}

impl RawFrame {
    /// Builds a frame from a backend's buffer, checking it matches the dimensions it claims.
    ///
    /// # Errors
    ///
    /// [`CaptureError::Backend`] when a dimension is zero or the buffer is not `width * height * 4`.
    pub fn new(width: u32, height: u32, pixels: Vec<u8>) -> Result<Self, CaptureError> {
        if width == 0 || height == 0 {
            return Err(CaptureError::Backend(format!(
                "the frame is {width}x{height}, which has no pixels"
            )));
        }
        let expected = u64::from(width) * u64::from(height) * 4;
        if pixels.len() as u64 != expected {
            return Err(CaptureError::Backend(format!(
                "the frame is {width}x{height} but holds {} bytes, not {expected}",
                pixels.len()
            )));
        }
        Ok(Self {
            width,
            height,
            pixels,
        })
    }

    /// The frame's width in physical pixels.
    #[must_use]
    pub const fn width(&self) -> u32 {
        self.width
    }

    /// The frame's height in physical pixels.
    #[must_use]
    pub const fn height(&self) -> u32 {
        self.height
    }

    /// The BGRA bytes, `width * height * 4` of them.
    #[must_use]
    pub fn pixels(&self) -> &[u8] {
        &self.pixels
    }
}

/// The port a screen-capture backend implements, real only in `os_windows`, over GDI.
pub trait ScreenCapture: Send + Sync {
    /// Reads the primary display, with the request's target resolved to a rectangle in its pixels.
    ///
    /// # Errors
    ///
    /// [`CaptureError`] when no display exists, capture is off, no window matches, or it fails.
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError>;
}

/// The [`ScreenCapture`] backend that always refuses, answering [`CaptureError::Disabled`].
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct DeniedScreenCapture;

impl ScreenCapture for DeniedScreenCapture {
    fn capture(&self, _request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        Err(CaptureError::Disabled)
    }
}
