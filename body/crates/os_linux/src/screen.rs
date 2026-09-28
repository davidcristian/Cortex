//! The Linux [`ScreenCapture`] backend's logic, over an X server's root window.

use body_core::{
    CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, RawFrame, ScreenCapture,
};

/// The channel masks of the one pixel layout the backend reads: eight bits each of red, green, blue.
const MASKS: (u32, u32, u32) = (0x00ff_0000, 0x0000_ff00, 0x0000_00ff);

/// The root window's pixels as the X server returned them, with the format that describes them.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RootImage {
    /// The root window's width in pixels.
    pub width: u32,
    /// The root window's height in pixels.
    pub height: u32,
    /// The root window's depth, in significant bits per pixel.
    pub depth: u8,
    /// How many bits each pixel takes in `data`, from the server's pixmap format for `depth`.
    pub bits_per_pixel: u8,
    /// Whether each pixel is stored least significant byte first.
    pub lsb_first: bool,
    /// The root visual's red, green and blue masks, all zero when the visual was not found.
    pub masks: (u32, u32, u32),
    /// The `ZPixmap` bytes, top-down rows.
    pub data: Vec<u8>,
}

/// Why reading the root window failed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum GrabError {
    /// No X server could be reached, such as on a Wayland session with no `DISPLAY`.
    NoDisplay(String),
    /// The server was reached but the read failed or its reply could not be decoded.
    Failed(String),
}

/// Reads the whole root window of one X screen.
pub trait RootGrab: Send + Sync {
    /// Reads every pixel of the root window, with the format the server describes them in.
    ///
    /// # Errors
    ///
    /// [`GrabError`] when there is no server or the read fails.
    fn grab(&self) -> Result<RootImage, GrabError>;
}

/// The Linux screen-capture backend over any [`RootGrab`].
pub struct LinuxScreenCapture<G> {
    root: G,
}

impl<G: RootGrab> LinuxScreenCapture<G> {
    /// Creates the backend over `root`.
    #[must_use]
    pub const fn new(root: G) -> Self {
        Self { root }
    }
}

impl<G: RootGrab> ScreenCapture for LinuxScreenCapture<G> {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        if request.target() == CaptureTarget::Focus {
            return Err(CaptureError::Backend(String::from(
                "capturing one window is not implemented on X11",
            )));
        }
        let image = self.root.grab().map_err(classify)?;
        Ok(CapturedFrame::display(to_bgra(image)?))
    }
}

/// Reorders one image's pixels to the core's BGRA, refusing any layout other than 8-bit channels
/// in a 32-bit pixel.
fn to_bgra(image: RootImage) -> Result<RawFrame, CaptureError> {
    let supported = matches!(image.depth, 24 | 32) && image.bits_per_pixel == 32;
    if !supported || image.masks != MASKS {
        return Err(CaptureError::Backend(format!(
            "the root window is depth {} at {} bits per pixel with masks {:x?}, not 8-bit RGB",
            image.depth, image.bits_per_pixel, image.masks
        )));
    }
    let mut pixels = image.data;
    if !image.lsb_first {
        for pixel in pixels.chunks_exact_mut(4) {
            pixel.reverse();
        }
    }
    RawFrame::new(image.width, image.height, pixels)
}

/// Maps a failed read to the port's error: no server is `NoDisplay`, the rest `Backend`.
fn classify(error: GrabError) -> CaptureError {
    match error {
        GrabError::NoDisplay(reason) => CaptureError::NoDisplay(reason),
        GrabError::Failed(reason) => CaptureError::Backend(reason),
    }
}
