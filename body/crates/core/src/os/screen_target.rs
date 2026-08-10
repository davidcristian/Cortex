//! What one capture is pointed at, and where the backend found it (ADR-0029).
//!
//! Split from the [`screen`](super::screen) port by responsibility, the way
//! [`screen_policy`](super::screen_policy) was. That module answers "what does a backend
//! implement"; this one answers "which pixels of the display did the caller ask for"; the size
//! policy answers "how many of them may cross the seam".
//!
//! Resolving a target to a rectangle is the OS backend's job, because only the OS knows where
//! windows are. Everything after that is pure and lives here: clamping the rectangle into the
//! frame, refusing one that lies off the display entirely, and deciding whether what came back
//! is still the whole screen. That is the same division that put the downscale ladder in core
//! rather than in `os_windows`, and it has the same payoff, since the arithmetic a crop gets
//! wrong is arithmetic the coverage gate can see.

use crate::os::screen::{CaptureError, RawFrame};

/// What the body points the camera at, mirroring the wire's `CaptureTarget`.
///
/// A closed vocabulary the body resolves, never a rectangle the caller names. The ADR's own
/// measurement is the argument: given the source size and an explicit "unreadable" escape, the
/// shipped cortex declined on 3 of 47 ground-truth strings and confidently invented the other
/// 38. A model that will not admit it cannot read a screen will not decline to name a rectangle
/// either; it will name a wrong one, and a wrong rectangle costs a second OS receipt and a
/// second tainted read of the wrong part of the screen.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CaptureTarget {
    /// The primary display, whole. The proto3 zero, and the behaviour this seam shipped with.
    Display,
    /// The topmost visible top-level window that is not the body's own and is not excluded
    /// from capture.
    ///
    /// Deliberately **not** the foreground window. The user summons the overlay with a global
    /// hotkey and types the question into it, so at the moment a capture runs the overlay *is*
    /// the foreground window, and it sets `WDA_EXCLUDEFROMCAPTURE` on itself, so cropping to it
    /// would yield an absent or black rectangle on the common path rather than in an edge case.
    Focus,
}

/// Where the resolved target sits, in the display's own physical pixels, exactly as the OS
/// reported it.
///
/// Signed and unvalidated on purpose. A window may hang off the left or top of the display
/// (negative edges), extend past its right or bottom, or sit entirely on another monitor, and
/// Win32 reports all three without complaint. Deciding what those mean is
/// [`CapturedFrame::region`]'s job, which is pure and gated; a backend's job is to report what
/// the OS said.
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
///
/// The backend keeps blitting the **whole display** whatever the target is, and reports the
/// rectangle beside the frame instead of cropping to it. Two reasons, both the ADR's existing
/// ones. The crop is then pure arithmetic under the 100% line and branch gate, while only the
/// Z-order walk that found the window is `cfg(windows)` and unmeasurable. And the value keeps
/// the display's own size, which the brain shows the model and which must go on saying how big
/// the *screen* is even when the picture is one window of it.
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
    ///
    /// A window is clamped into the frame edge by edge, so a window dragged half off the screen
    /// yields the half that is on it.
    ///
    /// # Errors
    ///
    /// [`CaptureError::NoTarget`] if the clamped rectangle has no pixels: the window sits
    /// entirely off the captured display (another monitor, or scrolled off an edge), or the OS
    /// reported an empty rectangle. Refusing is deliberate, and the alternative is worse than an
    /// error: falling back to the whole display would send more of the screen than was asked
    /// for, with neither the model nor the receipt knowing it happened.
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

/// One edge clamped into `0..=bound`, in the frame's own pixels. A negative edge is a window
/// hanging off the top or the left of the display and clamps to zero; an edge past the display
/// clamps to its size. Nothing else can happen: the only way [`u32::try_from`] fails on an
/// `i32` is a negative one.
fn clamp_edge(value: i32, bound: u32) -> u32 {
    u32::try_from(value).unwrap_or(0).min(bound)
}

/// The part of a frame a capture encodes: an origin and a size, both in the frame's own pixels
/// and both already known to be inside it.
///
/// Crate-private and constructed only by [`CapturedFrame::region`], so the downscaler can index
/// with it without bounds-checking the geometry a second time.
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

    /// Whether this region is the whole frame, which is what decides which of the two fixed
    /// receipt strings the body shows: a picture of the screen, or a picture of one window. It
    /// reads the region rather than the request so the notice describes what was actually sent,
    /// which is why a window covering the entire display honestly reports a screen capture.
    pub(crate) const fn covers(&self, width: u32, height: u32) -> bool {
        self.x == 0 && self.y == 0 && self.width == width && self.height == height
    }
}
