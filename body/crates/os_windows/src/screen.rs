//! The Windows [`ScreenCapture`] backend: a GDI `BitBlt` of the primary display.
#![allow(unsafe_code)] // ADR-0029: GDI (GetDC/BitBlt/GetDIBits) is a raw Win32 FFI surface.

use body_core::{CaptureError, CaptureRequest, RawFrame, ScreenCapture};
use windows::Win32::Foundation::HWND;
use windows::Win32::Graphics::Gdi::{
    BI_RGB, BITMAPINFO, BITMAPINFOHEADER, BitBlt, CAPTUREBLT, CreateCompatibleBitmap,
    CreateCompatibleDC, DIB_RGB_COLORS, DeleteDC, DeleteObject, GetDC, GetDIBits, HBITMAP, HDC,
    HGDIOBJ, ReleaseDC, SRCCOPY, SelectObject,
};
use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN};

/// Bytes per pixel in the DIB this backend asks for: 32-bit BGRA, matching [`RawFrame`].
const BYTES_PER_PIXEL: usize = 4;

/// The window whose device context is the whole screen: the null handle, by Win32 convention.
const SCREEN: HWND = HWND(std::ptr::null_mut());

/// The Windows GDI screen-capture backend.
pub struct WindowsScreenCapture;

impl WindowsScreenCapture {
    /// Creates the backend.
    #[must_use]
    pub const fn new() -> Self {
        Self
    }
}

impl Default for WindowsScreenCapture {
    fn default() -> Self {
        Self::new()
    }
}

impl ScreenCapture for WindowsScreenCapture {
    /// Blits the primary display and returns its raw BGRA pixels.
    fn capture(&self, _request: &CaptureRequest) -> Result<RawFrame, CaptureError> {
        let (width, height) = display_size()?;
        // SAFETY: a null window handle names the whole screen, which is what is being captured.
        let screen = unsafe { GetDC(SCREEN) };
        if screen.is_invalid() {
            return Err(CaptureError::NoDisplay(String::from(
                "GetDC returned no device context for the screen",
            )));
        }
        let taken = blit(screen, width, height);
        // SAFETY: `screen` came from `GetDC(SCREEN)`, so it is released against the same window.
        unsafe {
            ReleaseDC(SCREEN, screen);
        }
        RawFrame::new(width, height, taken?)
    }
}

/// The primary display's size in **physical pixels**.
fn display_size() -> Result<(u32, u32), CaptureError> {
    // SAFETY: a pure metric read with no handles and no out-parameters.
    let (width, height) = unsafe { (GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN)) };
    let sized = u32::try_from(width).ok().zip(u32::try_from(height).ok());
    match sized {
        Some((width, height)) if width > 0 && height > 0 => Ok((width, height)),
        _ => Err(CaptureError::NoDisplay(format!(
            "the primary display reports a {width}x{height} size"
        ))),
    }
}

/// Copies `width x height` pixels out of `screen` and reads them back as BGRA bytes.
fn blit(screen: HDC, width: u32, height: u32) -> Result<Vec<u8>, CaptureError> {
    // SAFETY: `screen` is a live DC from `GetDC`; the memory DC is deleted below.
    let memory = unsafe { CreateCompatibleDC(screen) };
    if memory.is_invalid() {
        return Err(CaptureError::Backend(String::from(
            "CreateCompatibleDC could not make a memory device context",
        )));
    }
    let taken = into_bitmap(screen, memory, width, height);
    // SAFETY: `memory` came from `CreateCompatibleDC` and nothing references it after this.
    unsafe {
        let _ = DeleteDC(memory);
    }
    taken
}

/// Creates the destination bitmap, blits into it, and reads it back.
fn into_bitmap(screen: HDC, memory: HDC, width: u32, height: u32) -> Result<Vec<u8>, CaptureError> {
    let (w, h) = (as_i32(width)?, as_i32(height)?);
    // SAFETY: `screen` is a live DC, so it can describe a compatible bitmap of this size.
    let bitmap = unsafe { CreateCompatibleBitmap(screen, w, h) };
    if bitmap.is_invalid() {
        return Err(CaptureError::Backend(format!(
            "CreateCompatibleBitmap could not make a {width}x{height} bitmap"
        )));
    }
    let taken = copy_pixels(screen, memory, bitmap, width, height);
    // SAFETY: `bitmap` came from `CreateCompatibleBitmap`, is deselected by the memory DC's own
    // deletion, and nothing references it after this.
    unsafe {
        let _ = DeleteObject(HGDIOBJ(bitmap.0));
    }
    taken
}

