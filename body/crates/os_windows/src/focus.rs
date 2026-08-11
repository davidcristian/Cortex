//! Resolving a targeted capture to a window rectangle: a walk down the desktop's Z-order
//! (ADR-0029).
//!
//! **Not `GetForegroundWindow`**, and that is the whole design. The user summons the overlay
//! with a global hotkey and types the question into it, so at the moment a capture runs the
//! overlay *is* the foreground window; it also sets `WDA_EXCLUDEFROMCAPTURE` on itself
//! ([`exclude_from_capture`](crate::exclude_from_capture)), so a crop to it would be an absent
//! or black rectangle. Cropping to the foreground window would therefore fail on the common
//! path rather than in an edge case.
//!
//! So this walks the desktop's child list, which is the top-level windows in Z-order from the
//! front, and takes the first one a person would call a window: visible, not minimized, not
//! DWM-cloaked, not a tool window, not the shell's own desktop, titled, ours in neither process
//! nor display affinity. Each of those is one class of thing that is on screen and is not what
//! the user is looking at, and the ones that are not obvious are argued at their own predicate.
//!
//! Nothing here decides how big the picture may be, and nothing here crops. It reports the
//! rectangle the OS gave, unclamped and possibly off the display, and `body_core` decides what
//! that means: a window half off the screen is cropped to the half that is on it, one entirely
//! off it is refused. That keeps the arithmetic under the coverage gate and leaves this file
//! with only the part no gate can reach.
//!
//! Host-authored, **never run**. Like the rest of this crate it is compiled and clippy-linted
//! for the Windows target from Linux, which type-checks it against the Win32 signatures and
//! nothing more: no walk here has ever seen a real desktop. What a real one has to confirm is
//! in `docs/host/index.md#windows-capture`.
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
///
/// A desktop has tens of top-level windows and a busy one has low hundreds, so this is a
/// termination bound rather than a policy: `GetWindow` walking a list that is being reordered
/// underneath it has no promise of ending, and an unbounded loop on a blocking-pool thread is a
/// wedged capture, which is the one failure the seam's deadline cannot un-wedge.
const MAX_WALK: usize = 512;

/// The topmost window worth capturing, as the OS reports its bounds.
///
/// # Errors
///
/// [`CaptureError::NoTarget`] if the walk finds nothing: a bare desktop, or every window on it
/// filtered out. Deliberately not a fallback to the whole display, which would send more of the
/// screen than was asked for with neither the model nor the receipt knowing.
/// [`CaptureError::Backend`] if a window is found and the OS then refuses to say where it is.
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
///
/// This is the filter that stops a targeted capture from resolving to a ghost. A store app the
/// user closed, a window on another virtual desktop, and a shell surface that never renders are
/// all *visible* by `IsWindowVisible` and cloaked by DWM, and a walk without this check would
/// crop to whichever of them happens to sit highest.
///
/// A DWM that will not answer is read as not cloaked, because the attribute is absent on a
/// desktop with composition off, where nothing is cloaked either.
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

/// Whether the window is chrome rather than content. `WS_EX_TOOLWINDOW` is what keeps a window
/// out of alt-tab, and it is what the taskbar carries: without this check the walk would resolve
/// to `Shell_TrayWnd` on an ordinary desktop, because the taskbar is topmost and so is at the
/// front of the Z-order the walk starts from.
///
/// Styles that do not fit a `u32` cannot happen (the value is a widened `DWORD`), and reading
/// them as none is the conservative arm: it keeps a window rather than silently skipping one.
fn is_tool_window(window: HWND) -> bool {
    // SAFETY: a style read on a handle from the walk; it takes and returns a plain integer.
    let styles = unsafe { GetWindowLongPtrW(window, GWL_EXSTYLE) };
    u32::try_from(styles).unwrap_or_default() & WS_EX_TOOLWINDOW.0 != 0
}

/// Whether the window has a title at all, which is how the wallpaper host (`WorkerW`) and the
/// untitled helper windows every desktop carries are told from real ones.
///
/// The **length** is read and the text never is. A window title is attacker-chosen text, this
/// ADR keeps titles out of the capture result for that reason, and counting characters is the
/// most that can be learned from one without carrying any of it.
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
///
/// The second half of the overlay check, and the one that holds for anything else on the desktop
/// that hides itself the same way (a password manager, a DRM surface, another capture-aware
/// app). Cropping to such a window would produce a black rectangle rather than an error.
///
/// A call that fails is read as excluded. That fails closed: skipping a window costs the user
/// the next one down, while capturing one that asked not to be captured is the mistake this
/// predicate exists to prevent.
fn is_hidden_from_capture(window: HWND) -> bool {
    let mut affinity = 0_u32;
    // SAFETY: the out-parameter is a live `u32`, which is what the call writes.
    let asked = unsafe { GetWindowDisplayAffinity(window, &raw mut affinity) };
    asked.is_err() || affinity != WDA_NONE.0
}

/// Where the OS says the window is, in the physical pixels the capture is in.
///
/// `DWMWA_EXTENDED_FRAME_BOUNDS` rather than `GetWindowRect`, because the latter includes the
/// invisible resize border a composited window carries and would put a strip of whatever is
/// behind the window along all four edges of the crop. `GetWindowRect` is the fallback for a
/// desktop with composition off, where there is no such border and the two agree.
///
/// The rectangle is reported exactly as given, negative edges and all: the process is
/// per-monitor DPI aware, so these are physical pixels of the virtual desktop, and a window on a
/// second monitor or half off the left of the primary one is a real case that `body_core`
/// clamps or refuses.
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
