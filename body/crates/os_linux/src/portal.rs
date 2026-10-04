//! The Linux [`ScreenCapture`] backend's logic over the desktop portal's `Screenshot` call.

use std::ffi::OsString;
use std::os::unix::ffi::OsStringExt;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, PoisonError};

use body_core::{CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, ScreenCapture};

use crate::decode::decode_png;

/// The object path the portal frontend's request and session handles sit under.
const HANDLE_ROOT: &str = "/org/freedesktop/portal/desktop";

/// The `Response` code of a request the user cancelled.
const CANCELLED: u32 = 1;

/// What the portal sent in the `Response` signal of one request.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PortalReply {
    /// The response code: 0 for success, 1 when the user cancelled, 2 for any other failure.
    pub code: u32,
    /// The `uri` result when it was present and a string.
    pub uri: Option<String>,
}

/// A failed portal call or file step, as the bus or the file system wrote it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PortalError(pub String);

/// The calls the backend makes on the portal and on the file the portal wrote.
pub trait ScreenshotPortal: Send + Sync {
    /// The unique bus name of the connection, such as `:1.16`.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when there is no bus or the connection has no unique name.
    fn sender(&self) -> Result<String, PortalError>;

    /// Subscribes to `Response` on `handle`, then calls `Screenshot` with `token`, and waits.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when a call fails, answers on another handle, or cannot be read.
    fn screenshot(&self, handle: &str, token: &str) -> Result<PortalReply, PortalError>;

    /// Reads the file at `path`.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when the file cannot be read.
    fn read(&self, path: &Path) -> Result<Vec<u8>, PortalError>;

    /// Removes the file at `path`.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when the file cannot be removed.
    fn remove(&self, path: &Path) -> Result<(), PortalError>;
}

/// The Linux screen-capture backend for a Wayland session, over any [`ScreenshotPortal`].
pub struct LinuxPortalCapture<P> {
    portal: P,
    // Held for a whole capture: a portal may write every picture to one fixed path.
    requests: Mutex<u64>,
}

impl<P: ScreenshotPortal> LinuxPortalCapture<P> {
    /// Creates the backend over `portal`.
    #[must_use]
    pub const fn new(portal: P) -> Self {
        Self {
            portal,
            requests: Mutex::new(0),
        }
    }
}

impl<P: ScreenshotPortal> ScreenCapture for LinuxPortalCapture<P> {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        display_only(request.target())?;
        let mut requests = self.requests.lock().unwrap_or_else(PoisonError::into_inner);
        let token = format!("cortex{requests}");
        *requests += 1;
        let handle = request_path(&self.portal.sender().map_err(failed)?, &token)?;
        let reply = self.portal.screenshot(&handle, &token).map_err(failed)?;
        let path = picture_path(reply)?;
        let bytes = self.portal.read(&path).map_err(failed)?;
        self.portal.remove(&path).map_err(failed)?;
        Ok(CapturedFrame::display(decode_png(&bytes)?))
    }
}

/// Refuses a focus target before any picture is taken, since a portal picture names no window.
fn display_only(target: CaptureTarget) -> Result<(), CaptureError> {
    match target {
        CaptureTarget::Display => Ok(()),
        CaptureTarget::Focus => Err(CaptureError::NoTarget(String::from(
            "a portal screenshot does not say where any window is",
        ))),
    }
}

/// The request handle the portal frontend creates for `sender` and `token`.
///
/// # Errors
///
/// [`CaptureError::Backend`] when `sender` is not a unique name.
pub fn request_path(sender: &str, token: &str) -> Result<String, CaptureError> {
    handle_path("request", sender, token).ok_or_else(|| {
        CaptureError::Backend(format!(
            "the bus named this connection {sender:?}, which is not a unique name"
        ))
    })
}

/// The `kind` handle, `request` or `session`, the frontend creates for `sender` and `token`, or
/// `None` when `sender` is not a unique name.
pub(crate) fn handle_path(kind: &str, sender: &str, token: &str) -> Option<String> {
    let name = sender.strip_prefix(':')?;
    Some(format!(
        "{HANDLE_ROOT}/{kind}/{}/{token}",
        name.replace('.', "_")
    ))
}

/// The local file a reply names, refusing every reply that is not a success with a `uri`.
fn picture_path(reply: PortalReply) -> Result<PathBuf, CaptureError> {
    match (reply.code, reply.uri) {
        (0, Some(uri)) => file_path(&uri),
        (0, None) => Err(CaptureError::Backend(String::from(
            "the portal answered success with no picture uri",
        ))),
        (CANCELLED, _) => Err(CaptureError::Backend(String::from(
            "the screenshot request was cancelled",
        ))),
        (code, _) => Err(CaptureError::Backend(format!(
            "the portal failed the screenshot with response {code}"
        ))),
    }
}

/// The path of a `file://` uri with an empty host, with each `%XX` escape decoded.
///
/// # Errors
///
/// [`CaptureError::Backend`] for any other uri, or an escape that is not two hex digits.
pub fn file_path(uri: &str) -> Result<PathBuf, CaptureError> {
    let refused = || CaptureError::Backend(format!("the picture uri {uri:?} is not a local file"));
    let path = uri
        .strip_prefix("file://")
        .filter(|path| path.starts_with('/'))
        .ok_or_else(refused)?;
    let mut parts = path.split('%');
    let mut bytes = parts.next().unwrap_or_default().as_bytes().to_vec();
    for part in parts {
        let (byte, rest) = part
            .split_at_checked(2)
            .filter(|(hex, _)| hex.bytes().all(|digit| digit.is_ascii_hexdigit()))
            .and_then(|(hex, rest)| u8::from_str_radix(hex, 16).ok().map(|byte| (byte, rest)))
            .ok_or_else(refused)?;
        bytes.push(byte);
        bytes.extend_from_slice(rest.as_bytes());
    }
    Ok(PathBuf::from(OsString::from_vec(bytes)))
}

/// Maps a failed portal or file step to the port's error: every one is `Backend`.
fn failed(error: PortalError) -> CaptureError {
    CaptureError::Backend(error.0)
}
