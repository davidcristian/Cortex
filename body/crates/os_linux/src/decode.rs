//! Decodes the PNG file a screenshot portal writes into the core's BGRA frame.

use std::io::Cursor;

use body_core::{CaptureError, RawFrame};
use png::{ColorType, Decoder, Transformations};

/// The most decoded bytes a picture may hold, 256 MiB: an 8192 by 8192 RGBA screen.
///
/// The size comes from the file's header, so this bound is checked before the buffer is made.
pub const MAX_DECODED_BYTES: usize = 256 * 1024 * 1024;

/// Decodes `bytes`, expanded to 8-bit channels, to a BGRA frame whose fourth byte is 255.
///
/// # Errors
///
/// [`CaptureError::Backend`] for bytes that are not a PNG, too large a picture, or a grey one.
pub fn decode_png(bytes: &[u8]) -> Result<RawFrame, CaptureError> {
    let mut decoder = Decoder::new(Cursor::new(bytes));
    decoder.set_transformations(Transformations::normalize_to_color8());
    let mut reader = decoder.read_info().map_err(|error| unreadable(&error))?;
    let size = reader.output_buffer_size().unwrap_or(usize::MAX);
    if size > MAX_DECODED_BYTES {
        let (width, height) = reader.info().size();
        return Err(CaptureError::Backend(format!(
            "the picture is {width}x{height}, over the {MAX_DECODED_BYTES} byte decode limit"
        )));
    }
    let mut buffer = vec![0; size];
    let info = reader
        .next_frame(&mut buffer)
        .map_err(|error| unreadable(&error))?;
    let channels = match info.color_type {
        ColorType::Rgb => 3,
        ColorType::Rgba => 4,
        other => {
            return Err(CaptureError::Backend(format!(
                "the picture is {other:?}, not RGB or RGBA"
            )));
        }
    };
    buffer.truncate(info.buffer_size());
    let pixels = buffer
        .chunks_exact(channels)
        .flat_map(|pixel| [pixel[2], pixel[1], pixel[0], u8::MAX])
        .collect();
    RawFrame::new(info.width, info.height, pixels)
}

fn unreadable(error: &png::DecodingError) -> CaptureError {
    CaptureError::Backend(format!("the picture file is not a readable PNG: {error}"))
}
