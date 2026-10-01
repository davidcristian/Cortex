//! The X11 adapter for [`KeyGrab`](crate::KeyGrab), over `x11rb`'s core protocol requests.

use x11rb::connection::Connection;
use x11rb::cookie::{Cookie, VoidCookie};
use x11rb::errors::{ConnectError, ReplyError};
use x11rb::protocol::Event;
use x11rb::protocol::xproto::{ConnectionExt, GrabMode, ModMask, Window};
use x11rb::rust_connection::RustConnection;

use crate::hotkey::{KeyError, KeyEvent, KeyGrab, Keyboard};

/// One screen of an X server connection, or a server that could not be reached.
pub struct X11Keys {
    connection: Result<(RustConnection, usize), KeyError>,
}

impl X11Keys {
    /// Wraps `connection`, grabbing keys on the root window of its screen number `screen`.
    #[must_use]
    pub const fn new(connection: RustConnection, screen: usize) -> Self {
        Self {
            connection: Ok((connection, screen)),
        }
    }

    /// Stands in for a server that failed to open with `error`: every request fails with its text.
    #[must_use]
    pub fn absent(error: &ConnectError) -> Self {
        Self {
            connection: Err(KeyError(error.to_string())),
        }
    }

    /// The connection and its screen's root window, or why neither can be used.
    fn root(&self) -> Result<(&RustConnection, Window), KeyError> {
        let (connection, number) = self.connection.as_ref().map_err(Clone::clone)?;
        let screen = connection
            .setup()
            .roots
            .get(*number)
            .ok_or_else(|| KeyError(format!("the X server has no screen {number}")))?;
        Ok((connection, screen.root))
    }
}

impl KeyGrab for X11Keys {
    fn keyboard(&self) -> Result<Keyboard, KeyError> {
        let (connection, _) = self.root()?;
        let setup = connection.setup();
        let first = setup.min_keycode;
        let count = setup.max_keycode.saturating_sub(first).saturating_add(1);
        let mapping = connection
            .get_keyboard_mapping(first, count)
            .map_err(ReplyError::from)
            .and_then(Cookie::reply)
            .map_err(|error| KeyError(error.to_string()))?;
        let modifiers = connection
            .get_modifier_mapping()
            .map_err(ReplyError::from)
            .and_then(Cookie::reply)
            .map_err(|error| KeyError(error.to_string()))?;
        Ok(Keyboard {
            min_keycode: first,
            keysyms_per_keycode: mapping.keysyms_per_keycode,
            keysyms: mapping.keysyms,
            modifiers: modifiers.keycodes,
        })
    }

    fn grab(&self, keycode: u8, modifiers: u16) -> Result<(), KeyError> {
        let (connection, root) = self.root()?;
        connection
            .grab_key(
                false,
                root,
                ModMask::from(modifiers),
                keycode,
                GrabMode::ASYNC,
                GrabMode::ASYNC,
            )
            .map_err(ReplyError::from)
            .and_then(VoidCookie::check)
            .map_err(|error| KeyError(error.to_string()))
    }

    fn next_key(&self) -> Result<KeyEvent, KeyError> {
        let (connection, _) = self.root()?;
        loop {
            let event = connection
                .wait_for_event()
                .map_err(|error| KeyError(error.to_string()))?;
            let (key, pressed) = match event {
                Event::KeyPress(key) => (key, true),
                Event::KeyRelease(key) => (key, false),
                _ => continue,
            };
            return Ok(KeyEvent {
                keycode: key.detail,
                state: u16::from(key.state),
                time: key.time,
                pressed,
            });
        }
    }
}
