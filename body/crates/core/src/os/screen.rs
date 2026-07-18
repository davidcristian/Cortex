//! The screen-capture port (ADR-0029), the third OS capability the brain drives over
//! `BodyService` after [`AudioControl`](super::AudioControl) and [`Notify`](super::Notify),
//! and the first whose *return value* is a payload rather than a status.

use crate::os::screen_policy::CaptureRequest;

/// The heading of the body-authored receipt shown after a capture.
pub const CAPTURE_RECEIPT_TITLE: &str = "Screen captured";

/// The message of the body-authored capture receipt. Says what happened in the user's terms
/// and names no model, tool, or window title.
pub const CAPTURE_RECEIPT_BODY: &str = "A picture of your screen was sent to the assistant.";

/// The correlation id the capture receipt carries. `Notification` was shaped for reminders,
/// so a capture borrows the field with a fixed body-owned marker rather than a reminder id.
pub const CAPTURE_RECEIPT_ID: &str = "screen-capture";

/// Why a screen capture failed. See [`ScreenCapture`].
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
pub enum CaptureError {
    /// No display to capture (no attached monitor, a headless session). `0` is a backend
    /// detail.
    #[error("no display is available to capture: {0}")]
    NoDisplay(String),
    /// Screen capture is switched off on this host, so no picture was taken. The host kill
    /// switch and [`DeniedScreenCapture`] answer this.
    #[error("screen capture is disabled on this host")]
    Disabled,
    /// The OS capture backend refused or failed the call, or handed back a frame that is not
    /// a frame. `0` is a backend detail.
    #[error("the screen-capture backend failed: {0}")]
    Backend(String),
    /// The capture still exceeded [`MAX_CAPTURE_BYTES`] after the shrink ladder ran out.
    /// `0` is the smallest encoding reached, in bytes.
    #[error("the capture is too large for the seam even downscaled: {0} bytes")]
    TooLarge(usize),
}

/// Raw pixels exactly as an OS backend read them: 4 bytes per pixel, blue, green, red, then
/// one byte the backend does not promise anything about, in top-down row order.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RawFrame {
    width: u32,
    height: u32,
    pixels: Vec<u8>,
}

impl RawFrame {
    /// Builds a frame from a backend's buffer, checking that it *is* one.
    pub fn new(width: u32, height: u32, pixels: Vec<u8>) -> Result<Self, CaptureError> {
        if width == 0 || height == 0 {
            return Err(CaptureError::Backend(format!(
                "the frame is {width}x{height}, which has no pixels"
            )));
        }
        let expected = u64::from(width) * u64::from(height) * 4;
        if pixels.len() as u64 != expected {
            return Err(CaptureError::Backend(format!(
                "the frame is {width}x{height} but carries {} bytes, not {expected}",
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

/// The port a screen-capture backend implements (`os_windows` real via GDI; other platforms
/// are stubs until built, per ADR-0011). The third OS capability the brain drives over
/// `BodyService`, after [`AudioControl`](super::AudioControl) and [`Notify`](super::Notify).
pub trait ScreenCapture: Send + Sync {
    /// Reads the primary display and returns its raw BGRA pixels.
    fn capture(&self, request: &CaptureRequest) -> Result<RawFrame, CaptureError>;
}

/// The [`ScreenCapture`] backend that always refuses, answering [`CaptureError::Disabled`].
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct DeniedScreenCapture;

impl ScreenCapture for DeniedScreenCapture {
    fn capture(&self, _request: &CaptureRequest) -> Result<RawFrame, CaptureError> {
        Err(CaptureError::Disabled)
    }
}
