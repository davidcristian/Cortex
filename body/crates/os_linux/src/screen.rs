//! The Linux [`ScreenCapture`] backend's logic, over an X server's root window.

use body_core::{
    CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, RawFrame, ScreenCapture,
};

use crate::compose::compose;
use crate::exclude::{black_out, own_windows};
use crate::focus::topmost;

/// The channel masks of the one pixel layout the backend reads: eight bits each of red, green, blue.
const MASKS: (u32, u32, u32) = (0x00ff_0000, 0x0000_ff00, 0x0000_00ff);

/// A rectangle of the root window, in pixels from its top left corner.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Area {
    /// The left edge.
    pub x: i16,
    /// The top edge.
    pub y: i16,
    /// The width in pixels.
    pub width: u16,
    /// The height in pixels.
    pub height: u16,
}

/// One monitor as `RandR` lists it on the root window.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Monitor {
    /// Whether the server marks this monitor as the primary one.
    pub primary: bool,
    /// Where the monitor shows the root window.
    pub area: Area,
}

/// The root window's own rectangle and the monitors on it, none when the server has no `RandR`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Layout {
    /// The whole root window, at the origin.
    pub root: Area,
    /// The monitors in the server's order.
    pub monitors: Vec<Monitor>,
}

/// One rectangle of a window as the X server returned it, with the format that describes it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RootImage {
    /// The width in pixels.
    pub width: u32,
    /// The height in pixels.
    pub height: u32,
    /// The window's depth, in significant bits per pixel.
    pub depth: u8,
    /// How many bits each pixel takes in `data`, from the server's pixmap format for `depth`.
    pub bits_per_pixel: u8,
    /// Whether each pixel is stored least significant byte first.
    pub lsb_first: bool,
    /// The window visual's red, green and blue masks, all zero when the visual was not found.
    pub masks: (u32, u32, u32),
    /// The `ZPixmap` bytes, top-down rows.
    pub data: Vec<u8>,
}

/// One window under the root, as the server lists it, with what a capture needs to know of it.
// Each flag is a separate fact the server reports about the window, not a state to fold together.
#[allow(clippy::struct_excessive_bools)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TreeWindow {
    /// Its parent's index in the same list, listed before it, or `None` for a child of the root.
    pub parent: Option<usize>,
    /// Its rectangle inside the border, from the inside corner of its parent.
    pub area: Area,
    /// Its border width in pixels.
    pub border: u16,
    /// Whether it and every window above it are mapped.
    pub viewable: bool,
    /// The process its `_NET_WM_PID` property names, if it has one.
    pub pid: Option<u32>,
    /// Whether it is an `InputOnly` window, which has no pixels to read.
    pub input_only: bool,
    /// Whether it has a `WM_NAME` that is not empty, the title a window manager shows.
    pub titled: bool,
    /// Whether it bypasses the window manager, as menus, tooltips and notifications do.
    pub override_redirect: bool,
}

/// One top-level window's own pixels inside the captured rectangle.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Layer {
    /// Where the pixels lie, from the root's corner.
    pub place: Area,
    /// The pixels, read from the window itself in its own format.
    pub image: RootImage,
}

/// The pixels of one rectangle, read from the root or, under a compositing manager, in layers.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Pixels {
    /// The root's own pixels, when no compositing manager owns the screen's `_NET_WM_CM_S` selection.
    Root(RootImage),
    /// When one does, the root background if one is read, then each top-level window, bottom to top.
    Layers(Vec<Layer>),
}

/// The pixels of one rectangle and every window under the root, read in one server grab.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Snapshot {
    /// Every window under the root, each listed after its parent.
    pub windows: Vec<TreeWindow>,
    /// The rectangle's pixels.
    pub pixels: Pixels,
}

/// Why reading the root window failed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum GrabError {
    /// No X server could be reached, such as on a Wayland session with no `DISPLAY`.
    NoDisplay(String),
    /// The server was reached but the read failed or its reply could not be decoded.
    Failed(String),
}

