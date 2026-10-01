//! Builds a capture from each top-level window's own pixels, for a screen a compositing manager
//! paints, so no fade, shadow or other compositor output reaches it.

use body_core::CaptureError;

use crate::exclude::{Span, points};
use crate::screen::{Area, Layer, TreeWindow, to_bgra};

/// One window read a composed capture needs, with where the part read lies on the root.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Piece {
    /// The window's index in the window list.
    pub window: usize,
    /// The part to read, from the window's inside corner.
    pub inside: Area,
    /// The same part, from the root's corner.
    pub place: Area,
}

/// Lists the part inside `area` of every viewable top-level window that has pixels, bottom to top
/// as the list orders them, so no read reaches past the screen.
#[must_use]
pub fn pieces(windows: &[TreeWindow], area: Area) -> Vec<Piece> {
    let shown =
        |window: &&TreeWindow| window.parent.is_none() && window.viewable && !window.input_only;
    let (screen_x, screen_y) = (i32::from(area.x), i32::from(area.y));
    let (screen_right, screen_bottom) = (
        screen_x + i32::from(area.width),
        screen_y + i32::from(area.height),
    );
    let mut pieces = Vec::new();
    for (index, window) in windows
        .iter()
        .enumerate()
        .filter(|(_, window)| shown(window))
    {
        let border = i32::from(window.border);
        let (x, y) = (
            i32::from(window.area.x) + border,
            i32::from(window.area.y) + border,
        );
        let (left, top) = (x.max(screen_x), y.max(screen_y));
        let right = (x + i32::from(window.area.width)).min(screen_right);
        let bottom = (y + i32::from(window.area.height)).min(screen_bottom);
        if left < right && top < bottom {
            let (width, height) = (narrow(right - left), narrow(bottom - top));
            pieces.push(Piece {
                window: index,
                inside: at(left - x, top - y, width, height),
                place: at(left, top, width, height),
            });
        }
    }
    pieces
}

/// Paints each layer bottom to top over black into a BGRA image of `area`, refusing a layer whose
/// format the core cannot read or whose pixels do not fill its place.
pub fn compose(area: Area, layers: Vec<Layer>) -> Result<Vec<u8>, CaptureError> {
    let screen = Span::of(area);
    let mut pixels = vec![0; usize::from(area.width) * usize::from(area.height) * 4];
    for Layer { place, image } in layers {
        let (_, _, data) = to_bgra(image)?;
        if data.len() != usize::from(place.width) * usize::from(place.height) * 4 {
            return Err(CaptureError::Backend(format!(
                "a window read of {} by {} returned {} bytes",
                place.width,
                place.height,
                data.len()
            )));
        }
        for (pixel, (x, y)) in data.chunks_exact(4).zip(points(place)) {
            if screen.holds(x, y) {
                let start = screen.offset(x, y);
                pixels[start..start + 4].copy_from_slice(pixel);
            }
        }
    }
    Ok(pixels)
}

fn at(x: i32, y: i32, width: u16, height: u16) -> Area {
    Area {
        x: i16::try_from(x).unwrap_or(i16::MAX),
        y: i16::try_from(y).unwrap_or(i16::MAX),
        width,
        height,
    }
}

fn narrow(length: i32) -> u16 {
    u16::try_from(length).unwrap_or(u16::MAX)
}
