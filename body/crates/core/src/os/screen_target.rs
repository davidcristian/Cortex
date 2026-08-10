//! What one capture is pointed at, and where the backend found it (ADR-0029).

use crate::os::screen::{CaptureError, RawFrame};

/// What the body points the camera at, mirroring the wire's `CaptureTarget`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CaptureTarget {
    /// The primary display, whole. The proto3 zero, and the behaviour this seam shipped with.
    Display,
    /// The topmost visible top-level window that is not the body's own and is not excluded
    /// from capture.
    Focus,
}

/// Where the resolved target sits, in the display's own physical pixels, exactly as the OS
/// reported it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TargetRect {
    left: i32,
    top: i32,
    right: i32,
    bottom: i32,
}

impl TargetRect {
    /// A rectangle as the OS reports one: two corners, right and bottom exclusive.
    #[must_use]
    pub const fn new(left: i32, top: i32, right: i32, bottom: i32) -> Self {
        Self {
            left,
            top,
            right,
            bottom,
        }
    }

    /// The left edge, which may be negative.
    #[must_use]
    pub const fn left(&self) -> i32 {
        self.left
    }

    /// The top edge, which may be negative.
    #[must_use]
    pub const fn top(&self) -> i32 {
        self.top
    }

    /// The right edge, exclusive.
    #[must_use]
    pub const fn right(&self) -> i32 {
        self.right
    }

    /// The bottom edge, exclusive.
    #[must_use]
    pub const fn bottom(&self) -> i32 {
        self.bottom
    }
}

/// One backend answer: the display's pixels, and where in them the resolved target sits.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CapturedFrame {
    frame: RawFrame,
    window: Option<TargetRect>,
}

impl CapturedFrame {
    /// The whole display, which is what a [`CaptureTarget::Display`] request answers.
    #[must_use]
    pub const fn display(frame: RawFrame) -> Self {
        Self {
            frame,
            window: None,
        }
    }

    /// The display, with the window a [`CaptureTarget::Focus`] request resolved to.
    ///
    /// `window` is where the OS says that window is, unclamped. A rectangle that hangs off the
    /// display is cropped to the part that is on it; one that misses it entirely is refused.
    #[must_use]
    pub const fn window(frame: RawFrame, window: TargetRect) -> Self {
        Self {
            frame,
            window: Some(window),
        }
    }

    /// The display's own pixels, whole, whatever the target was.
    #[must_use]
    pub const fn frame(&self) -> &RawFrame {
        &self.frame
    }

    /// The part of the frame this capture encodes, in the frame's own pixels.
    pub(crate) fn region(&self) -> Result<Region, CaptureError> {
        let (width, height) = (self.frame.width(), self.frame.height());
        let Some(rect) = self.window else {
            return Ok(Region {
                x: 0,
                y: 0,
                width,
                height,
            });
        };
        let (left, right) = (
            clamp_edge(rect.left(), width),
            clamp_edge(rect.right(), width),
        );
        let (top, bottom) = (
            clamp_edge(rect.top(), height),
            clamp_edge(rect.bottom(), height),
        );
        if right <= left || bottom <= top {
            return Err(CaptureError::NoTarget(format!(
                "the target window at {rect:?} has nothing inside the {width}x{height} display"
            )));
        }
        Ok(Region {
            x: left,
            y: top,
            width: right - left,
            height: bottom - top,
        })
    }
}

/// One edge clamped into `0..=bound`, in the frame's own pixels.
fn clamp_edge(value: i32, bound: u32) -> u32 {
    u32::try_from(value).unwrap_or(0).min(bound)
}

/// The part of a frame a capture encodes: an origin and a size, both in the frame's own pixels
/// and both already known to be inside it.
#[derive(Clone, Copy)]
pub(crate) struct Region {
    x: u32,
    y: u32,
    width: u32,
    height: u32,
}

impl Region {
    /// The region's left edge in the frame.
    pub(crate) const fn x(&self) -> u32 {
        self.x
    }

    /// The region's top edge in the frame.
    pub(crate) const fn y(&self) -> u32 {
        self.y
    }

    /// The region's width in pixels.
    pub(crate) const fn width(&self) -> u32 {
        self.width
    }

    /// The region's height in pixels.
    pub(crate) const fn height(&self) -> u32 {
        self.height
    }

    /// Whether this region is the whole frame, which is what decides which of the two fixed receipt
    /// strings the body shows: a picture of the screen, or a picture of one window.
    pub(crate) const fn covers(&self, width: u32, height: u32) -> bool {
        self.x == 0 && self.y == 0 && self.width == width && self.height == height
    }
}