/// Reads the root window of one X screen.
pub trait RootGrab: Send + Sync {
    /// Reports the root window's size and the monitors the server lists on it.
    ///
    /// # Errors
    ///
    /// [`GrabError`] when there is no server or the request fails.
    fn layout(&self) -> Result<Layout, GrabError>;

    /// Reads every window and the pixels of `area`, from the root or in layers, in one grab.
    ///
    /// # Errors
    ///
    /// [`GrabError`] when there is no server or a read fails.
    fn grab(&self, area: Area) -> Result<Snapshot, GrabError>;
}

/// The Linux screen-capture backend over any [`RootGrab`], which paints the windows of one
/// process black and builds a composited screen from its windows, so the overlay never shows.
pub struct LinuxScreenCapture<G> {
    root: G,
    process: u32,
}

impl<G: RootGrab> LinuxScreenCapture<G> {
    /// Creates the backend over `root`, keeping out every window whose `_NET_WM_PID` is `process`.
    #[must_use]
    pub const fn new(root: G, process: u32) -> Self {
        Self { root, process }
    }
}

impl<G: RootGrab> ScreenCapture for LinuxScreenCapture<G> {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        let area = primary(&self.root.layout().map_err(classify)?);
        let snapshot = self.root.grab(area).map_err(classify)?;
        answer(request.target(), area, snapshot, self.process)
    }
}

/// Builds the answer from one read of `area`: the pixels with the windows of `process` painted
/// black, and for a focus target the window it resolves to.
fn answer(
    target: CaptureTarget,
    area: Area,
    snapshot: Snapshot,
    process: u32,
) -> Result<CapturedFrame, CaptureError> {
    let Snapshot { windows, pixels } = snapshot;
    let own = own_windows(&windows, process)?;
    let window = match target {
        CaptureTarget::Display => None,
        CaptureTarget::Focus => Some(topmost(&windows, process, area)?),
    };
    let (width, height, mut pixels) = match pixels {
        Pixels::Root(image) => to_bgra(image)?,
        Pixels::Layers(layers) => {
            let pixels = compose(area, layers)?;
            (u32::from(area.width), u32::from(area.height), pixels)
        }
    };
    black_out(&mut pixels, area, &own);
    let frame = RawFrame::new(width, height, pixels)?;
    Ok(match window {
        None => CapturedFrame::display(frame),
        Some(rect) => CapturedFrame::window(frame, rect),
    })
}

/// Picks the display target: the primary monitor, else the first listed, else the whole root.
fn primary(layout: &Layout) -> Area {
    let monitors = &layout.monitors;
    monitors
        .iter()
        .find(|monitor| monitor.primary)
        .or_else(|| monitors.first())
        .map_or(layout.root, |monitor| monitor.area)
}

/// Reorders one image's pixels to the core's BGRA, refusing any layout other than 8-bit channels
/// in a 32-bit pixel.
pub fn to_bgra(image: RootImage) -> Result<(u32, u32, Vec<u8>), CaptureError> {
    let supported = matches!(image.depth, 24 | 32) && image.bits_per_pixel == 32;
    if !supported || image.masks != MASKS {
        return Err(CaptureError::Backend(format!(
            "a window read is depth {} at {} bits per pixel with masks {:x?}, not 8-bit RGB",
            image.depth, image.bits_per_pixel, image.masks
        )));
    }
    let mut pixels = image.data;
    if !image.lsb_first {
        for pixel in pixels.chunks_exact_mut(4) {
            pixel.reverse();
        }
    }
    Ok((image.width, image.height, pixels))
}

/// Maps a failed read to the port's error: no server is `NoDisplay`, the rest `Backend`.
fn classify(error: GrabError) -> CaptureError {
    match error {
        GrabError::NoDisplay(reason) => CaptureError::NoDisplay(reason),
        GrabError::Failed(reason) => CaptureError::Backend(reason),
    }
}
