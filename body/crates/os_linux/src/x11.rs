//! The X11 adapter for [`RootGrab`](crate::RootGrab), over `x11rb` and its `RandR` extension.

use x11rb::connection::Connection;
use x11rb::cookie::Cookie;
use x11rb::errors::{ConnectError, ConnectionError, ReplyError};
use x11rb::protocol::randr::{ConnectionExt as _, MonitorInfo};
use x11rb::protocol::xproto::{
    Atom, AtomEnum, ConnectionExt, GetGeometryReply, GetImageReply, GetPropertyReply,
    GetWindowAttributesReply, ImageFormat, ImageOrder, MapState, QueryTreeReply, Screen, Window,
    WindowClass,
};
use x11rb::rust_connection::RustConnection;
use x11rb::x11_utils::TryParse;

use crate::compose::{Piece, pieces};
use crate::screen::{
    Area, GrabError, Layer, Layout, Monitor, RootGrab, RootImage, Snapshot, TreeWindow,
};

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

/// Reads `area` of the root window of screen `number`, lists every window under it, asks whether
/// a compositing manager owns the screen and, if one does, reads each top-level window inside `area`.
fn read(
    connection: &RustConnection,
    screen: &Screen,
    number: usize,
    area: Area,
) -> Result<Snapshot, ReplyError> {
    image(connection, screen, area).and_then(|image| {
        answer(connection.intern_atom(false, b"_NET_WM_PID"))
            .and_then(|pid| windows(connection, screen.root, pid.atom))
            .and_then(|(windows, ids)| {
                let selection = format!("_NET_WM_CM_S{number}");
                answer(connection.intern_atom(false, selection.as_bytes()))
                    .and_then(|name| answer(connection.get_selection_owner(name.atom)))
                    .and_then(|owner| {
                        let composited = owner.owner != x11rb::NONE;
                        let layers = if composited {
                            layers(connection, screen, &windows, &ids, area)?
                        } else {
                            Vec::new()
                        };
                        Ok(Snapshot {
                            image,
                            windows,
                            composited,
                            layers,
                        })
                    })
            })
    })
}

/// Reads the pixels of `area` with the format the setup describes them in.
fn image(
    connection: &RustConnection,
    screen: &Screen,
    area: Area,
) -> Result<RootImage, ReplyError> {
    let Area {
        x,
        y,
        width,
        height,
    } = area;
    answer(connection.get_image(ImageFormat::Z_PIXMAP, screen.root, x, y, width, height, !0))
        .map(|reply| picture(connection, screen, area, reply))
}

/// Reads the part of each viewable top-level window inside `area`, bottom to top.
fn layers(
    connection: &RustConnection,
    screen: &Screen,
    windows: &[TreeWindow],
    ids: &[Window],
    area: Area,
) -> Result<Vec<Layer>, ReplyError> {
    let read = |piece: Piece| {
        let Area {
            x,
            y,
            width,
            height,
        } = piece.inside;
        let id = ids[piece.window];
        answer(connection.get_image(ImageFormat::Z_PIXMAP, id, x, y, width, height, !0)).map(
            |reply| Layer {
                place: piece.place,
                image: picture(connection, screen, piece.inside, reply),
            },
        )
    };
    pieces(windows, area).into_iter().map(read).collect()
}

/// Describes the pixels of one read of `area` by its depth's pixmap format and its visual's masks.
fn picture(
    connection: &RustConnection,
    screen: &Screen,
    area: Area,
    reply: GetImageReply,
) -> RootImage {
    let setup = connection.setup();
    let bits_per_pixel = setup
        .pixmap_formats
        .iter()
        .find(|format| format.depth == reply.depth)
        .map_or(0, |format| format.bits_per_pixel);
    let masks = screen
        .allowed_depths
        .iter()
        .flat_map(|depth| &depth.visuals)
        .find(|visual| visual.visual_id == reply.visual)
        .map_or((0, 0, 0), |visual| {
            (visual.red_mask, visual.green_mask, visual.blue_mask)
        });
    RootImage {
        width: u32::from(area.width),
        height: u32::from(area.height),
        depth: reply.depth,
        bits_per_pixel,
        lsb_first: setup.image_byte_order == ImageOrder::LSB_FIRST,
        masks,
        data: reply.data,
    }
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

/// Lists every window under `root` one level at a time, each after its parent, with their ids.
fn windows(
    connection: &RustConnection,
    root: Window,
    pid: Atom,
) -> Result<(Vec<TreeWindow>, Vec<Window>), ReplyError> {
    let mut windows = Vec::new();
    let mut ids = Vec::new();
    let mut level: Vec<(Option<usize>, Window)> = answer(connection.query_tree(root))?
        .children
        .into_iter()
        .map(|child| (None, child))
        .collect();
    while !level.is_empty() {
        ids.extend(level.iter().map(|(_, window)| *window));
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
    Ok((windows, ids))
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
                        input_only: attributes.class == WindowClass::INPUT_ONLY,
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
