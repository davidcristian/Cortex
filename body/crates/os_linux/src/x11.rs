//! The X11 adapter for [`RootGrab`](crate::RootGrab), over `x11rb` and its `RandR` extension.

mod pixels;
mod tree;

use x11rb::connection::Connection;
use x11rb::cookie::Cookie;
use x11rb::errors::{ConnectError, ConnectionError, ReplyError};
use x11rb::protocol::randr::{ConnectionExt as _, MonitorInfo};
use x11rb::protocol::xproto::{ConnectionExt, Screen};
use x11rb::rust_connection::RustConnection;
use x11rb::x11_utils::TryParse;

use crate::screen::{Area, GrabError, Layout, Monitor, Pixels, RootGrab, Snapshot};

/// One screen of an X server connection, or a server that could not be reached.
pub struct X11Root {
    connection: Result<(RustConnection, usize), GrabError>,
}

impl X11Root {
    /// Wraps `connection`, reading screen number `screen` of it.
    #[must_use]
    pub const fn new(connection: RustConnection, screen: usize) -> Self {
        Self {
            connection: Ok((connection, screen)),
        }
    }

    /// Stands in for a server that failed to open with `error`: every read fails as `NoDisplay`.
    #[must_use]
    pub fn absent(error: &ConnectError) -> Self {
        Self {
            connection: Err(GrabError::NoDisplay(error.to_string())),
        }
    }
}

impl X11Root {
    /// The connection, its screen and that screen's number, or why none can be read.
    fn screen(&self) -> Result<(&RustConnection, &Screen, usize), GrabError> {
        let (connection, number) = self.connection.as_ref().map_err(Clone::clone)?;
        let screen = connection
            .setup()
            .roots
            .get(*number)
            .ok_or_else(|| GrabError::Failed(format!("the X server has no screen {number}")))?;
        Ok((connection, screen, *number))
    }
}

impl RootGrab for X11Root {
    fn layout(&self) -> Result<Layout, GrabError> {
        let (connection, screen, _) = self.screen()?;
        let root = Area {
            x: 0,
            y: 0,
            width: screen.width_in_pixels,
            height: screen.height_in_pixels,
        };
        let listed = connection
            .randr_get_monitors(screen.root, true)
            .map_err(ReplyError::from)
            .and_then(Cookie::reply);
        let monitors = match listed {
            Ok(reply) => reply.monitors.iter().map(monitor).collect(),
            Err(ReplyError::ConnectionError(ConnectionError::UnsupportedExtension)) => Vec::new(),
            Err(error) => return Err(GrabError::Failed(error.to_string())),
        };
        Ok(Layout { root, monitors })
    }

    fn grab(&self, area: Area) -> Result<Snapshot, GrabError> {
        let (connection, screen, number) = self.screen()?;
        let read = connection
            .grab_server()
            .map_err(ReplyError::from)
            .and_then(|_| read(connection, screen, number, area));
        let released = connection.ungrab_server().and_then(|_| connection.flush());
        read.and_then(|snapshot| released.map(|()| snapshot).map_err(ReplyError::from))
            .map_err(|error| GrabError::Failed(error.to_string()))
    }
}

/// Lists every window under the root of screen `number`, asks whether a compositing manager owns
/// the screen, then reads `area` from the root if none does, or in layers if one does.
fn read(
    connection: &RustConnection,
    screen: &Screen,
    number: usize,
    area: Area,
) -> Result<Snapshot, ReplyError> {
    answer(connection.intern_atom(false, b"_NET_WM_PID"))
        .and_then(|pid| tree::windows(connection, screen.root, pid.atom))
        .and_then(|(windows, ids)| {
            let selection = format!("_NET_WM_CM_S{number}");
            answer(connection.intern_atom(false, selection.as_bytes()))
                .and_then(|name| answer(connection.get_selection_owner(name.atom)))
                .and_then(|owner| {
                    if owner.owner == x11rb::NONE {
                        pixels::root(connection, screen, area).map(Pixels::Root)
                    } else {
                        pixels::layers(connection, screen, &windows, &ids, area).map(Pixels::Layers)
                    }
                })
                .map(|pixels| Snapshot { windows, pixels })
        })
}

type Sent<'c, R> = Result<Cookie<'c, RustConnection, R>, ConnectionError>;

/// Waits for the reply to a request, or returns why it was not sent or failed.
fn answer<R: TryParse>(sent: Sent<'_, R>) -> Result<R, ReplyError> {
    sent.map_err(ReplyError::from).and_then(Cookie::reply)
}

/// Translates one `RandR` monitor to the core's.
const fn monitor(info: &MonitorInfo) -> Monitor {
    Monitor {
        primary: info.primary,
        area: Area {
            x: info.x,
            y: info.y,
            width: info.width,
            height: info.height,
        },
    }
}
