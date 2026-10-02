//! Reads the pixels of a capture: the root's own, or each layer a compositing manager paints.

use x11rb::connection::Connection;
use x11rb::errors::ReplyError;
use x11rb::protocol::xproto::{
    AtomEnum, ConnectionExt, Drawable, GetImageReply, ImageFormat, ImageOrder, Screen, Visualid,
    Window,
};
use x11rb::rust_connection::RustConnection;

use super::answer;
use crate::compose::pieces;
use crate::screen::{Area, Layer, RootImage, TreeWindow};

/// Reads `area` of the root, described by the visual the reply names.
pub fn root(
    connection: &RustConnection,
    screen: &Screen,
    area: Area,
) -> Result<RootImage, ReplyError> {
    part(connection, screen, screen.root, area, None)
}

/// Reads the root background, then the part inside `area` of each viewable top-level window,
/// bottom to top.
pub fn layers(
    connection: &RustConnection,
    screen: &Screen,
    windows: &[TreeWindow],
    ids: &[Window],
    area: Area,
) -> Result<Vec<Layer>, ReplyError> {
    let below = background(connection, screen, area)?;
    let above = pieces(windows, area).into_iter().map(|piece| {
        part(connection, screen, ids[piece.window], piece.inside, None).map(|image| Layer {
            place: piece.place,
            image,
        })
    });
    below.into_iter().map(Ok).chain(above).collect()
}

/// Reads the part inside `area` of the pixmap the root's `_XROOTPMAP_ID` names, from the root's
/// corner and not tiled, or nothing when no pixmap at the root's depth is named.
fn background(
    connection: &RustConnection,
    screen: &Screen,
    area: Area,
) -> Result<Option<Layer>, ReplyError> {
    let named = answer(connection.intern_atom(false, b"_XROOTPMAP_ID")).and_then(|name| {
        answer(connection.get_property(false, screen.root, name.atom, AtomEnum::PIXMAP, 0, 1))
    })?;
    let Some(pixmap) = named.value32().and_then(|mut values| values.next()) else {
        return Ok(None);
    };
    let Some(geometry) = answer(connection.get_geometry(pixmap))
        .ok()
        .filter(|geometry| geometry.depth == screen.root_depth)
    else {
        return Ok(None);
    };
    let sheet = TreeWindow {
        parent: None,
        area: Area {
            x: 0,
            y: 0,
            width: geometry.width,
            height: geometry.height,
        },
        border: 0,
        viewable: true,
        pid: None,
        input_only: false,
    };
    let visual = Some(screen.root_visual);
    pieces(&[sheet], area)
        .first()
        .map(|piece| {
            part(connection, screen, pixmap, piece.inside, visual).map(|image| Layer {
                place: piece.place,
                image,
            })
        })
        .transpose()
}

/// Reads `inside` of `drawable`, described by `visual`, or when that is `None` by the reply's.
fn part(
    connection: &RustConnection,
    screen: &Screen,
    drawable: Drawable,
    inside: Area,
    visual: Option<Visualid>,
) -> Result<RootImage, ReplyError> {
    let Area {
        x,
        y,
        width,
        height,
    } = inside;
    answer(connection.get_image(ImageFormat::Z_PIXMAP, drawable, x, y, width, height, !0)).map(
        |reply| {
            let visual = visual.unwrap_or(reply.visual);
            picture(connection, screen, inside, visual, reply)
        },
    )
}

/// Describes the pixels of one read of `area` by its depth's pixmap format and `visual`'s masks.
fn picture(
    connection: &RustConnection,
    screen: &Screen,
    area: Area,
    visual: Visualid,
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
        .find(|listed| listed.visual_id == visual)
        .map_or((0, 0, 0), |listed| {
            (listed.red_mask, listed.green_mask, listed.blue_mask)
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
