//! The X11 adapter for [`SelectionRead`](crate::SelectionRead), over `x11rb`'s core requests.

use std::thread;
use std::time::{Duration, Instant};

use x11rb::connection::Connection;
use x11rb::cookie::Cookie;
use x11rb::errors::{ConnectError, ReplyError, ReplyOrIdError};
use x11rb::protocol::Event;
use x11rb::protocol::xproto::{
    Atom, AtomEnum, ConnectionExt, CreateWindowAux, EventMask, GetPropertyReply, Property, Window,
    WindowClass,
};
use x11rb::rust_connection::RustConnection;
use x11rb::{COPY_DEPTH_FROM_PARENT, COPY_FROM_PARENT, CURRENT_TIME, NONE};

use crate::clipboard::{SelectionError, SelectionRead};

/// How long a read waits for each answer from the clipboard's owner.
pub const SELECTION_LIMIT: Duration = Duration::from_secs(1);

/// How often a read looks for the owner's answer while it waits.
const POLL: Duration = Duration::from_millis(5);

/// The most bytes a `TARGETS` answer may have: 1024 atoms.
const TARGETS_LIMIT: usize = 4096;

/// The property on the read's own window that the owner writes the selection to.
const PROPERTY: &[u8] = b"CORTEX_PASTE";

/// One screen of an X server connection, or a server that could not be reached.
pub struct X11Selection {
    connection: Result<(RustConnection, usize), SelectionError>,
    limit: Duration,
}

impl X11Selection {
    /// Wraps `connection`, reading through a window on its screen `screen`, waiting
    /// [`SELECTION_LIMIT`] for each answer.
    #[must_use]
    pub const fn new(connection: RustConnection, screen: usize) -> Self {
        Self::with_limit(connection, screen, SELECTION_LIMIT)
    }

    /// As [`X11Selection::new`], waiting `limit` for each answer instead.
    #[must_use]
    pub const fn with_limit(connection: RustConnection, screen: usize, limit: Duration) -> Self {
        Self {
            connection: Ok((connection, screen)),
            limit,
        }
    }

    /// Stands in for a server that failed to open with `error`: every read fails with its text.
    #[must_use]
    pub fn absent(error: &ConnectError) -> Self {
        Self {
            connection: Err(SelectionError::Failed(error.to_string())),
            limit: SELECTION_LIMIT,
        }
    }
}

impl SelectionRead for X11Selection {
    fn offered(&self) -> Result<Vec<String>, SelectionError> {
        let (connection, number) = self.connection.as_ref().map_err(Clone::clone)?;
        let listed = transfer(connection, *number, self.limit, "TARGETS", TARGETS_LIMIT)?;
        listed.map_or_else(|| Ok(Vec::new()), |atoms| names(connection, &atoms))
    }

    fn convert(&self, target: &str, limit: usize) -> Result<Option<Vec<u8>>, SelectionError> {
        let (connection, number) = self.connection.as_ref().map_err(Clone::clone)?;
        transfer(connection, *number, self.limit, target, limit)
    }
}

impl From<ReplyOrIdError> for SelectionError {
    fn from(error: ReplyOrIdError) -> Self {
        Self::Failed(error.to_string())
    }
}

/// The selection converted to `target` through a window made for this one read.
fn transfer(
    connection: &RustConnection,
    number: usize,
    patience: Duration,
    target: &str,
    limit: usize,
) -> Result<Option<Vec<u8>>, SelectionError> {
    let screen = connection.setup().roots.get(number);
    let root = screen.ok_or_else(|| missing(number))?.root;
    let opened = Atoms::intern(connection, target).and_then(|atoms| {
        open(connection, root).map(|window| Read {
            connection,
            window,
            atoms,
            patience,
        })
    });
    let read = opened?;
    let found = read.run(limit);
    // The bytes are already read, and the window goes with the connection if this fails.
    let _ = connection
        .destroy_window(read.window)
        .map(drop)
        .and_then(|()| connection.flush());
    found
}

/// An unmapped window of this client's that reports changes to its properties.
fn open(connection: &RustConnection, root: Window) -> Result<Window, ReplyOrIdError> {
    let watch = CreateWindowAux::new().event_mask(EventMask::PROPERTY_CHANGE);
    let (depth, class, visual) = (
        COPY_DEPTH_FROM_PARENT,
        WindowClass::INPUT_ONLY,
        COPY_FROM_PARENT,
    );
    connection.generate_id().and_then(|window| {
        connection
            .create_window(depth, window, root, 0, 0, 1, 1, 0, class, visual, &watch)
            .map(|_| window)
            .map_err(ReplyOrIdError::from)
    })
}

/// The atoms one read names.
struct Atoms {
    clipboard: Atom,
    target: Atom,
    property: Atom,
    incr: Atom,
}

