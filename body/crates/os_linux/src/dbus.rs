//! The session-bus adapter for [`NotificationBus`](crate::NotificationBus), over `zbus`.

use std::collections::HashMap;

use zbus::blocking::Connection;
use zbus::message::Message;
use zbus::zvariant::Value;

use crate::notify::{BusError, BusMessage, NO_BUS, NotificationBus};

const DESTINATION: &str = "org.freedesktop.Notifications";
const PATH: &str = "/org/freedesktop/Notifications";

/// `org.freedesktop.Notifications` on a D-Bus connection, or on a bus that did not open.
pub struct DbusNotifications {
    connection: Result<Connection, BusError>,
}

impl DbusNotifications {
    /// Wraps `connection`, normally the user's session bus.
    #[must_use]
    pub const fn new(connection: Connection) -> Self {
        Self {
            connection: Ok(connection),
        }
    }

    /// Stands in for a bus that failed to open with `error`: every call fails as `NoServer`.
    #[must_use]
    pub fn absent(error: &zbus::Error) -> Self {
        Self {
            connection: Err(BusError {
                name: Some(String::from(NO_BUS)),
                message: error.to_string(),
            }),
        }
    }

    fn connection(&self) -> Result<&Connection, BusError> {
        self.connection.as_ref().map_err(Clone::clone)
    }
}

impl NotificationBus for DbusNotifications {
    fn capabilities(&self) -> Result<Vec<String>, BusError> {
        let reply = self
            .connection()?
            .call_method(
                Some(DESTINATION),
                PATH,
                Some(DESTINATION),
                "GetCapabilities",
                &(),
            )
            .map_err(|error| bus_error(&error))?;
        reply
            .body()
            .deserialize()
            .map_err(|error| bus_error(&error))
    }

    fn notify(&self, message: &BusMessage) -> Result<u32, BusError> {
        let actions: Vec<&str> = Vec::new();
        let hints: HashMap<&str, Value<'_>> = HashMap::new();
        // Replace no earlier notification, no icon, and the server's own expiry (-1).
        let arguments = (
            message.app_name.as_str(),
            0_u32,
            "",
            message.summary.as_str(),
            message.body.as_str(),
            actions,
            hints,
            -1_i32,
        );
        let reply: Message = self
            .connection()?
            .call_method(
                Some(DESTINATION),
                PATH,
                Some(DESTINATION),
                "Notify",
                &arguments,
            )
            .map_err(|error| bus_error(&error))?;
        reply
            .body()
            .deserialize()
            .map_err(|error| bus_error(&error))
    }
}

/// Splits a `zbus` failure into the D-Bus error name, when there is one, and its text.
fn bus_error(error: &zbus::Error) -> BusError {
    let name = match error {
        zbus::Error::MethodError(name, _, _) => Some(name.to_string()),
        _ => None,
    };
    BusError {
        name,
        message: error.to_string(),
    }
}
