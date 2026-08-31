//! The image arithmetic behind the capture policy: the downscaler and the PNG encoder
//! [`Capture::from_bgra`](super::screen_policy::Capture::from_bgra) runs.

use crate::os::screen::{CaptureError, RawFrame};
use crate::os::screen_target::Region;

/// An image the encoder can take: three bytes per pixel, red, green, blue, top-down.
///
/// Alpha is already gone: an OS blit leaves the fourth BGRA byte undefined, so keeping it would
/// encode a transparency channel out of uninitialized memory.
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

/// Reads `region` out of `frame` and shrinks it so its longest edge is at most `bound`.
///
/// The shrink is a box filter. Nearest-neighbour sampling is cheaper but drops the thin strokes
/// text is made of, which leaves a screenshot the model cannot read.
pub(crate) fn downscale(frame: &RawFrame, region: Region, bound: u32) -> Rgb {
    let (width, height) = scaled_dimensions(region.width(), region.height(), bound);
    if width == region.width() && height == region.height() {
        return copy_region(frame, region);
    }
    box_filter(frame, region, width, height)
}

/// The size `width x height` shrinks to so its longest edge is at most `bound`, keeping the aspect
/// ratio and never returning a zero edge.
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

/// Scales one edge by `bound / longest`, floored, with a minimum of one pixel. The multiply is
/// done in `u64` so a wide frame cannot overflow it.
fn scale_edge(value: u32, bound: u32, longest: u32) -> u32 {
    let scaled = u64::from(value) * u64::from(bound) / u64::from(longest);
    u32::try_from(scaled).unwrap_or(value).max(1)
}

/// Copies `region` out of `frame` unscaled, dropping the undefined fourth byte of every BGRA pixel
/// and reordering the rest to RGB.
fn copy_region(frame: &RawFrame, region: Region) -> Rgb {
    let source = frame.pixels();
    let stride = frame.width() as usize;
    let (width, height) = (region.width() as usize, region.height() as usize);
    let mut pixels = Vec::with_capacity(width * height * 3);
    for row in 0..height {
        let start = ((region.y() as usize + row) * stride + region.x() as usize) * 4;
        for pixel in source[start..start + width * 4].chunks_exact(4) {
            pixels.extend_from_slice(&[pixel[2], pixel[1], pixel[0]]);
        }
    }
    Rgb {
        width: region.width(),
        height: region.height(),
        pixels,
    }
}

/// Averages `region` of `frame` down to `width x height`.
///
/// The destination is never larger than the region, so the source rectangle for each destination
/// pixel is non-empty and [`average`] cannot divide by zero.
fn box_filter(frame: &RawFrame, region: Region, width: u32, height: u32) -> Rgb {
    let source = frame.pixels();
    let stride = frame.width() as usize;
    let (off_x, off_y) = (region.x() as usize, region.y() as usize);
    let src_width = region.width() as usize;
    let src_height = region.height() as usize;
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
                    let at = ((off_y + row) * stride + off_x + col) * 4;
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

/// The mean of `count` colour bytes.
fn average(total: u64, count: u64) -> u8 {
    u8::try_from(total / count).unwrap_or(u8::MAX)
}

/// PNG-encodes `rgb`, three bytes per pixel at eight bits per channel.
///
/// # Errors
///
/// [`CaptureError::Backend`] when a dimension is zero or `rgb` is not `width * height * 3` bytes.
pub fn encode_png(width: u32, height: u32, rgb: &[u8]) -> Result<Vec<u8>, CaptureError> {
    let mut encoded = Vec::new();
    write_png(width, height, rgb, &mut encoded)
        .map_err(|error| CaptureError::Backend(format!("PNG encoding failed: {error}")))?;
    Ok(encoded)
}

/// Writes the PNG stream into `out`, returning the `png` crate's own error type.
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
