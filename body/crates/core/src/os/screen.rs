//! The screen-capture port (ADR-0029), the third OS capability the brain drives over
//! `BodyService` after [`AudioControl`](super::AudioControl) and [`Notify`](super::Notify),
//! and the first whose return value is a payload rather than a status.
//!
//! This module holds the port and nothing else: the trait, the raw pixels that cross it, the
//! failures it can report, the refusing backend a switched-off host wires, and the fixed
//! strings of the receipt the body shows afterwards. Every size decision lives in
//! [`screen_policy`](super::screen_policy), what a capture is pointed at in
//! [`screen_target`](super::screen_target), and the pixel arithmetic behind both in
//! `screen_image`.
//!
//! The policy is core rather than backend for the reason [`escape_xml`] is pure
//! ([`super::notify`]): the only real backend is `cfg(windows)`, which CI never compiles and
//! coverage never measures, so keeping the byte ceiling and the downscale ladder there would
//! rest the seam's size guarantee on code no gate can see. It also means nothing in Cortex
//! decodes a foreign image, because the body encodes pixels it captured itself.
//!
//! [`escape_xml`]: super::escape_xml

use crate::os::screen_policy::CaptureRequest;
use crate::os::screen_target::CapturedFrame;

/// The heading of the body-authored receipt shown after a capture.
///
/// Fixed and body-owned, like [`UNTRUSTED_ATTRIBUTION`](super::UNTRUSTED_ATTRIBUTION): the
/// notice telling the user their screen was read is never built from anything the brain sent,
/// so a brain acting on injected instructions cannot word the notice about its own capture.
pub const CAPTURE_RECEIPT_TITLE: &str = "Screen captured";

/// The message of the body-authored capture receipt when the whole display was sent. Says what
/// happened in the user's terms and names no model, tool, or window title.
pub const CAPTURE_RECEIPT_BODY_DISPLAY: &str =
    "A picture of your screen was sent to the assistant.";

/// The message of the same receipt when only one window was sent.
///
/// A second fixed string rather than one sentence with the target interpolated, so the body
/// picks between two sentences it wrote itself. It does not name the window: a window title
/// is attacker-chosen text, which is why ADR-0029 keeps titles out of the capture result at
/// all, and quoting one in the receipt would put that text back in front of the user.
pub const CAPTURE_RECEIPT_BODY_WINDOW: &str = "A picture of one window was sent to the assistant.";

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
    /// A targeted capture found nothing to point at: no window on this desktop passed the
    /// resolution rules, or the one that did lies entirely off the captured display. `0` says
    /// which. There is no silent fallback to the whole display, which would send more of the
    /// screen than was asked for without the model or the receipt reflecting it.
    #[error("there is no window to capture: {0}")]
    NoTarget(String),
    /// The capture still exceeded [`MAX_CAPTURE_BYTES`] after the shrink ladder ran out.
    /// `0` is the smallest encoding reached, in bytes.
    #[error("the capture is too large for the seam even downscaled: {0} bytes")]
    TooLarge(usize),
}

/// Raw pixels exactly as an OS backend read them: 4 bytes per pixel, blue, green, red, then
/// one byte the backend does not promise anything about, in top-down row order.
///
/// The alpha byte is deliberately unspecified. GDI leaves it undefined, so treating it as
/// transparency would render whole captures invisible; the encoder drops it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RawFrame {
    width: u32,
    height: u32,
    pixels: Vec<u8>,
}

impl RawFrame {
    /// Builds a frame from a backend's buffer, checking that the buffer matches the
    /// dimensions it claims.
    ///
    /// # Errors
    ///
    /// [`CaptureError::Backend`] if either dimension is zero or the buffer is not exactly
    /// `width * height * 4` bytes. A backend that miscounts is a backend bug, and catching it
    /// at the boundary keeps every later index in the policy in range by construction.
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
///
/// The method is synchronous because the OS call is: a blit blocks, and declaring it
/// `async fn` would not make it yield. Keeping it off the async worker is the server's job,
/// which hands the call to the blocking pool exactly as it does for the volume and
/// notification ports.
///
/// `Send + Sync` for the same reason those two carry the bound and single-threaded
/// [`Hotkey`](super::Hotkey) does not: the body's `BodyService` server holds the backend
/// across async tasks. Backends are stateless, so nothing here violates the one hard rule;
/// the pixels exist only for the duration of the call that returns them.
pub trait ScreenCapture: Send + Sync {
    /// Reads the primary display and returns its raw BGRA pixels, with the request's target
    /// resolved to a rectangle inside them.
    ///
    /// The backend does not downscale, encode, crop, or bound anything. It resolves the
    /// target, because only the OS knows where windows are, and reports what it found beside
    /// the whole frame. `request`'s size hints are passed so a future backend that can ask the
    /// OS for a cheaper read has the numbers, and the policy in [`Capture::from_bgra`]
    /// re-applies all of them either way. The extra information is carried in the return value
    /// rather than in a second method, which keeps everything a crop can get wrong in the pure
    /// core where the coverage gate reaches it.
    ///
    /// # Errors
    ///
    /// [`CaptureError`] if no display is available, capture is disabled on this host, a
    /// targeted capture finds no window to point at, or the backend fails.
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError>;
}

/// The [`ScreenCapture`] backend that always refuses, answering [`CaptureError::Disabled`].
///
/// This is what the host shell wires unless the user opts in, and what it falls back to if
/// the overlay cannot exclude itself from capture. Refusing is a capability here rather than
/// a missing platform, so this is real gated code on every platform rather than an
/// `unimplemented!()` stub, and the refusal stays under test.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct DeniedScreenCapture;

impl ScreenCapture for DeniedScreenCapture {
    fn capture(&self, _request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        Err(CaptureError::Disabled)
    }
}
