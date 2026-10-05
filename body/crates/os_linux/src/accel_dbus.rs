//! The session-bus adapter for [`GlobalAccel`](crate::GlobalAccel), over `zbus`.

use std::sync::{Mutex, PoisonError};

use zbus::MatchRule;
use zbus::blocking::{Connection, MessageIterator};
use zbus::message::Type;
use zbus::names::{MemberName, UniqueName};

use crate::accel::{AccelError, COMPONENT, GlobalAccel, Press};
use crate::shortcuts_dbus::owner;

const SERVICE: &str = "org.kde.kglobalaccel";
const PATH: &str = "/kglobalaccel";
const ACCEL: &str = "org.kde.KGlobalAccel";
const SIGNALS: &str = "org.kde.kglobalaccel.Component";
const COMPONENT_PATH: &str = "/component/cortex";
/// The component's name in System Settings.
const FRIENDLY: &str = "Cortex";
/// `setShortcut`'s `NoAutoloading` (4), so the key given replaces one kept from an earlier run,
/// and `SetPresent` (2), so `kglobalaccel` grabs it now.
const SET_GIVEN: u32 = 6;

/// The arguments of a press or release signal: component, action and timestamp.
type Signal = (String, String, i64);

/// The signals a connection subscribed to, and `kglobalaccel`'s unique bus name once named.
struct Listener {
    signals: MessageIterator,
    connection: Connection,
    owner: Option<String>,
}

/// `org.kde.kglobalaccel` on a D-Bus connection, or on a bus that did not open.
pub struct DbusGlobalAccel {
    connection: Result<Connection, AccelError>,
    presses: Mutex<Result<Listener, AccelError>>,
}

impl DbusGlobalAccel {
    /// Wraps `connection`, normally the user's session bus.
    #[must_use]
    pub fn new(connection: Connection) -> Self {
        // Subscribed before any registration, so a press between it and the first read is kept.
        let presses = MatchRule::builder()
            .msg_type(Type::Signal)
            .interface(SIGNALS)
            .and_then(|rule| rule.path(COMPONENT_PATH))
            .and_then(|rule| MessageIterator::for_match_rule(rule.build(), &connection, None))
            .map(|signals| Listener {
                signals,
                connection: connection.clone(),
                owner: None,
            })
            .map_err(AccelError::from);
        Self {
            connection: Ok(connection),
            presses: Mutex::new(presses),
        }
    }

    /// Stands in for a bus that failed to open with `error`: every call fails with its text.
    #[must_use]
    pub fn absent(error: &zbus::Error) -> Self {
        let error = AccelError(error.to_string());
        Self {
            connection: Err(error.clone()),
            presses: Mutex::new(Err(error)),
        }
    }

    fn connection(&self) -> Result<&Connection, AccelError> {
        self.connection.as_ref().map_err(Clone::clone)
    }
}

/// Whether `org.kde.kglobalaccel` has an owner on `connection`'s bus, as on a KDE Plasma session.
#[must_use]
pub fn kglobalaccel_running(connection: &Connection) -> bool {
    owner(connection, SERVICE).is_some()
}

impl GlobalAccel for DbusGlobalAccel {
    fn bind(&self, action: &str, description: &str, key: i32) -> Result<Vec<i32>, AccelError> {
        let connection = self.connection()?;
        let id = [COMPONENT, action, FRIENDLY, description];
        let id = (id.as_slice(),);
        connection
            .call_method(Some(SERVICE), PATH, Some(ACCEL), "doRegister", &id)
            .map_err(AccelError::from)?;
        let body = (id.0, vec![key], SET_GIVEN);
        connection
            .call_method(Some(SERVICE), PATH, Some(ACCEL), "setShortcut", &body)
            .and_then(|reply| reply.body().deserialize())
            .map_err(AccelError::from)
    }

    fn unbind(&self, action: &str) -> Result<(), AccelError> {
        let body = (COMPONENT, action);
        self.connection()?
            .call_method(Some(SERVICE), PATH, Some(ACCEL), "unregister", &body)
            .map(drop)
            .map_err(AccelError::from)
    }

    fn next_press(&self) -> Result<Press, AccelError> {
        let mut presses = self.presses.lock().unwrap_or_else(PoisonError::into_inner);
        let listener = presses.as_mut().map_err(|error| error.clone())?;
        loop {
            let closed = || Err(zbus::Error::Failure(String::from("the bus closed")));
            let message = listener
                .signals
                .next()
                .unwrap_or_else(closed)
                .map_err(AccelError::from)?;
            let header = message.header();
            let active = match header.member().map(MemberName::as_str) {
                Some("globalShortcutPressed") => true,
                Some("globalShortcutReleased") => false,
                _ => continue,
            };
            if listener.owner.is_none() {
                listener.owner = owner(&listener.connection, SERVICE);
            }
            // Any process on the bus can send these signals, so only `kglobalaccel`'s are read.
            let sender = header.sender().map(UniqueName::as_str);
            if sender.is_none() || sender != listener.owner.as_deref() {
                continue;
            }
            let Ok((_, action, _)) = message.body().deserialize::<Signal>() else {
                continue;
            };
            return Ok(Press { action, active });
        }
    }
}

impl From<zbus::Error> for AccelError {
    fn from(error: zbus::Error) -> Self {
        Self(error.to_string())
    }
}
