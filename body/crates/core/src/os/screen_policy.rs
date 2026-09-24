//! The size policy of a screen capture: how far to downscale, what to encode, and how many
//! bytes may be sent to the brain.

use crate::os::screen::CaptureError;
use crate::os::screen_image::{Rgb, downscale};
use crate::os::screen_target::{CaptureTarget, CapturedFrame, Region};

pub use crate::os::screen_image::encode_png;

/// The edge a capture is downscaled to when the caller asks for no particular size.
///
/// 1600 is chosen from measurement: the cortex charges the same 266 prompt tokens for 1280x720
/// and for 3840x2160, and 1600 keeps a little more text readable than 1280.
pub const DEFAULT_MAX_EDGE: u32 = 1600;

/// The largest long edge a caller may ask for.
pub const MAX_EDGE_CEILING: u32 = 4096;

/// The hard byte limit on one encoded capture, 6 MiB.
///
/// The brain's `CORTEX_BODY_MAX_IMAGE_BYTES` defaults to the same number and the two must
/// agree. The measured worst case, a synthetic-noise screen, encodes to 4.33 MB at 1600x900.
pub const MAX_CAPTURE_BYTES: usize = 6 * 1024 * 1024;

/// How many times [`Capture::from_bgra`] may halve the edge and re-encode before giving up.
///
/// Two, so a 1600 px request degrades through 800 to 400 and then reports
/// [`CaptureError::TooLarge`] rather than looping toward a one-pixel image.
pub const MAX_SHRINK_ATTEMPTS: u32 = 2;

/// The only image format the body sends.
pub const CAPTURE_MIME: &str = "image/png";

/// One capture's resolved policy: the wire's `max_edge` hint turned into a number the ladder can
/// act on, the byte ceiling that capture is held to, and what the caller asked the body to point
/// at.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CaptureRequest {
    max_edge: u32,
    max_bytes: usize,
    target: CaptureTarget,
}

impl CaptureRequest {
    /// Resolves a raw `max_edge` into a request for the whole display, under [`MAX_CAPTURE_BYTES`].
    #[must_use]
    pub const fn new(max_edge: u32) -> Self {
        Self::bounded(max_edge, 0)
    }

    /// Resolves both raw size hints into a request for the whole display.
    #[must_use]
    pub const fn bounded(max_edge: u32, max_bytes: u32) -> Self {
        Self::targeted(max_edge, max_bytes, CaptureTarget::Display)
    }

    /// Resolves every raw hint into a request. A zero means unset under proto3, so a zero edge
    /// becomes [`DEFAULT_MAX_EDGE`] and a zero limit [`MAX_CAPTURE_BYTES`]. Larger values are
    /// clamped down, so a caller can only tighten these bounds.
    #[must_use]
    pub const fn targeted(max_edge: u32, max_bytes: u32, target: CaptureTarget) -> Self {
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
            target,
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

    /// What the backend is to point at.
    #[must_use]
    pub const fn target(&self) -> CaptureTarget {
        self.target
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
    target_width: u32,
    target_height: u32,
    covers_display: bool,
}

impl Capture {
    /// Crops, downscales, encodes, and bounds one captured frame.
    ///
    /// # Errors
    ///
    /// `NoTarget` when the region has no pixels, `TooLarge` when the smallest rung is still too big.
    pub fn from_bgra(
        captured: &CapturedFrame,
        request: &CaptureRequest,
    ) -> Result<Self, CaptureError> {
        let frame = captured.frame();
        let region = captured.region()?;
        let mut edge = request.max_edge();
        let mut smallest = 0;
        for _ in 0..=MAX_SHRINK_ATTEMPTS {
            let image = downscale(frame, region, edge);
            let data = encode_rung(&image);
            if data.len() <= request.max_bytes() {
                return Ok(Self::encoded(data, &image, captured, region));
            }
            smallest = data.len();
            edge = image.width().max(image.height()).div_ceil(2);
        }
        Err(CaptureError::TooLarge(smallest))
    }

    /// Assembles the value once a rung of the ladder has come in under the ceiling.
    fn encoded(data: Vec<u8>, image: &Rgb, captured: &CapturedFrame, region: Region) -> Self {
        let frame = captured.frame();
        Self {
            data,
            width: image.width(),
            height: image.height(),
            source_width: frame.width(),
            source_height: frame.height(),
            target_width: region.width(),
            target_height: region.height(),
            covers_display: region.covers(frame.width(), frame.height()),
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

    /// The width of the part of the display the picture shows, before the downscale.
    #[must_use]
    pub const fn target_width(&self) -> u32 {
        self.target_width
    }

    /// The height of the part of the display the picture shows, before the downscale.
    #[must_use]
    pub const fn target_height(&self) -> u32 {
        self.target_height
    }

    /// Whether this picture is the whole display rather than one window of it.
    #[must_use]
    pub const fn covers_display(&self) -> bool {
        self.covers_display
    }
}

/// Encodes one rung of the ladder, returning no bytes if the encoder rejects the image.
fn encode_rung(image: &Rgb) -> Vec<u8> {
    encode_png(image.width(), image.height(), image.pixels()).unwrap_or_default()
}
