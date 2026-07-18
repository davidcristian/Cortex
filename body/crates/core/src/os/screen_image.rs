//! The image arithmetic behind the capture policy: the downscaler and the PNG encoder
//! [`Capture::from_bgra`](super::screen_policy::Capture::from_bgra) runs (ADR-0029).
//!
//! Split from [`screen_policy`](super::screen_policy) by responsibility rather than by size:
//! that module decides how big a picture may be, this one owns pixels in and bytes out and
//! knows nothing about requests, ladders, or the wire beyond the one error type it reports
//! through.
//!
//! Both steps are pure and fully gated, which is the point of doing them here instead of in
//! the `cfg(windows)` backend that produces the frames.

use crate::os::screen::CaptureError;

/// An image the encoder can take: three bytes per pixel, red, green, blue, top-down.
///
/// Alpha is already gone. An OS blit leaves the fourth BGRA byte undefined (GDI does), so
/// carrying it into a PNG would encode a transparency channel out of uninitialized memory and
/// could render an entire capture invisible. Dropping it also cuts a quarter of the bytes
/// before compression ever runs.
pub(crate) struct Rgb {
    width: u32,
    height: u32,
    pixels: Vec<u8>,
}

impl Rgb {
    /// The image's width in pixels.
    pub(crate) const fn width(&self) -> u32 {
        self.width
    }

    /// The image's height in pixels.
    pub(crate) const fn height(&self) -> u32 {
        self.height
    }

    /// The RGB bytes, `width * height * 3` of them.
    pub(crate) fn pixels(&self) -> &[u8] {
        &self.pixels
    }
}

/// Shrinks `frame` so its longest edge is at most `bound`, dropping alpha either way.
///
/// A box filter, averaging each destination pixel over the source rectangle it covers. It is
/// the cheap resampler that still tells the truth about a shrunk screen: dropping pixels
/// instead (nearest neighbour) deletes exactly the thin strokes that text is made of, and a
/// screenshot the model cannot read is the failure mode this whole slice is trying to avoid.
///
/// The identity arm is separate and does no averaging, so a screen already inside the bound
/// crosses the seam pixel-for-pixel.
pub(crate) fn downscale(frame: &super::screen::RawFrame, bound: u32) -> Rgb {
    let (width, height) = scaled_dimensions(frame.width(), frame.height(), bound);
    if width == frame.width() && height == frame.height() {
        return Rgb {
            width,
            height,
            pixels: drop_alpha(frame.pixels()),
        };
    }
    box_filter(frame, width, height)
}

/// The size `width x height` shrinks to so its longest edge is at most `bound`, keeping the
/// aspect ratio and never returning a zero edge. Never upscales: a bound above the longest
/// edge returns the size unchanged.
fn scaled_dimensions(width: u32, height: u32, bound: u32) -> (u32, u32) {
    let longest = width.max(height);
    if longest <= bound {
        return (width, height);
    }
    (
        scale_edge(width, bound, longest),
        scale_edge(height, bound, longest),
    )
}

/// Scales one edge by `bound / longest`, floored, with a floor of one pixel.
///
/// The multiply is done in `u64` so a wide frame cannot overflow it. The result is never
/// larger than `value` (this is only reached when `bound < longest`), so the narrowing back to
/// `u32` cannot lose anything and the fallback is arithmetic insurance, not a policy.
fn scale_edge(value: u32, bound: u32, longest: u32) -> u32 {
    let scaled = u64::from(value) * u64::from(bound) / u64::from(longest);
    u32::try_from(scaled).unwrap_or(value).max(1)
}

/// Drops the undefined fourth byte of every BGRA pixel and reorders the rest to RGB.
fn drop_alpha(pixels: &[u8]) -> Vec<u8> {
    pixels
        .chunks_exact(4)
        .flat_map(|pixel| [pixel[2], pixel[1], pixel[0]])
        .collect()
}

/// Averages `frame` down to `width x height`.
///
/// Only ever called with a destination no larger than the source in either axis, which is what
/// makes the source rectangle for each destination pixel non-empty: with `dst <= src` the real
/// span `src / dst` is at least one, so the floored start and end of consecutive destination
/// columns always differ by at least one source column. That is why there is no empty-span
/// guard here and no division by zero in [`average`].
fn box_filter(frame: &super::screen::RawFrame, width: u32, height: u32) -> Rgb {
    let source = frame.pixels();
    let src_width = frame.width() as usize;
    let src_height = frame.height() as usize;
    let dst_width = width as usize;
    let dst_height = height as usize;
    let mut pixels = Vec::with_capacity(dst_width * dst_height * 3);
    for y in 0..dst_height {
        let (first_row, last_row) = (
            y * src_height / dst_height,
            (y + 1) * src_height / dst_height,
        );
        for x in 0..dst_width {
            let (first_col, last_col) =
                (x * src_width / dst_width, (x + 1) * src_width / dst_width);
            let (mut blue, mut green, mut red, mut count) = (0_u64, 0_u64, 0_u64, 0_u64);
            for row in first_row..last_row {
                for col in first_col..last_col {
                    let at = (row * src_width + col) * 4;
                    blue += u64::from(source[at]);
                    green += u64::from(source[at + 1]);
                    red += u64::from(source[at + 2]);
                    count += 1;
                }
            }
            pixels.push(average(red, count));
            pixels.push(average(green, count));
            pixels.push(average(blue, count));
        }
    }
    Rgb {
        width,
        height,
        pixels,
    }
}

/// The mean of `count` colour bytes. Every term is a byte so the mean is one too; the fallback
/// is arithmetic insurance rather than a policy.
fn average(total: u64, count: u64) -> u8 {
    u8::try_from(total / count).unwrap_or(u8::MAX)
}

/// PNG-encodes `rgb`, three bytes per pixel at eight bits per channel.
///
/// Public because it is the one step of the policy whose failure a caller has to be able to
/// provoke: the encoder is the only place a malformed buffer or a zero dimension turns into a
/// [`CaptureError`], and a gate that cannot be made to fail is not a gate.
///
/// # Errors
///
/// [`CaptureError::Backend`] if either dimension is zero or `rgb` is not exactly
/// `width * height * 3` bytes.
pub fn encode_png(width: u32, height: u32, rgb: &[u8]) -> Result<Vec<u8>, CaptureError> {
    let mut encoded = Vec::new();
    write_png(width, height, rgb, &mut encoded)
        .map_err(|error| CaptureError::Backend(format!("PNG encoding failed: {error}")))?;
    Ok(encoded)
}

/// Writes the PNG stream into `out`, in the `png` crate's own error currency.
///
/// Separated from [`encode_png`] so the crate's error type is translated exactly once: the
/// closing `finish` is the tail expression rather than a `?`, because with a `Vec` sink it
/// cannot fail and a branch nothing can take is a coverage lie.
fn write_png(
    width: u32,
    height: u32,
    rgb: &[u8],
    out: &mut Vec<u8>,
) -> Result<(), png::EncodingError> {
    let mut encoder = png::Encoder::new(out, width, height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header()?;
    writer.write_image_data(rgb)?;
    writer.finish()
}