impl Atoms {
    /// Interns the four names, sending every request before waiting for the first answer.
    fn intern(connection: &RustConnection, target: &str) -> Result<Self, ReplyOrIdError> {
        let names: [&[u8]; 4] = [b"CLIPBOARD", target.as_bytes(), PROPERTY, b"INCR"];
        let sent: Vec<_> = names
            .iter()
            .map(|name| connection.intern_atom(false, name))
            .collect();
        sent.into_iter()
            .map(|cookie| cookie.map_err(ReplyError::from).and_then(Cookie::reply))
            .map(|reply| reply.map(|reply| reply.atom))
            .collect::<Result<Vec<Atom>, ReplyError>>()
            .map(|atoms| Self {
                clipboard: atoms[0],
                target: atoms[1],
                property: atoms[2],
                incr: atoms[3],
            })
            .map_err(ReplyOrIdError::from)
    }
}

/// One conversion through one window.
struct Read<'c> {
    connection: &'c RustConnection,
    window: Window,
    atoms: Atoms,
    patience: Duration,
}

impl Read<'_> {
    /// Asks the owner for the selection, then reads it whole or in `INCR` chunks.
    fn run(&self, limit: usize) -> Result<Option<Vec<u8>>, SelectionError> {
        let Atoms {
            clipboard,
            target,
            property,
            incr,
        } = self.atoms;
        let asked = self
            .connection
            .convert_selection(self.window, clipboard, target, property, CURRENT_TIME)
            .map(drop)
            .map_err(ReplyOrIdError::from)
            .map_err(SelectionError::from);
        if asked.and_then(|()| self.wait(selected))? == NONE {
            return Ok(None);
        }
        let first = self.take(limit)?;
        if first.type_ != incr {
            return Ok(Some(first.value));
        }
        let mut data = Vec::new();
        loop {
            let room = limit - data.len();
            let chunk = self.wait(written).and_then(|_| self.take(room))?;
            if chunk.value.is_empty() {
                return Ok(Some(data));
            }
            data.extend_from_slice(&chunk.value);
        }
    }

    /// Reads and deletes the property, failing as [`SelectionError::Over`] past `room` bytes.
    fn take(&self, room: usize) -> Result<GetPropertyReply, SelectionError> {
        let words = u32::try_from(room / 4 + 1).unwrap_or(u32::MAX);
        let (window, property) = (self.window, self.atoms.property);
        let sent = self
            .connection
            .get_property(true, window, property, AtomEnum::ANY, 0, words);
        let reply = sent
            .map_err(ReplyError::from)
            .and_then(Cookie::reply)
            .map_err(ReplyOrIdError::from)?;
        if reply.bytes_after > 0 || reply.value.len() > room {
            return Err(SelectionError::Over);
        }
        Ok(reply)
    }

    /// Waits for the first event `pick` names, for at most the read's patience.
    fn wait(&self, pick: fn(&Event, Window) -> Option<Atom>) -> Result<Atom, SelectionError> {
        let deadline = Instant::now() + self.patience;
        loop {
            let connection = self.connection;
            let polled = connection
                .flush()
                .and_then(|()| connection.poll_for_event());
            match polled.map_err(ReplyOrIdError::from)? {
                Some(Event::Error(error)) => {
                    return Err(SelectionError::Failed(format!("{error:?}")));
                }
                Some(event) => {
                    if let Some(atom) = pick(&event, self.window) {
                        return Ok(atom);
                    }
                }
                None if Instant::now() >= deadline => return Err(SelectionError::Silent),
                None => thread::sleep(POLL),
            }
        }
    }
}

/// The property a `SelectionNotify` to `window` names, `NONE` when the owner refused.
fn selected(event: &Event, window: Window) -> Option<Atom> {
    match event {
        Event::SelectionNotify(notify) if notify.requestor == window => Some(notify.property),
        _ => None,
    }
}

/// The property a new value was written to on `window`.
fn written(event: &Event, window: Window) -> Option<Atom> {
    match event {
        Event::PropertyNotify(change)
            if change.window == window && change.state == Property::NEW_VALUE =>
        {
            Some(change.atom)
        }
        _ => None,
    }
}

/// The names of the atoms a `TARGETS` answer lists, asking for every name before the first answer.
fn names(connection: &RustConnection, atoms: &[u8]) -> Result<Vec<String>, SelectionError> {
    let words = atoms.chunks_exact(4);
    let atoms = words.map(|word| u32::from_ne_bytes([word[0], word[1], word[2], word[3]]));
    let sent: Vec<_> = atoms.map(|atom| connection.get_atom_name(atom)).collect();
    sent.into_iter()
        .map(|cookie| cookie.map_err(ReplyError::from).and_then(Cookie::reply))
        .map(|reply| reply.map(|reply| String::from_utf8_lossy(&reply.name).into_owned()))
        .collect::<Result<_, _>>()
        .map_err(ReplyOrIdError::from)
        .map_err(SelectionError::from)
}

fn missing(number: usize) -> SelectionError {
    SelectionError::Failed(format!("the X server has no screen {number}"))
}
