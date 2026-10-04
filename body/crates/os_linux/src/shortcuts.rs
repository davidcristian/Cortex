//! The Linux [`Hotkey`] backend's logic over the desktop portal's `GlobalShortcuts` calls.

use std::sync::{Arc, Mutex, MutexGuard, Once, PoisonError};
use std::thread;

use body_core::{Accelerator, Hotkey, HotkeyCallback, HotkeyChord, HotkeyError, Modifier};

use crate::portal::{PortalError, handle_path};

/// The `Response` code of a request the user cancelled.
const CANCELLED: u32 = 1;

/// One shortcut a session asks the portal to bind.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Shortcut {
    /// The id the portal names the shortcut by in each `Activated` signal.
    pub id: String,
    /// The text the compositor shows the user for the shortcut.
    pub description: String,
    /// The trigger asked for, in the XDG shortcuts form such as `CTRL+ALT+space`.
    pub trigger: String,
}

/// What the portal sent in the `Response` to one request.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ShortcutsReply {
    /// The response code: 0 for success, 1 when the user cancelled, 2 for any other failure.
    pub code: u32,
    /// The session handle a `CreateSession` response names, or each shortcut id a bind bound.
    pub names: Vec<String>,
}

/// One `Activated` signal: the session and the id of the shortcut the user pressed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Activation {
    /// The session handle the shortcut belongs to.
    pub session: String,
    /// The shortcut's id.
    pub shortcut: String,
}

/// The calls the backend makes on `org.freedesktop.portal.GlobalShortcuts`.
pub trait ShortcutsPortal: Send + Sync {
    /// The unique bus name of the connection, such as `:1.16`.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when there is no bus or the connection has no unique name.
    fn sender(&self) -> Result<String, PortalError>;

    /// Calls `CreateSession` with both tokens and waits for its `Response` on `handle`.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when the call fails, answers on another handle, or sends no response.
    fn create_session(
        &self,
        handle: &str,
        token: &str,
        session_token: &str,
    ) -> Result<ShortcutsReply, PortalError>;

    /// Calls `BindShortcuts` on `session` with `shortcut` and waits for its `Response` on `handle`.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when the call fails, answers on another handle, or sends no response.
    fn bind(
        &self,
        session: &str,
        handle: &str,
        token: &str,
        shortcut: &Shortcut,
    ) -> Result<ShortcutsReply, PortalError>;

    /// Blocks until the next `Activated` signal.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when the connection closes or a signal cannot be read.
    fn next_activation(&self) -> Result<Activation, PortalError>;
}

/// One bound shortcut: its session, its id and what to run on each press.
struct Binding {
    session: String,
    shortcut: String,
    on_activate: HotkeyCallback,
}

/// The Linux global-hotkey backend for a Wayland session, over any [`ShortcutsPortal`].
pub struct LinuxPortalHotkey {
    portal: Arc<dyn ShortcutsPortal>,
    description: String,
    tokens: Mutex<u64>,
    bindings: Arc<Mutex<Vec<Binding>>>,
    listener: Once,
}

impl LinuxPortalHotkey {
    /// Creates the backend over `portal`, naming each shortcut to the user with `description`.
    #[must_use]
    pub fn new(portal: impl ShortcutsPortal + 'static, description: &str) -> Self {
        Self {
            portal: Arc::new(portal),
            description: String::from(description),
            tokens: Mutex::new(0),
            bindings: Arc::new(Mutex::new(Vec::new())),
            listener: Once::new(),
        }
    }

    /// A token no earlier request of this backend used.
    fn token(&self) -> String {
        let mut tokens = self.tokens.lock().unwrap_or_else(PoisonError::into_inner);
        *tokens += 1;
        format!("cortex{tokens}")
    }

    /// The handles of one registration's two requests and its session, from fresh tokens.
    fn handles(&self, sender: &str) -> Result<Handles, HotkeyError> {
        let (create, bind) = (self.token(), self.token());
        handle_path("request", sender, &create)
            .zip(handle_path("session", sender, &create))
            .zip(handle_path("request", sender, &bind))
            .map(|((create_handle, session), bind_handle)| Handles {
                create: (create_handle, create),
                session,
                bind: (bind_handle, bind),
            })
            .ok_or_else(|| {
                HotkeyError::Registration(format!(
                    "the bus named this connection {sender:?}, which is not a unique name"
                ))
            })
    }
}

/// One registration's request handles with their tokens, and its session handle.
struct Handles {
    create: (String, String),
    session: String,
    bind: (String, String),
}

