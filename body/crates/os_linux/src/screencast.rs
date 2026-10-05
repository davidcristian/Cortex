//! The Linux window capture's logic over the desktop portal's `ScreenCast` calls.

use std::os::fd::OwnedFd;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Mutex, MutexGuard, PoisonError};
use std::time::Duration;

use body_core::{CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, ScreenCapture};

use crate::decode::decode_png;
use crate::portal::PortalError;

/// The bit of `AvailableSourceTypes` and of `SelectSources`' `types` that names a window.
pub const WINDOW_SOURCE: u32 = 2;

/// How long a session restored from a token may take to start: a restored `Start` answered at
/// once on headless `KWin`, and a token whose window closed opens the chooser instead.
pub const RESTORE_LIMIT: Duration = Duration::from_secs(2);

/// What a focus capture answers when no window is chosen.
pub const NO_WINDOW: &str =
    "no window is chosen to read; the user is asked to choose one when the overlay next hides";

/// One window stream that a session's `Start` gave.
#[derive(Debug)]
pub struct WindowStream {
    /// The `PipeWire` node of the stream.
    pub node: u32,
    /// The `restore_token` result, which starts the next session with no chooser.
    pub restore: Option<String>,
    /// The descriptor `OpenPipeWireRemote` returned, which reaches the stream's node.
    pub remote: OwnedFd,
}

/// How a session's `Start` ended.
#[derive(Debug)]
pub enum Started {
    /// The portal answered 0 with a stream.
    Stream(WindowStream),
    /// The portal answered with this response code: 1 when the user cancelled, 2 for a failure.
    Refused(u32),
    /// The limit passed before the portal answered.
    Expired,
}

/// One session the portal opened, and how its `Start` ended.
#[derive(Debug)]
pub struct CastSession {
    /// The session handle, which [`ScreenCastPortal::close`] ends.
    pub handle: String,
    /// How the session's `Start` ended.
    pub started: Started,
}

/// The calls the window capture makes on `org.freedesktop.portal.ScreenCast`.
pub trait ScreenCastPortal: Send + Sync {
    /// The `AvailableSourceTypes` property: 1 for a monitor, [`WINDOW_SOURCE`] for a window.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when there is no bus or the property cannot be read.
    fn source_types(&self) -> Result<u32, PortalError>;

    /// Opens and starts one window's session from `restore` if given, waiting at most `limit`.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when a call fails before `Start` ends; the adapter closes its session.
    fn start(&self, restore: Option<&str>, limit: Duration) -> Result<CastSession, PortalError>;

    /// Sends `Close` on the session `handle` and waits for no reply.
    fn close(&self, handle: &str);
}

/// A failed frame read, as the reading program or its pipe wrote it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FrameError(pub String);

/// Reads one frame of a `PipeWire` stream.
pub trait FrameReader: Send + Sync {
    /// Reads one frame of `node` through the `remote` descriptor, as PNG bytes.
    ///
    /// # Errors
    ///
    /// [`FrameError`] when the reader is missing, fails, or writes no picture.
    fn read(&self, remote: OwnedFd, node: u32) -> Result<Vec<u8>, FrameError>;
}

/// Whether `portal` offers a window source.
///
/// # Errors
///
/// [`PortalError`] when the property cannot be read.
pub fn offers_window(portal: &dyn ScreenCastPortal) -> Result<bool, PortalError> {
    Ok(portal.source_types()? & WINDOW_SOURCE != 0)
}

/// The Linux capture of the window the user chose in the portal's chooser.
pub struct LinuxWindowCapture<P, R> {
    portal: P,
    reader: R,
    grant: Grant,
}

/// The restore token the portal last gave, and whether a focus capture found none to use.
struct Grant {
    token: Mutex<Option<String>>,
    wanted: AtomicBool,
}

impl<P: ScreenCastPortal, R: FrameReader> LinuxWindowCapture<P, R> {
    /// Creates the capture over `portal` and `reader`, with no window chosen.
    #[must_use]
    pub const fn new(portal: P, reader: R) -> Self {
        Self {
            portal,
            reader,
            grant: Grant {
                token: Mutex::new(None),
                wanted: AtomicBool::new(false),
            },
        }
    }

    /// Whether a focus capture found no window chosen since the last [`Self::choose`].
    pub fn choice_wanted(&self) -> bool {
        self.grant.wanted.load(Ordering::SeqCst)
    }

    /// Opens the chooser with no token, waiting at most `limit`; returns whether a token was kept.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when a portal call fails.
    pub fn choose(&self, limit: Duration) -> Result<bool, PortalError> {
        choose(&self.portal, &self.grant, limit)
    }
}

impl<P: ScreenCastPortal, R: FrameReader> ScreenCapture for LinuxWindowCapture<P, R> {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        capture(&self.portal, &self.reader, &self.grant, request.target())
    }
}

// The logic takes `&dyn` ports so that its branches are not split per instantiation.
fn capture(
    portal: &dyn ScreenCastPortal,
    reader: &dyn FrameReader,
    grant: &Grant,
    target: CaptureTarget,
) -> Result<CapturedFrame, CaptureError> {
    if target == CaptureTarget::Display {
        return Err(CaptureError::Backend(String::from(
            "the window capture reads the chosen window, not the display",
        )));
    }
    // Held for the whole capture: a token starts one session only.
    let mut token = lock(&grant.token);
    let Some(restore) = token.clone() else {
        return Err(grant.want());
    };
    let CastSession { handle, started } = portal
        .start(Some(&restore), RESTORE_LIMIT)
        .map_err(|error| CaptureError::Backend(error.0))?;
    let stream = match started {
        Started::Stream(stream) => stream,
        Started::Refused(code) => {
            portal.close(&handle);
            *token = None;
            grant.want();
            return Err(CaptureError::Backend(format!(
                "the portal failed the restored window session with response {code}"
            )));
        }
        Started::Expired => {
            portal.close(&handle);
            *token = None;
            return Err(grant.want());
        }
    };
    *token = stream.restore;
    let bytes = reader.read(stream.remote, stream.node);
    portal.close(&handle);
    let bytes = bytes.map_err(|error| CaptureError::Backend(error.0))?;
    Ok(CapturedFrame::window_only(decode_png(&bytes)?))
}

fn choose(
    portal: &dyn ScreenCastPortal,
    grant: &Grant,
    limit: Duration,
) -> Result<bool, PortalError> {
    grant.wanted.store(false, Ordering::SeqCst);
    let CastSession { handle, started } = portal.start(None, limit)?;
    portal.close(&handle);
    let Started::Stream(WindowStream {
        restore: Some(restore),
        ..
    }) = started
    else {
        return Ok(false);
    };
    *lock(&grant.token) = Some(restore);
    Ok(true)
}

impl Grant {
    /// Records that a choice is wanted, and returns the error a focus capture answers then.
    fn want(&self) -> CaptureError {
        self.wanted.store(true, Ordering::SeqCst);
        CaptureError::NoTarget(String::from(NO_WINDOW))
    }
}

/// Locks the token; a capture that panicked leaves it usable.
fn lock(token: &Mutex<Option<String>>) -> MutexGuard<'_, Option<String>> {
    token.lock().unwrap_or_else(PoisonError::into_inner)
}
