//! Lists the window tree under a root, one level at a time.

use x11rb::errors::ReplyError;
use x11rb::protocol::xproto::{
    Atom, AtomEnum, ConnectionExt, GetGeometryReply, GetPropertyReply, GetWindowAttributesReply,
    MapState, QueryTreeReply, Window, WindowClass,
};
use x11rb::rust_connection::RustConnection;

use super::{Sent, answer};
use crate::screen::{Area, TreeWindow};

/// The four requests sent for one window, in the order they are answered.
type Asked<'c> = (
    Option<usize>,
    Sent<'c, GetWindowAttributesReply>,
    Sent<'c, GetGeometryReply>,
    Sent<'c, GetPropertyReply>,
    Sent<'c, QueryTreeReply>,
);

/// Lists every window under `root` one level at a time, each after its parent, with their ids.
pub fn windows(
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