impl Hotkey for LinuxPortalHotkey {
    fn register(
        &self,
        chord: &HotkeyChord,
        on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        let shortcut = Shortcut {
            id: chord.to_string(),
            description: self.description.clone(),
            trigger: trigger(chord)?,
        };
        let refused =
            |error: PortalError| HotkeyError::Registration(format!("{chord}: {}", error.0));
        let sender = self.portal.sender().map_err(refused)?;
        let Handles {
            create,
            session,
            bind,
        } = self.handles(&sender)?;
        let created = self
            .portal
            .create_session(&create.0, &create.1, &create.1)
            .map_err(refused)?;
        answered("the session", &created, &session)?;
        let bound = self
            .portal
            .bind(&session, &bind.0, &bind.1, &shortcut)
            .map_err(refused)?;
        answered("the shortcut", &bound, &shortcut.id)?;
        lock(&self.bindings).push(Binding {
            session,
            shortcut: shortcut.id,
            on_activate,
        });
        self.listener.call_once(|| {
            let portal = Arc::clone(&self.portal);
            let bindings = Arc::clone(&self.bindings);
            thread::spawn(move || listen(portal.as_ref(), &bindings));
        });
        Ok(())
    }
}

/// The trigger a chord asks for, in the XDG shortcuts form: modifiers, then the key's keysym name.
///
/// # Errors
///
/// [`HotkeyError::UnsupportedKey`] when the chord's key has no code or no keysym name here.
pub fn trigger(chord: &HotkeyChord) -> Result<String, HotkeyError> {
    let key = key(chord)?;
    let mut parts: Vec<&str> = chord
        .modifiers()
        .iter()
        .map(|&each| modifier(each))
        .collect();
    parts.push(&key);
    Ok(parts.join("+"))
}

/// The keysym name of a chord's key, or [`HotkeyError::UnsupportedKey`].
fn key(chord: &HotkeyChord) -> Result<String, HotkeyError> {
    let code = Accelerator::from_chord(chord)?.code;
    keysym_name(&code).ok_or(HotkeyError::UnsupportedKey(code))
}

/// The modifier's name in the XDG shortcuts form.
const fn modifier(modifier: Modifier) -> &'static str {
    match modifier {
        Modifier::Ctrl => "CTRL",
        Modifier::Alt => "ALT",
        Modifier::Shift => "SHIFT",
        Modifier::Super => "LOGO",
    }
}

/// The xkb keysym name of a `KeyboardEvent.code` name, or `None` for a code with none here.
#[must_use]
pub fn keysym_name(code: &str) -> Option<String> {
    let named = match code {
        "Space" => "space",
        "Enter" => "Return",
        "Escape" => "Escape",
        "Tab" => "Tab",
        "Backspace" => "BackSpace",
        "ArrowUp" => "Up",
        "ArrowDown" => "Down",
        "ArrowLeft" => "Left",
        "ArrowRight" => "Right",
        _ => return printable(code),
    };
    Some(String::from(named))
}

/// The keysym name of a letter, digit or function key code: `KeyA` is `a`, `Digit1` is `1`.
fn printable(code: &str) -> Option<String> {
    match code.as_bytes() {
        [b'K', b'e', b'y', letter @ b'A'..=b'Z'] => {
            Some(char::from(letter.to_ascii_lowercase()).to_string())
        }
        [b'D', b'i', b'g', b'i', b't', digit @ b'0'..=b'9'] => Some(char::from(*digit).to_string()),
        [b'F', ..] => code[1..]
            .parse::<u32>()
            .ok()
            .filter(|number| (1..=35).contains(number))
            .map(|number| format!("F{number}")),
        _ => None,
    }
}

/// Refuses every reply that is not a success naming `expected`.
fn answered(what: &str, reply: &ShortcutsReply, expected: &str) -> Result<(), HotkeyError> {
    match reply.code {
        0 if reply.names.iter().any(|name| name == expected) => Ok(()),
        0 => Err(HotkeyError::Registration(format!(
            "the portal answered success without {what} {expected}"
        ))),
        CANCELLED => Err(HotkeyError::Registration(format!(
            "the user cancelled {what} {expected}"
        ))),
        code => Err(HotkeyError::Registration(format!(
            "the portal failed {what} {expected} with response {code}"
        ))),
    }
}

/// Reads `Activated` signals until the connection fails, running each binding a signal names.
fn listen(portal: &dyn ShortcutsPortal, bindings: &Mutex<Vec<Binding>>) {
    while let Ok(activation) = portal.next_activation() {
        for binding in lock(bindings).iter() {
            if binding.session == activation.session && binding.shortcut == activation.shortcut {
                (binding.on_activate)();
            }
        }
    }
}

/// Locks the bindings; a callback that panicked leaves them usable.
fn lock(bindings: &Mutex<Vec<Binding>>) -> MutexGuard<'_, Vec<Binding>> {
    bindings.lock().unwrap_or_else(PoisonError::into_inner)
}
