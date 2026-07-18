//! The size policy of a screen capture (ADR-0029): how far to downscale, what to encode, and
//! how many bytes may cross the seam.
//!
//! Split from the port in [`screen`](super::screen) by responsibility. That module answers
//! "what does a backend implement"; this one answers "what is allowed to reach the brain",
//! which is the half a security review reads. The pixel arithmetic both rest on is in
//! `screen_image`.

use crate::os::screen::{CaptureError, RawFrame};
use crate::os::screen_image::{Rgb, downscale};

pub use crate::os::screen_image::encode_png;

/// The longest edge, in physical pixels, a capture is downscaled to when the caller asks for
/// no particular size (a proto3 `max_edge` of zero).
///
/// 1600 is chosen from measurement, not taste: the cortex's projector charges the same 266
/// prompt tokens for 1280x720 and for 3840x2160, so past roughly 1280 on the long edge a
/// bigger picture buys context legibility at the price of bytes only. 1600 keeps a little
/// more text readable than 1280 while a worst-case incompressible screen still encodes
/// inside [`MAX_CAPTURE_BYTES`] without the ladder firing.
pub const DEFAULT_MAX_EDGE: u32 = 1600;

/// The largest long edge a caller may ask for. A request above this is clamped, not refused:
/// the brain is asking for detail, and silently giving it the most this seam will carry is
/// friendlier than an error it cannot act on.
pub const MAX_EDGE_CEILING: u32 = 4096;

/// The hard byte ceiling on one encoded capture, 6 MiB.
///
/// **One ceiling, two enforcers.** The brain's `CORTEX_BODY_MAX_IMAGE_BYTES` defaults to this
/// same number, and the two must agree: a body ceiling looser than the brain's domain bound
/// would let a capture pass here and be refused there, and a ceiling tighter than the
/// measured worst case (a synthetic-noise screen encodes to 4.33 MB at 1600x900) would trip
/// the halving ladder on any photographic screen and silently drop the user to an 800 px
/// view. 6 MiB clears that worst case with headroom, so the ladder fires only on genuinely
/// pathological input. Nothing mechanical couples the two constants; they are pinned to the
/// same literal in each toolchain and that coupling is a documented invariant.
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
///
/// Private fields plus accessors (the [`Notification`](super::Notification) shape rather
/// than the [`VolumeState`](super::VolumeState) one) because the value carries an invariant:
/// an existing `CaptureRequest` always names an edge inside `1..=MAX_EDGE_CEILING`.
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
    ///
    /// Zero means "unset" under proto3, which is indistinguishable from an explicit zero, so a
    /// zero edge becomes [`DEFAULT_MAX_EDGE`] and a zero ceiling becomes [`MAX_CAPTURE_BYTES`].
    /// An edge above [`MAX_EDGE_CEILING`] and a ceiling above [`MAX_CAPTURE_BYTES`] are both
    /// clamped down, so a caller can only ever tighten this seam's bounds, never loosen them.
    /// The resolution lives here, pure and gated, for the same reason
    /// [`VolumeChange::new`](super::VolumeChange::new) clamps here: no OS backend should ever
    /// receive a constraint the wire could not enforce.
    ///
    /// The byte ceiling rides the request rather than being baked into the ladder because it
    /// is one number shared with the brain, whose own image budget is an env var: letting the
    /// caller name it is what makes "one ceiling, two enforcers" a mechanism instead of a
    /// comment. It is also what makes the give-up arm of the ladder reachable at all, since at
    /// [`MAX_CAPTURE_BYTES`] with a [`MAX_EDGE_CEILING`] edge the arithmetic guarantees the
    /// third rung fits, and a branch nothing can take is a gate that cannot fail.
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
///
/// Constructed only through [`Capture::from_bgra`], so an existing value is always inside
/// [`MAX_CAPTURE_BYTES`] and always [`CAPTURE_MIME`]. It remembers the display's own size so
/// the brain can tell the model it is looking at a shrunk view.
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
    ///
    /// The ladder: shrink so the long edge is at most `request.max_edge()`, PNG-encode, and
    /// while the result is over `request.max_bytes()` halve the edge and try again, up to
    /// [`MAX_SHRINK_ATTEMPTS`] times. Verifying the size *after* encoding is the only honest
    /// order, because how many bytes a screen costs depends on what is on it: a flat desktop
    /// is kilobytes at 1600x900 and a photograph is megabytes.
    ///
    /// Each rung halves the edge the previous rung actually *reached*, not the edge it asked
    /// for, so every rung is strictly smaller than the last even when the frame was already
    /// inside the requested bound and the first rung did nothing.
    ///
    /// # Errors
    ///
    /// [`CaptureError::TooLarge`] if even the smallest rung is over the ceiling, carrying the
    /// size it got down to.
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
///
/// Coverage escape (AGENTS.md gate 2): [`encode_png`] rejects exactly two things, a zero
/// dimension and a buffer that is not `width * height * 3` bytes, and `downscale` can produce
/// neither, so the failing arm is genuinely unreachable. The escape sits on this three-line
/// wrapper rather than on the ladder, which stays fully measured, and `encode_png`'s own
/// rejects stay gated where a caller can provoke them.
///
/// Answering with no bytes rather than an error keeps the ladder free of a branch nothing can
/// take, and it does not swallow the impossible case: an empty blob is refused by the brain's
/// own image validation with a message the model can read, so the failure would surface at the
/// next gate instead of becoming a picture of nothing.
#[cfg_attr(coverage, coverage(off))]
fn encode_rung(image: &Rgb) -> Vec<u8> {
    encode_png(image.width(), image.height(), image.pixels()).unwrap_or_default()
}
