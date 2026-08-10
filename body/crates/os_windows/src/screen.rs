//! The Windows [`ScreenCapture`] backend: a GDI `BitBlt` of the primary display.
//!
//! A thin adapter (AGENTS.md gate 3): it asks the OS for the display's size, blits it into a
//! memory bitmap, reads the pixels back as a top-down 32-bit DIB, and hands the raw BGRA bytes
//! to the pure core. **Every size decision (the crop, the downscale, the PNG encode, the byte
//! ceiling and its shrink ladder) lives in `body_core` and none of it is here**, because this
//! crate is `cfg(windows)` and the coverage gate never measures it, so a policy left here would
//! be a seam guarantee resting on code no gate can see. What this file does own is the part no
//! gate could reach anyway: the blit, and the [`focus`](crate::focus) walk behind a targeted
//! capture, which reports a rectangle for the core to crop to.
//!
//! GDI rather than DXGI Desktop Duplication or `Windows.Graphics.Capture` (ADR-0029): it needs
//! no COM apartment, so it does not deepen the recorded unbalanced-`CoUninitialize` entry with
//! a third initialized backend on the blocking pool; it holds no persistent device, so it
//! satisfies the `FnOnce + Send + 'static` closure the body server hands to an arbitrary
//! blocking-pool thread; and it has the smallest `unsafe` surface. Every handle it creates is
//! released inside the one call that created it.
//!
//! **Known limitation, silent by nature:** GDI renders hardware-overlay and DRM-protected
//! surfaces black, and there is no error to distinguish that from a genuinely dark screen.
//!
//! Host-authored, **validated on Windows by the user**. Like the other real backends it is
//! never built or measured in CI. It *is* compiled and clippy-linted on the Windows target from
//! Linux, which type-checks it against the port and nothing more: no blit here has ever run.
//!
//! [`ScreenCapture`]: body_core::ScreenCapture
#![allow(unsafe_code)] // ADR-0029: GDI (GetDC/BitBlt/GetDIBits) is a raw Win32 FFI surface.

use body_core::{
    CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, RawFrame, ScreenCapture, TargetRect,
};
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
///
/// Stateless: every call resolves the current display size and creates and releases its own
/// handles, so a resolution change or a monitor swap between calls is picked up and nothing
/// `!Send` outlives a call (the one hard rule, and what lets the body server lend it to an
/// arbitrary blocking thread).
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
    /// Blits the primary display and returns its raw BGRA pixels, with the request's target
    /// resolved to a rectangle inside them.
    ///
    /// The blit is the whole display whatever the target is, and a targeted request adds only
    /// the Z-order walk in [`crate::focus`] that says which part of it the caller meant. The
    /// crop itself is `body_core`'s, for the same reason the downscale is: this file is
    /// `cfg(windows)` and no gate can see it. The request's size hints stay unread here, since
    /// GDI has no cheaper read to ask for; the core re-applies them to what comes back.
    ///
    /// The target is resolved **before** the blit, so the rectangle names a window that was on
    /// screen at most one blit ago. Nothing can make that exact: a desktop is free to reorder
    /// itself between any two Win32 calls, and the other order would be stale by the same
    /// amount in the other direction.
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        let target = match request.target() {
            CaptureTarget::Display => None,
            CaptureTarget::Focus => Some(crate::focus::topmost_window()?),
        };
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
        let frame = RawFrame::new(width, height, taken?)?;
        Ok(framed(frame, target))
    }
}

/// Pairs the display's pixels with the rectangle the target resolved to, if it resolved to one.
fn framed(frame: RawFrame, target: Option<TargetRect>) -> CapturedFrame {
    match target {
        Some(window) => CapturedFrame::window(frame, window),
        None => CapturedFrame::display(frame),
    }
}

/// The primary display's size in **physical pixels**.
///
/// `GetSystemMetrics` reports the primary monitor, which is what this backend captures. The
/// numbers are physical rather than logical: the manifest marks the process per-monitor DPI
/// aware, so no scaling is applied on the way out, and the docs say so rather than pretending
/// these are points.
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
///
/// Split from the trait method so the device context release above is unconditional: this
/// function may fail at four points, and every one of them still has to give the screen DC
/// back. Its own memory DC and bitmap are released here, in reverse creation order.
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
///
/// The overlay excludes **itself** with this at setup, and the shell wires
/// `DeniedScreenCapture` if it fails (ADR-0029). Not cosmetic: the overlay is an always-on-top
/// opaque window, so without exclusion the model receives a picture of that window covering the
/// content, containing the user's own prompt and the prior reply. That is a **self-injection
/// loop**, where one line an attacker gets into a rendered reply is re-ingested as screen
/// content on the next capture, laundered from model output back into untrusted model input.
///
/// `WDA_EXCLUDEFROMCAPTURE` is DWM level, so it holds for GDI, DXGI and WGC alike if the
/// backend is ever swapped, and it has no timing relationship with a capture. Hide, capture,
/// show is rejected: it flickers, it blanks the window the user is typing into, and it races a
/// handler running on a blocking-pool thread with no ordering guarantee against the UI thread.
///
/// # Errors
///
/// Answers `false` if the OS refuses the call, which the caller must treat as "no capture may
/// happen at all" rather than as a warning.
#[must_use]
pub fn exclude_from_capture(hwnd: isize) -> bool {
    use windows::Win32::UI::WindowsAndMessaging::{
        SetWindowDisplayAffinity, WDA_EXCLUDEFROMCAPTURE,
    };

    // SAFETY: a display-affinity change on a window handle the caller owns; it touches no
    // memory of ours and returns a plain success flag.
    unsafe { SetWindowDisplayAffinity(HWND(hwnd as *mut _), WDA_EXCLUDEFROMCAPTURE).is_ok() }
}
