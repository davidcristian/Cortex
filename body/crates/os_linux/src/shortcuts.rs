//! The Linux [`Hotkey`] backend's logic over the desktop portal's `GlobalShortcuts` calls.

use std::sync::{Arc, Mutex, MutexGuard, Once, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use body_core::{Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};

use crate::portal::{PortalError, handle_path};
use crate::trigger::trigger;

/// The `Response` code of a request the user cancelled.
const CANCELLED: u32 = 1;

/// How long a shortcut stays held with no signal for it: above the 600 ms repeat delay of
/// `kwin_wayland`'s defaults, and short for a backend that sends no `Deactivated`.
pub const REPEAT_GAP: Duration = Duration::from_secs(1);

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

/// One `Activated` or `Deactivated` signal: the session and the id of the shortcut it names.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Activation {
    /// The session handle the shortcut belongs to.
    pub session: String,
    /// The shortcut's id.
    pub shortcut: String,
    /// True for `Activated`, a press or one auto-repeat of it, and false for `Deactivated`.
    pub active: bool,
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

    /// Blocks until the next `Activated` or `Deactivated` signal the portal sent, in its order.
    ///
    /// # Errors
    ///
    /// [`PortalError`] when the connection closes or a message cannot be read from it.
    fn next_activation(&self) -> Result<Activation, PortalError>;
}

/// Tells a new press of one shortcut from the auto-repeats the portal sends while it is held.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Hold {
    last: Option<Instant>,
}

impl Hold {
    /// Whether a signal at `now` is a press: an `Activated` (`active`) that comes after a
    /// `Deactivated`, or `gap` or more after the shortcut's last `Activated`.
    pub fn pressed(&mut self, active: bool, now: Instant, gap: Duration) -> bool {
        if !active {
            self.last = None;
            return false;
        }
        let repeat = self.last.is_some_and(|last| now.duration_since(last) < gap);
        self.last = Some(now);
        !repeat
    }
}

/// One bound shortcut: its session, its id, its callback and whether it is held.
struct Binding {
    session: String,
    shortcut: String,
    on_activate: HotkeyCallback,
    hold: Hold,
}

/// The Linux global-hotkey backend for a Wayland session, over any [`ShortcutsPortal`].
pub struct LinuxPortalHotkey {
    portal: Arc<dyn ShortcutsPortal>,
    description: String,
    tokens: Mutex<u64>,
    bindings: Arc<Mutex<Vec<Binding>>>,
    listener: Once,
    gap: Duration,
}

impl LinuxPortalHotkey {
    /// Creates the backend over `portal`, naming each shortcut to the user with `description`.
    #[must_use]
    pub fn new(portal: impl ShortcutsPortal + 'static, description: &str) -> Self {
        Self::with_gap(portal, description, REPEAT_GAP)
    }

    /// Creates the backend, ending a hold after `gap` with no signal for its shortcut.
    #[must_use]
    pub fn with_gap(
        portal: impl ShortcutsPortal + 'static,
        description: &str,
        gap: Duration,
    ) -> Self {
        Self {
            portal: Arc::new(portal),
            description: String::from(description),
            tokens: Mutex::new(0),
            bindings: Arc::new(Mutex::new(Vec::new())),
            listener: Once::new(),
            gap,
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
            hold: Hold::default(),
        });
        self.listener.call_once(|| {
            let portal = Arc::clone(&self.portal);
            let bindings = Arc::clone(&self.bindings);
            let gap = self.gap;
            thread::spawn(move || listen(portal.as_ref(), &bindings, gap));
        });
        Ok(())
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

/// Reads signals until the connection fails, running each binding a new press names once.
fn listen(portal: &dyn ShortcutsPortal, bindings: &Mutex<Vec<Binding>>, gap: Duration) {
    while let Ok(signal) = portal.next_activation() {
        let now = Instant::now();
        for binding in lock(bindings).iter_mut() {
            if binding.session == signal.session
                && binding.shortcut == signal.shortcut
                && binding.hold.pressed(signal.active, now, gap)
            {
                (binding.on_activate)();
            }
        }
    }
}

/// Locks the bindings; a callback that panicked leaves them usable.
fn lock(bindings: &Mutex<Vec<Binding>>) -> MutexGuard<'_, Vec<Binding>> {
    bindings.lock().unwrap_or_else(PoisonError::into_inner)
}
