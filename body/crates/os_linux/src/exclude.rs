//! Finds this process's windows in a read of the screen and paints them black.

use body_core::CaptureError;

use crate::screen::{Area, TreeWindow};

/// A rectangle of the root window in pixels, from `left` and `top` up to but not including
/// `right` and `bottom`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Span {
    left: i32,
    top: i32,
    right: i32,
    bottom: i32,
}

impl Span {
    const fn holds(self, x: i32, y: i32) -> bool {
        self.left <= x && x < self.right && self.top <= y && y < self.bottom
    }
}

/// Returns the rectangle, border included, of every viewable window whose `_NET_WM_PID` is
/// `process`, refusing a list where no window names `process` or a parent is not listed earlier.
pub fn own_windows(windows: &[TreeWindow], process: u32) -> Result<Vec<Span>, CaptureError> {
    let mut insides: Vec<(i32, i32)> = Vec::with_capacity(windows.len());
    let mut own = Vec::new();
    let mut named = false;
    for window in windows {
        let (x, y) = match window.parent {
            None => (0, 0),
            Some(parent) => *insides.get(parent).ok_or_else(|| {
                refuse("the window list names a parent after its child, so it cannot be placed")
            })?,
        };
        let border = i32::from(window.border);
        let left = x + i32::from(window.area.x);
        let top = y + i32::from(window.area.y);
        insides.push((left + border, top + border));
        if window.pid == Some(process) {
            named = true;
            if window.viewable {
                own.push(Span {
                    left,
                    top,
                    right: left + i32::from(window.area.width) + 2 * border,
                    bottom: top + i32::from(window.area.height) + 2 * border,
                });
            }
        }
    }
    if named {
        Ok(own)
    } else {
        Err(refuse(
            "no window names this process in _NET_WM_PID, so the overlay cannot be found",
        ))
    }
}

/// Paints black every pixel of `pixels`, a BGRA image of `area`, that lies inside one of `spans`.
pub fn black_out(pixels: &mut [u8], area: Area, spans: &[Span]) {
    let (left, top) = (i32::from(area.x), i32::from(area.y));
    let columns = left..left + i32::from(area.width);
    let points =
        (top..top + i32::from(area.height)).flat_map(|y| columns.clone().map(move |x| (x, y)));
    for (pixel, (x, y)) in pixels.chunks_exact_mut(4).zip(points) {
        if spans.iter().any(|span| span.holds(x, y)) {
            pixel.fill(0);
        }
    }
}

fn refuse(reason: &str) -> CaptureError {
    CaptureError::Backend(String::from(reason))
}
