//! Lists the window tree under a root, one level at a time.

use x11rb::errors::ReplyError;
use x11rb::protocol::xproto::{
    Atom, AtomEnum, ConnectionExt, GetGeometryReply, GetPropertyReply, GetWindowAttributesReply,
    MapState, QueryTreeReply, Window, WindowClass,
};
use x11rb::rust_connection::RustConnection;

use super::{Sent, answer};
use crate::screen::{Area, TreeWindow};

/// How many atoms of a window's `_NET_WM_WINDOW_TYPE` list are read, more than a client sets.
const TYPES: u32 = 32;

/// The six requests sent for one window, in the order they are answered.
type Asked<'c> = (
    Option<usize>,
    Sent<'c, GetWindowAttributesReply>,
    Sent<'c, GetGeometryReply>,
    Sent<'c, GetPropertyReply>,
    Sent<'c, GetPropertyReply>,
    Sent<'c, GetPropertyReply>,
    Sent<'c, QueryTreeReply>,
);

/// The atoms a tree read names properties and window types by.
pub struct Atoms {
    /// `_NET_WM_PID`, the process that owns a window.
    pid: Atom,
    /// `_NET_WM_WINDOW_TYPE`, a client's list of window types.
    kind: Atom,
    /// `_NET_WM_WINDOW_TYPE_DOCK` and `_NET_WM_WINDOW_TYPE_DESKTOP`.
    dock_or_desktop: [Atom; 2],
}

impl Atoms {
    /// Interns every atom a tree read uses, sending all four requests before reading a reply.
    pub fn intern(connection: &RustConnection) -> Result<Self, ReplyError> {
        let [pid, kind, dock, desktop] = [
            b"_NET_WM_PID".as_slice(),
            b"_NET_WM_WINDOW_TYPE",
            b"_NET_WM_WINDOW_TYPE_DOCK",
            b"_NET_WM_WINDOW_TYPE_DESKTOP",
        ]
        .map(|name| connection.intern_atom(false, name));
        answer(pid).and_then(|pid| {
            answer(kind).and_then(|kind| {
                answer(dock).and_then(|dock| {
                    answer(desktop).map(|desktop| Self {
                        pid: pid.atom,
                        kind: kind.atom,
                        dock_or_desktop: [dock.atom, desktop.atom],
                    })
                })
            })
        })
    }
}

/// Lists every window under `root` one level at a time, each after its parent, with their ids.
pub fn windows(
    connection: &RustConnection,
    root: Window,
    atoms: &Atoms,
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
                    connection.get_property(false, window, atoms.pid, AtomEnum::CARDINAL, 0, 1),
                    connection.get_property(false, window, AtomEnum::WM_NAME, AtomEnum::ANY, 0, 0),
                    connection.get_property(false, window, atoms.kind, AtomEnum::ATOM, 0, TYPES),
                    connection.query_tree(window),
                )
            })
            .collect();
        level = Vec::new();
        for asked in asked {
            let index = windows.len();
            let (window, children) = window(asked, atoms.dock_or_desktop)?;
            windows.push(window);
            level.extend(children.into_iter().map(|child| (Some(index), child)));
        }
    }
    Ok((windows, ids))
}

/// Reads the six answers about one window: the window, then its children.
fn window(
    asked: Asked<'_>,
    dock_or_desktop: [Atom; 2],
) -> Result<(TreeWindow, Vec<Window>), ReplyError> {
    let (parent, attributes, geometry, property, name, kind, tree) = asked;
    answer(attributes).and_then(|attributes| {
        answer(geometry).and_then(|geometry| {
            answer(property).and_then(|property| {
                answer(name).and_then(|name| {
                    answer(kind).and_then(|kind| {
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
                                titled: name.bytes_after > 0,
                                override_redirect: attributes.override_redirect,
                                dock_or_desktop: kind.value32().is_some_and(|mut types| {
                                    types.any(|atom| dock_or_desktop.contains(&atom))
                                }),
                            };
                            (window, tree.children)
                        })
                    })
                })
            })
        })
    })
}
