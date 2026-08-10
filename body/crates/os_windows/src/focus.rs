//! Resolving a targeted capture to a window rectangle: a walk down the desktop's Z-order
//! (ADR-0029).
#![allow(unsafe_code)] // ADR-0029: the Z-order walk is a raw Win32 FFI surface.

use body_core::{CaptureError, TargetRect};
use windows::Win32::Foundation::{HWND, RECT};
use windows::Win32::Graphics::Dwm::{
    DWMWA_CLOAKED, DWMWA_EXTENDED_FRAME_BOUNDS, DwmGetWindowAttribute,
};
use windows::Win32::System::Threading::GetCurrentProcessId;
use windows::Win32::UI::WindowsAndMessaging::{
    GW_HWNDNEXT, GWL_EXSTYLE, GetShellWindow, GetTopWindow, GetWindow, GetWindowDisplayAffinity,
    GetWindowLongPtrW, GetWindowRect, GetWindowTextLengthW, GetWindowThreadProcessId, IsIconic,
    IsWindowVisible, WDA_NONE, WS_EX_TOOLWINDOW,
};

/// The desktop, whose child list is the top-level windows: the null handle, by Win32 convention.
const DESKTOP: HWND = HWND(std::ptr::null_mut());

/// How many windows down the Z-order the walk will look before giving up.
const MAX_WALK: usize = 512;

/// The topmost window worth capturing, as the OS reports its bounds.
pub(crate) fn topmost_window() -> Result<TargetRect, CaptureError> {
    // SAFETY: three pure reads of process-wide state, no handles owned and no out-parameters.
    let (ours, shell) = unsafe { (GetCurrentProcessId(), GetShellWindow()) };
    // SAFETY: a null handle names the desktop, whose children are the top-level windows. An
    // error means it has none, which the walk below reports as an empty desktop.
    let mut next = unsafe { GetTopWindow(DESKTOP) }.ok();
    for _ in 0..MAX_WALK {
        let Some(window) = next else { break };
        if is_capturable(window, ours, shell) {
            return bounds_of(window);
        }
        // SAFETY: `window` came from the same walk and is still a handle; an error ends the list.
        next = unsafe { GetWindow(window, GW_HWNDNEXT) }.ok();
    }
    Err(CaptureError::NoTarget(String::from(
        "no window on this desktop is visible, titled, and capturable",
    )))
}

/// Whether `window` is the one the user is looking at, as far as anything but the user can tell.
fn is_capturable(window: HWND, ours: u32, shell: HWND) -> bool {
    window != shell
        && is_visible(window)
        && !is_minimized(window)
        && !is_cloaked(window)
        && !is_tool_window(window)
        && has_title(window)
        && !is_ours(window, ours)
        && !is_hidden_from_capture(window)
}

/// Whether the OS calls the window visible. The first filter and the weakest one: a window can
/// be visible, be nothing anyone can see, and still say yes here.
fn is_visible(window: HWND) -> bool {
    // SAFETY: a state read on a handle from the walk; it touches no memory of ours.
    unsafe { IsWindowVisible(window) }.as_bool()
}

/// Whether the window is minimized, which [`is_visible`] still calls visible. Its bounds while
/// iconic are off-screen coordinates, so capturing it would answer a rectangle of nothing.
fn is_minimized(window: HWND) -> bool {
    // SAFETY: a state read on a handle from the walk.
    unsafe { IsIconic(window) }.as_bool()
}

/// Whether DWM is hiding the window from the compositor.
fn is_cloaked(window: HWND) -> bool {
    let mut cloaked = 0_u32;
    // SAFETY: the out-parameter is a live `u32` of exactly the size passed, and DWM writes at
    // most that many bytes into it.
    let asked = unsafe {
        DwmGetWindowAttribute(
            window,
            DWMWA_CLOAKED,
            (&raw mut cloaked).cast(),
            u32::try_from(size_of::<u32>()).unwrap_or(4),
        )
    };
    asked.is_ok() && cloaked != 0
}

/// Whether the window is chrome rather than content.
fn is_tool_window(window: HWND) -> bool {
    // SAFETY: a style read on a handle from the walk; it takes and returns a plain integer.
    let styles = unsafe { GetWindowLongPtrW(window, GWL_EXSTYLE) };
    u32::try_from(styles).unwrap_or_default() & WS_EX_TOOLWINDOW.0 != 0
}

/// Whether the window has a title at all, which is how the wallpaper host (`WorkerW`) and the
/// untitled helper windows every desktop carries are told from real ones.
fn has_title(window: HWND) -> bool {
    // SAFETY: a length read on a handle from the walk; no buffer is passed, so none is written.
    let length = unsafe { GetWindowTextLengthW(window) };
    length > 0
}

/// Whether the window belongs to this process, which is the overlay and anything else the body
/// puts on screen. Checked by process rather than by handle so a second body window, a Tauri
/// dialog, or a web view's own child window is caught by the same rule.
fn is_ours(window: HWND, ours: u32) -> bool {
    let mut owner = 0_u32;
    // SAFETY: the out-parameter is a live `u32`, which is exactly what the call writes.
    unsafe { GetWindowThreadProcessId(window, Some(&raw mut owner)) };
    owner == ours
}

/// Whether the window has asked to be left out of screen captures.
fn is_hidden_from_capture(window: HWND) -> bool {
    let mut affinity = 0_u32;
    // SAFETY: the out-parameter is a live `u32`, which is what the call writes.
    let asked = unsafe { GetWindowDisplayAffinity(window, &raw mut affinity) };
    asked.is_err() || affinity != WDA_NONE.0
}

/// Where the OS says the window is, in the physical pixels the capture is in.
fn bounds_of(window: HWND) -> Result<TargetRect, CaptureError> {
    let mut rect = RECT::default();
    // SAFETY: the out-parameter is a live `RECT` of exactly the size passed.
    let extended = unsafe {
        DwmGetWindowAttribute(
            window,
            DWMWA_EXTENDED_FRAME_BOUNDS,
            (&raw mut rect).cast(),
            u32::try_from(size_of::<RECT>()).unwrap_or(16),
        )
    };
    if extended.is_err() {
        // SAFETY: the same live `RECT`, written by the ordinary bounds call.
        unsafe { GetWindowRect(window, &raw mut rect) }.map_err(|error| {
            CaptureError::Backend(format!("the window's bounds could not be read: {error}"))
        })?;
    }
    Ok(TargetRect::new(
        rect.left,
        rect.top,
        rect.right,
        rect.bottom,
    ))
}
