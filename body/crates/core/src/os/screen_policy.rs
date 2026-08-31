//! The size policy of a screen capture (ADR-0029): how far to downscale, what to encode, and
//! how many bytes may cross the seam.
//!
//! Split from the port in [`screen`](super::screen) by responsibility. That module declares
//! what a backend implements; this one decides what is allowed to reach the brain. The pixel
//! arithmetic both rest on is in `screen_image`.

use crate::os::screen::CaptureError;
use crate::os::screen_image::{Rgb, downscale};
use crate::os::screen_target::{CaptureTarget, CapturedFrame, Region};

pub use crate::os::screen_image::encode_png;

/// The longest edge, in physical pixels, a capture is downscaled to when the caller asks for
/// no particular size (a proto3 `max_edge` of zero).
///
/// 1600 is chosen from measurement: the cortex's projector charges the same 266 prompt tokens for
/// 1280x720 and for 3840x2160, so past roughly 1280 on the long edge a bigger picture costs
/// bytes without buying context legibility. 1600 keeps a little more text readable than 1280
/// while a worst-case incompressible screen still encodes inside [`MAX_CAPTURE_BYTES`]
/// without the ladder firing.
///
/// `tests/capture_bytes.rs` prints every screen's cost at this edge beside the cost at the one
/// the brain asks for, and imports this constant rather than spelling the number again, so
/// retuning it here cannot leave that measurement comparing against an edge nothing captures
/// at. Its neighbour `BRAIN_EDGE` belongs to the brain and cannot be imported the same way, so
/// `scripts/crosscheck.py` holds it instead.
pub const DEFAULT_MAX_EDGE: u32 = 1600;

/// The largest long edge a caller may ask for. A request above this is clamped rather than
/// refused, because the caller is asking for detail and the most this seam will carry is a
/// more useful answer than an error the caller cannot act on.
pub const MAX_EDGE_CEILING: u32 = 4096;

/// The hard byte ceiling on one encoded capture, 6 MiB.
///
/// The brain's `CORTEX_BODY_MAX_IMAGE_BYTES` defaults to this same number and the two must
/// agree. A body ceiling looser than the brain's domain bound would let a capture pass here
/// and be refused there, and a ceiling tighter than the measured worst case (a
/// synthetic-noise screen encodes to 4.33 MB at 1600x900) would trip the halving ladder on
/// any photographic screen and silently drop the user to an 800 px view. 6 MiB clears that
/// worst case with headroom, so the ladder fires only on pathological input. Neither
/// toolchain can import the other's constant, so `scripts/crosscheck.py` reads both
/// declarations and fails when they disagree, while each stays pinned to the same literal in
/// its own suite. Editing this value means editing the brain's too.
pub const MAX_CAPTURE_BYTES: usize = 6 * 1024 * 1024;

/// How many times [`Capture::from_bgra`] may halve the edge and re-encode before giving up.
/// Two, so a 1600 px request degrades through 800 to 400 and then answers
/// [`CaptureError::TooLarge`] rather than looping toward a one-pixel image.
pub const MAX_SHRINK_ATTEMPTS: u32 = 2;

/// The only image format this seam emits in v1. PNG because the body encodes pixels it owns
/// and lossless keeps small text as legible as the downscale left it.
pub const CAPTURE_MIME: &str = "image/png";

/// One capture's resolved policy: the wire's `max_edge` hint turned into a number the ladder
/// can act on, the byte ceiling that capture is held to, and what the caller asked the body to
/// point at.
///
/// Private fields plus accessors (the [`Notification`](super::Notification) shape rather
/// than the [`VolumeState`](super::VolumeState) one) because the value carries an invariant:
/// an existing `CaptureRequest` always names an edge inside `1..=MAX_EDGE_CEILING`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CaptureRequest {
    max_edge: u32,
    max_bytes: usize,
    target: CaptureTarget,
}

impl CaptureRequest {
    /// Resolves a raw wire `max_edge` into a request for the whole display, held to the seam's
    /// own [`MAX_CAPTURE_BYTES`] ceiling.
    #[must_use]
    pub const fn new(max_edge: u32) -> Self {
        Self::bounded(max_edge, 0)
    }

    /// Resolves both raw size hints into a request for the whole display.
    #[must_use]
    pub const fn bounded(max_edge: u32, max_bytes: u32) -> Self {
        Self::targeted(max_edge, max_bytes, CaptureTarget::Display)
    }

