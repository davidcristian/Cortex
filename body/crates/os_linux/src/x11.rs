//! The X11 adapter for [`RootGrab`](crate::RootGrab), over `x11rb` and its `RandR` extension.

use x11rb::connection::Connection;
use x11rb::cookie::Cookie;
use x11rb::errors::{ConnectError, ConnectionError, ReplyError};
use x11rb::protocol::randr::{ConnectionExt as _, MonitorInfo};
use x11rb::protocol::xproto::{ConnectionExt, ImageFormat, ImageOrder, Screen};
use x11rb::rust_connection::RustConnection;

use crate::screen::{Area, GrabError, Layout, Monitor, RootGrab, RootImage};

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
    /// The connection and its screen, or why neither can be read.
    fn screen(&self) -> Result<(&RustConnection, &Screen), GrabError> {
        let (connection, number) = self.connection.as_ref().map_err(Clone::clone)?;
        let screen = connection
            .setup()
            .roots
            .get(*number)
            .ok_or_else(|| GrabError::Failed(format!("the X server has no screen {number}")))?;
        Ok((connection, screen))
    }
}

impl RootGrab for X11Root {
    fn layout(&self) -> Result<Layout, GrabError> {
        let (connection, screen) = self.screen()?;
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

    fn grab(&self, area: Area) -> Result<RootImage, GrabError> {
        let (connection, screen) = self.screen()?;
        let setup = connection.setup();
        let bits_per_pixel = setup
            .pixmap_formats
            .iter()
            .find(|format| format.depth == screen.root_depth)
            .map_or(0, |format| format.bits_per_pixel);
        let masks = screen
            .allowed_depths
            .iter()
            .flat_map(|depth| &depth.visuals)
            .find(|visual| visual.visual_id == screen.root_visual)
            .map_or((0, 0, 0), |visual| {
                (visual.red_mask, visual.green_mask, visual.blue_mask)
            });
        let Area {
            x,
            y,
            width,
            height,
        } = area;
        let reply = connection
            .get_image(ImageFormat::Z_PIXMAP, screen.root, x, y, width, height, !0)
            .map_err(ReplyError::from)
            .and_then(Cookie::reply)
            .map_err(|error| GrabError::Failed(error.to_string()))?;
        Ok(RootImage {
            width: u32::from(width),
            height: u32::from(height),
            depth: reply.depth,
            bits_per_pixel,
            lsb_first: setup.image_byte_order == ImageOrder::LSB_FIRST,
            masks,
            data: reply.data,
        })
    }
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
