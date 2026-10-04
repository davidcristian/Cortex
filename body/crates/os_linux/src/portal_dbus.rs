//! The session-bus adapter for [`ScreenshotPortal`](crate::ScreenshotPortal), over `zbus`.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use zbus::MatchRule;
use zbus::blocking::{Connection, MessageIterator};
use zbus::message::Type;
use zbus::zvariant::{OwnedObjectPath, OwnedValue, Value};

use crate::portal::{PortalError, PortalReply, ScreenshotPortal};

const DESTINATION: &str = "org.freedesktop.portal.Desktop";
const PATH: &str = "/org/freedesktop/portal/desktop";
const SCREENSHOT: &str = "org.freedesktop.portal.Screenshot";
const REQUEST: &str = "org.freedesktop.portal.Request";

/// `org.freedesktop.portal.Screenshot` on a D-Bus connection, or on a bus that did not open.
pub struct DbusPortal {
    connection: Result<Connection, PortalError>,
}

impl DbusPortal {
    /// Wraps `connection`, normally the user's session bus.
    #[must_use]
    pub const fn new(connection: Connection) -> Self {
        Self {
            connection: Ok(connection),
        }
    }

    /// Stands in for a bus that failed to open with `error`: every portal call fails with its text.
    #[must_use]
    pub fn absent(error: &zbus::Error) -> Self {
        Self {
            connection: Err(PortalError(error.to_string())),
        }
    }

    fn connection(&self) -> Result<&Connection, PortalError> {
        self.connection.as_ref().map_err(Clone::clone)
    }
}

impl ScreenshotPortal for DbusPortal {
    fn sender(&self) -> Result<String, PortalError> {
        self.connection()?
            .unique_name()
            .map(ToString::to_string)
            .ok_or_else(|| PortalError(String::from("the connection has no unique bus name")))
    }

    fn screenshot(&self, handle: &str, token: &str) -> Result<PortalReply, PortalError> {
        let connection = self.connection()?;
        // The portal may answer before its method reply arrives, so the match comes first.
        let mut responses = MatchRule::builder()
            .msg_type(Type::Signal)
            .interface(REQUEST)
            .and_then(|rule| rule.member("Response"))
            .and_then(|rule| rule.path(handle))
            .and_then(|rule| MessageIterator::for_match_rule(rule.build(), connection, None))
            .map_err(|error| failure(&error))?;
        let options = HashMap::from([
            ("handle_token", Value::from(token)),
            ("interactive", Value::from(false)),
        ]);
        let returned: OwnedObjectPath = connection
            .call_method(
                Some(DESTINATION),
                PATH,
                Some(SCREENSHOT),
                "Screenshot",
                &("", options),
            )
            .and_then(|reply| reply.body().deserialize())
            .map_err(|error| failure(&error))?;
        if returned.as_str() != handle {
            return Err(PortalError(format!(
                "the portal answered on {returned}, not on {handle}"
            )));
        }
        let closed = zbus::Error::Failure(String::from("the bus closed before the response"));
        let (code, results): (u32, HashMap<String, OwnedValue>) = responses
            .next()
            .unwrap_or(Err(closed))
            .and_then(|message| message.body().deserialize())
            .map_err(|error| failure(&error))?;
        let uri = results
            .get("uri")
            .and_then(|value| String::try_from(&**value).ok());
        Ok(PortalReply { code, uri })
    }

    fn read(&self, path: &Path) -> Result<Vec<u8>, PortalError> {
        fs::read(path).map_err(|error| file_failure("read", path, &error))
    }

    fn remove(&self, path: &Path) -> Result<(), PortalError> {
        fs::remove_file(path).map_err(|error| file_failure("remove", path, &error))
    }
}

fn failure(error: &zbus::Error) -> PortalError {
    PortalError(error.to_string())
}

fn file_failure(step: &str, path: &Path, error: &std::io::Error) -> PortalError {
    PortalError(format!("could not {step} {}: {error}", path.display()))
}
