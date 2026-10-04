//! Picks the window a focus capture points at from one read of the window tree.

use body_core::{CaptureError, TargetRect};

use crate::screen::{Area, TreeWindow};

/// Returns the topmost viewable top-level window that holds a title and no window of `process`,
/// border included, in the pixels of `area`. Override-redirect, `InputOnly`, dock and desktop
/// windows are skipped.
pub fn topmost(
    windows: &[TreeWindow],
    process: u32,
    area: Area,
) -> Result<TargetRect, CaptureError> {
    let mut heads: Vec<usize> = Vec::with_capacity(windows.len());
    for (index, window) in windows.iter().enumerate() {
        let head = window.parent.and_then(|parent| heads.get(parent).copied());
        heads.push(head.unwrap_or(index));
    }
    windows
        .iter()
        .enumerate()
        .rev()
        .filter(|(_, window)| window.viewable && !window.input_only && !window.override_redirect)
        // A child heads no window, so `under` finds no title for it and only a top-level is picked.
        .find(|(index, _)| {
            under(windows, &heads, *index).any(|window| window.titled)
                && !under(windows, &heads, *index).any(|window| window.pid == Some(process))
                && !under(windows, &heads, *index).any(|window| window.dock_or_desktop)
        })
        .map(|(_, window)| rect(window, area))
        .ok_or_else(|| {
            CaptureError::NoTarget(String::from(
                "no top-level window on this X screen is viewable, titled, not a dock or desktop \
                 and not the body's own",
            ))
        })
}

/// Lists the top-level window at `head` and every window under it.
fn under<'a>(
    windows: &'a [TreeWindow],
    heads: &'a [usize],
    head: usize,
) -> impl Iterator<Item = &'a TreeWindow> {
    windows
        .iter()
        .zip(heads)
        .filter(move |(_, top)| **top == head)
        .map(|(window, _)| window)
}

/// The rectangle a top-level window covers, border included, from the corner of `area`.
fn rect(window: &TreeWindow, area: Area) -> TargetRect {
    let left = i32::from(window.area.x) - i32::from(area.x);
    let top = i32::from(window.area.y) - i32::from(area.y);
    let border = 2 * i32::from(window.border);
    TargetRect::new(
        left,
        top,
        left + i32::from(window.area.width) + border,
        top + i32::from(window.area.height) + border,
    )
}
