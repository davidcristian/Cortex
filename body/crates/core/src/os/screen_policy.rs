//! The size policy of a screen capture (ADR-0029): how far to downscale, what to encode, and
//! how many bytes may cross the seam.

use crate::os::screen::{CaptureError, RawFrame};
use crate::os::screen_image::{Rgb, downscale};

pub use crate::os::screen_image::encode_png;

/// The longest edge, in physical pixels, a capture is downscaled to when the caller asks for
/// no particular size (a proto3 `max_edge` of zero).
pub const DEFAULT_MAX_EDGE: u32 = 1600;

/// The largest long edge a caller may ask for. A request above this is clamped, not refused:
/// the brain is asking for detail, and silently giving it the most this seam will carry is
/// friendlier than an error it cannot act on.
pub const MAX_EDGE_CEILING: u32 = 4096;

/// The hard byte ceiling on one encoded capture, 6 MiB.
pub const MAX_CAPTURE_BYTES: usize = 6 * 1024 * 1024;

/// How many times [`Capture::from_bgra`] may halve the edge and re-encode before giving up.
/// Two, so a 1600 px request degrades through 800 to 400 and then answers
/// [`CaptureError::TooLarge`] rather than looping toward a one-pixel image.
pub const MAX_SHRINK_ATTEMPTS: u32 = 2;

/// The only image format this seam emits in v1. PNG because the body encodes pixels it owns
/// and lossless keeps small text as legible as the downscale left it.
pub const CAPTURE_MIME: &str = "image/png";

/// One capture's resolved size policy: the wire's `max_edge` hint turned into a number the
/// ladder can act on, plus the byte ceiling that capture is held to.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CaptureRequest {
    max_edge: u32,
    max_bytes: usize,
}

impl CaptureRequest {
    /// Resolves a raw wire `max_edge` into a request held to the seam's own
    /// [`MAX_CAPTURE_BYTES`] ceiling.
    #[must_use]
    pub const fn new(max_edge: u32) -> Self {
        Self::bounded(max_edge, 0)
    }

    /// Resolves both raw wire hints into a request. This is what the `BodyService` handler
    /// calls.
    #[must_use]
    pub const fn bounded(max_edge: u32, max_bytes: u32) -> Self {
        let edge = if max_edge == 0 {
            DEFAULT_MAX_EDGE
        } else if max_edge > MAX_EDGE_CEILING {
            MAX_EDGE_CEILING
        } else {
            max_edge
        };
        let bytes = max_bytes as usize;
        let ceiling = if max_bytes == 0 || bytes > MAX_CAPTURE_BYTES {
            MAX_CAPTURE_BYTES
        } else {
            bytes
        };
        Self {
            max_edge: edge,
            max_bytes: ceiling,
        }
    }

    /// The longest edge the encoded capture may have, in physical pixels.
    #[must_use]
    pub const fn max_edge(&self) -> u32 {
        self.max_edge
    }

    /// The most bytes the encoded capture may occupy.
    #[must_use]
    pub const fn max_bytes(&self) -> usize {
        self.max_bytes
    }
}

/// An encoded capture, bounded and ready for the wire.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Capture {
    data: Vec<u8>,
    width: u32,
    height: u32,
    source_width: u32,
    source_height: u32,
}

impl Capture {
    /// Downscales, encodes, and bounds one raw frame.
    pub fn from_bgra(frame: &RawFrame, request: &CaptureRequest) -> Result<Self, CaptureError> {
        let mut edge = request.max_edge();
        let mut smallest = 0;
        for _ in 0..=MAX_SHRINK_ATTEMPTS {
            let image = downscale(frame, edge);
            let data = encode_rung(&image);
            if data.len() <= request.max_bytes() {
                return Ok(Self::encoded(data, &image, frame));
            }
            smallest = data.len();
            edge = image.width().max(image.height()).div_ceil(2);
        }
        Err(CaptureError::TooLarge(smallest))
    }

    /// Assembles the value once a rung of the ladder has come in under the ceiling.
    fn encoded(data: Vec<u8>, image: &Rgb, frame: &RawFrame) -> Self {
        Self {
            data,
            width: image.width(),
            height: image.height(),
            source_width: frame.width(),
            source_height: frame.height(),
        }
    }

    /// The encoded image bytes, at most [`MAX_CAPTURE_BYTES`] of them.
    #[must_use]
    pub fn data(&self) -> &[u8] {
        &self.data
    }

    /// The encoding, always [`CAPTURE_MIME`].
    #[must_use]
    pub const fn mime_type(&self) -> &'static str {
        CAPTURE_MIME
    }

    /// The encoded image's width in physical pixels, after any downscale.
    #[must_use]
    pub const fn width(&self) -> u32 {
        self.width
    }

    /// The encoded image's height in physical pixels, after any downscale.
    #[must_use]
    pub const fn height(&self) -> u32 {
        self.height
    }

    /// The display's own width, before the downscale.
    #[must_use]
    pub const fn source_width(&self) -> u32 {
        self.source_width
    }

    /// The display's own height, before the downscale.
    #[must_use]
    pub const fn source_height(&self) -> u32 {
        self.source_height
    }
}

/// Encodes one rung of the ladder, or nothing at all if the encoder somehow refuses it.
fn encode_rung(image: &Rgb) -> Vec<u8> {
    encode_png(image.width(), image.height(), image.pixels()).unwrap_or_default()
}