    /// Resolves every raw wire hint into a request. This is what the `BodyService` handler
    /// calls.
    ///
    /// Zero means "unset" under proto3, which is indistinguishable from an explicit zero, so a
    /// zero edge becomes [`DEFAULT_MAX_EDGE`] and a zero ceiling becomes [`MAX_CAPTURE_BYTES`].
    /// An edge above [`MAX_EDGE_CEILING`] and a ceiling above [`MAX_CAPTURE_BYTES`] are both
    /// clamped down, so a caller can only ever tighten this seam's bounds, never loosen them.
    /// The resolution lives here, pure and gated, for the same reason
    /// [`VolumeChange::new`](super::VolumeChange::new) clamps here: no OS backend should ever
    /// receive a constraint the wire could not enforce.
    ///
    /// The byte ceiling is carried on the request rather than fixed inside the ladder because
    /// it is one number shared with the brain, whose own image budget is an env var, so the
    /// caller names the ceiling it will accept. It is also what makes the give-up arm of the
    /// ladder reachable from a test: at [`MAX_CAPTURE_BYTES`] with a [`MAX_EDGE_CEILING`]
    /// edge, the arithmetic guarantees the third rung fits.
    ///
    /// `target` needs no resolution of its own: the wire's unknown-value case is decided by the
    /// adapter that reads the enum off the wire, and by the time it arrives here it is one of
    /// two things the body knows how to point at.
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

    /// What the backend is to point at. Unlike the two size hints, the core does not re-apply
    /// this one: only the OS can resolve it, so the backend's answer settles it and the core
    /// only crops to the region that answer names.
    #[must_use]
    pub const fn target(&self) -> CaptureTarget {
        self.target
    }
}

/// An encoded capture, bounded and ready for the wire.
///
/// Constructed only through [`Capture::from_bgra`], so an existing value is always inside
/// [`MAX_CAPTURE_BYTES`] and always [`CAPTURE_MIME`]. It carries the display's own size, so the
/// brain can tell the model it is looking at a shrunk view, and whether the picture is that
/// whole display or one window of it, which picks the receipt the user sees.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Capture {
    data: Vec<u8>,
    width: u32,
    height: u32,
    source_width: u32,
    source_height: u32,
    covers_display: bool,
}

impl Capture {
    /// Crops, downscales, encodes, and bounds one captured frame.
    ///
    /// The crop comes first and runs outside the ladder: the region the backend resolved is
    /// the only part of the frame that is ever read, so a window already inside the capture
    /// edge crosses the seam pixel for pixel through the identity arm of `downscale`, where
    /// the same desktop captured whole would spend the same image tokens on a resampled
    /// screen.
    ///
    /// The ladder follows: shrink so the long edge is at most `request.max_edge()`, PNG-encode,
    /// and while the result is over `request.max_bytes()` halve the edge and try again, up to
    /// [`MAX_SHRINK_ATTEMPTS`] times. The size is checked after encoding rather than predicted
    /// before it, because how many bytes a screen costs depends on what is on it: a flat
    /// desktop is kilobytes at 1600x900 and a photograph is megabytes.
    ///
    /// Each rung halves the edge the previous rung reached rather than the edge it asked for,
    /// so every rung is strictly smaller than the last even when the region was already inside
    /// the requested bound and the first rung did nothing.
    ///
    /// # Errors
    ///
    /// [`CaptureError::NoTarget`] if the resolved region has no pixels on the display, before
    /// anything is encoded. [`CaptureError::TooLarge`] if even the smallest rung is over the
    /// ceiling, carrying the size it got down to.
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
    ///
    /// The source size is the display's rather than the region's, which is why this takes a
    /// [`CapturedFrame`] instead of a pre-cropped frame. Three consumers read it as the size
    /// of the screen: `ImageBlob.source_*` on the wire, `ScreenCapture.downscaled` in the
    /// brain's own pure core, and the "downscaled from `WxH`" clause the tool shows the model.
    /// A cropped frame flowing through here would make all three report the window as though
    /// it were the screen.
    fn encoded(data: Vec<u8>, image: &Rgb, captured: &CapturedFrame, region: Region) -> Self {
        let frame = captured.frame();
        Self {
            data,
            width: image.width(),
            height: image.height(),
            source_width: frame.width(),
            source_height: frame.height(),
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

    /// Whether this picture is the whole display rather than one window of it.
    ///
    /// The only consumer is the body's own receipt, which has to say which of the two things
    /// happened. It reports what was encoded rather than what was asked for, so a window
    /// covering the entire display reports a screen capture, and a backend that answered a
    /// whole frame to a targeted request cannot make the notice say otherwise.
    #[must_use]
    pub const fn covers_display(&self) -> bool {
        self.covers_display
    }
}

/// Encodes one rung of the ladder, returning no bytes if the encoder rejects the image.
///
/// [`encode_png`] rejects exactly two things, a zero dimension and a buffer that is not
/// `width * height * 3` bytes, and `downscale` can produce neither, so the `Err` arm of that
/// call is unreachable from here. It needs no coverage escape, because the unreachable arm
/// lives inside `Result::unwrap_or_default`, which is std's line rather than a region of this
/// function, and `encode_png`'s own rejects stay gated where a caller can provoke them.
///
/// Returning no bytes rather than an error keeps a branch no test can take out of the ladder.
/// The impossible case is still not silent: the brain's own image validation rejects an empty
/// blob with a message the model can read.
fn encode_rung(image: &Rgb) -> Vec<u8> {
    encode_png(image.width(), image.height(), image.pixels()).unwrap_or_default()
}