/// Selects `bitmap` into `memory`, blits the screen into it, and reads the pixels back.
fn copy_pixels(
    screen: HDC,
    memory: HDC,
    bitmap: HBITMAP,
    width: u32,
    height: u32,
) -> Result<Vec<u8>, CaptureError> {
    let (w, h) = (as_i32(width)?, as_i32(height)?);
    // SAFETY: both handles are live and the bitmap is compatible with `screen`.
    let previous = unsafe { SelectObject(memory, HGDIOBJ(bitmap.0)) };
    // SAFETY: a straight copy of the whole screen into the selected bitmap. CAPTUREBLT is what
    // includes layered windows, which is most of what a modern desktop is made of.
    let blitted = unsafe { BitBlt(memory, 0, 0, w, h, screen, 0, 0, SRCCOPY | CAPTUREBLT) };
    let taken = match blitted {
        Ok(()) => read_back(memory, bitmap, width, height),
        Err(error) => Err(CaptureError::Backend(format!("BitBlt failed: {error}"))),
    };
    // SAFETY: restoring the DC's original object before the caller deletes ours.
    unsafe {
        SelectObject(memory, previous);
    }
    taken
}

/// Reads `bitmap` back as a top-down 32-bit BGRA buffer.
///
/// The header's height is **negative**, which is what asks GDI for top-down rows; a positive
/// height would hand back a vertically flipped image, and the core has no way to know.
fn read_back(
    memory: HDC,
    bitmap: HBITMAP,
    width: u32,
    height: u32,
) -> Result<Vec<u8>, CaptureError> {
    let pixels = (width as usize)
        .checked_mul(height as usize)
        .and_then(|count| count.checked_mul(BYTES_PER_PIXEL))
        .ok_or_else(|| {
            CaptureError::Backend(format!("a {width}x{height} frame does not fit in memory"))
        })?;
    let mut buffer = vec![0_u8; pixels];
    let mut info = BITMAPINFO {
        bmiHeader: BITMAPINFOHEADER {
            biSize: u32::try_from(size_of::<BITMAPINFOHEADER>()).unwrap_or(40),
            biWidth: as_i32(width)?,
            biHeight: -as_i32(height)?,
            biPlanes: 1,
            biBitCount: 32,
            biCompression: BI_RGB.0,
            ..BITMAPINFOHEADER::default()
        },
        ..BITMAPINFO::default()
    };
    // SAFETY: `buffer` is exactly `width * height * 4` bytes, which is what the header above
    // describes, and `info` outlives the call.
    let rows = unsafe {
        GetDIBits(
            memory,
            bitmap,
            0,
            height,
            Some(buffer.as_mut_ptr().cast()),
            &raw mut info,
            DIB_RGB_COLORS,
        )
    };
    if u32::try_from(rows).unwrap_or(0) != height {
        return Err(CaptureError::Backend(format!(
            "GetDIBits returned {rows} of {height} rows"
        )));
    }
    Ok(buffer)
}

/// A pixel count as the `i32` the GDI entry points take.
fn as_i32(value: u32) -> Result<i32, CaptureError> {
    i32::try_from(value).map_err(|_| {
        CaptureError::Backend(format!(
            "a {value} pixel edge is larger than GDI can address"
        ))
    })
}

/// Hides a window from every screen capture on the machine, at the DWM level.
#[must_use]
pub fn exclude_from_capture(hwnd: isize) -> bool {
    use windows::Win32::UI::WindowsAndMessaging::{
        SetWindowDisplayAffinity, WDA_EXCLUDEFROMCAPTURE,
    };

    // SAFETY: a display-affinity change on a window handle the caller owns; it touches no
    // memory of ours and returns a plain success flag.
    unsafe { SetWindowDisplayAffinity(HWND(hwnd as *mut _), WDA_EXCLUDEFROMCAPTURE).is_ok() }
}
