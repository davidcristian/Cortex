//! The X11 adapter for [`RootGrab`](crate::RootGrab), over `x11rb` and its `RandR` extension.

use x11rb::connection::Connection;
use x11rb::cookie::Cookie;
use x11rb::errors::{ConnectError, ConnectionError, ReplyError};
use x11rb::protocol::randr::{ConnectionExt as _, MonitorInfo};
use x11rb::protocol::xproto::{
    Atom, AtomEnum, ConnectionExt, GetGeometryReply, GetPropertyReply, GetWindowAttributesReply,
    ImageFormat, ImageOrder, MapState, QueryTreeReply, Screen, Window,
};
use x11rb::rust_connection::RustConnection;
use x11rb::x11_utils::TryParse;

use crate::screen::{Area, GrabError, Layout, Monitor, RootGrab, RootImage, Snapshot, TreeWindow};

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

    fn grab(&self, area: Area) -> Result<Snapshot, GrabError> {
        let (connection, screen) = self.screen()?;
        let read = connection
            .grab_server()
            .map_err(ReplyError::from)
            .and_then(|_| read(connection, screen, area));
        let released = connection.ungrab_server().and_then(|_| connection.flush());
        read.and_then(|snapshot| released.map(|()| snapshot).map_err(ReplyError::from))
            .map_err(|error| GrabError::Failed(error.to_string()))
    }
}

/// Reads `area` of the root window, then lists every window under it.
fn read(connection: &RustConnection, screen: &Screen, area: Area) -> Result<Snapshot, ReplyError> {
    image(connection, screen, area).and_then(|image| {
        answer(connection.intern_atom(false, b"_NET_WM_PID"))
            .and_then(|pid| windows(connection, screen.root, pid.atom))
            .map(|windows| Snapshot { image, windows })
    })
}

/// Reads the pixels of `area` with the format the setup describes them in.
fn image(
    connection: &RustConnection,
    screen: &Screen,
    area: Area,
) -> Result<RootImage, ReplyError> {
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
    answer(connection.get_image(ImageFormat::Z_PIXMAP, screen.root, x, y, width, height, !0)).map(
        |reply| RootImage {
            width: u32::from(width),
            height: u32::from(height),
            depth: reply.depth,
            bits_per_pixel,
            lsb_first: setup.image_byte_order == ImageOrder::LSB_FIRST,
            masks,
            data: reply.data,
        },
    )
}

/// The four requests sent for one window, in the order they are answered.
type Asked<'c> = (
    Option<usize>,
    Sent<'c, GetWindowAttributesReply>,
    Sent<'c, GetGeometryReply>,
    Sent<'c, GetPropertyReply>,
    Sent<'c, QueryTreeReply>,
);
type Sent<'c, R> = Result<Cookie<'c, RustConnection, R>, ConnectionError>;

/// Lists every window under `root` one level at a time, each after its parent.
fn windows(
    connection: &RustConnection,
    root: Window,
    pid: Atom,
) -> Result<Vec<TreeWindow>, ReplyError> {
    let mut windows = Vec::new();
    let mut level: Vec<(Option<usize>, Window)> = answer(connection.query_tree(root))?
        .children
        .into_iter()
        .map(|child| (None, child))
        .collect();
    while !level.is_empty() {
        let asked: Vec<Asked<'_>> = level
            .into_iter()
            .map(|(parent, window)| {
                (
                    parent,
                    connection.get_window_attributes(window),
                    connection.get_geometry(window),
                    connection.get_property(false, window, pid, AtomEnum::CARDINAL, 0, 1),
                    connection.query_tree(window),
                )
            })
            .collect();
        level = Vec::new();
        for asked in asked {
            let index = windows.len();
            let (window, children) = window(asked)?;
            windows.push(window);
            level.extend(children.into_iter().map(|child| (Some(index), child)));
        }
    }
    Ok(windows)
}

/// Reads the four answers about one window: the window, then its children.
fn window(asked: Asked<'_>) -> Result<(TreeWindow, Vec<Window>), ReplyError> {
    let (parent, attributes, geometry, property, tree) = asked;
    answer(attributes).and_then(|attributes| {
        answer(geometry).and_then(|geometry| {
            answer(property).and_then(|property| {
                answer(tree).map(|tree| {
                    let window = TreeWindow {
                        parent,
                        area: Area {
                            x: geometry.x,
                            y: geometry.y,
                            width: geometry.width,
                            height: geometry.height,
                        },
                        border: geometry.border_width,
                        viewable: attributes.map_state == MapState::VIEWABLE,
                        pid: property.value32().and_then(|mut values| values.next()),
                    };
                    (window, tree.children)
                })
            })
        })
    })
}

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
