//! The session-bus adapter for [`ScreenshotPortal`](crate::ScreenshotPortal), over `zbus`.

use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::time::Duration;

use zbus::blocking::Connection;
use zbus::zvariant::Value;

use crate::portal::{PortalError, PortalReply, ScreenshotPortal};
use crate::request::{DESTINATION, PATH, request};

const SCREENSHOT: &str = "org.freedesktop.portal.Screenshot";

/// How long [`DbusPortal::new`] waits for the method reply and the `Response` together: the
/// brain's default capture deadline.
pub const RESPONSE_LIMIT: Duration = Duration::from_secs(10);

/// `org.freedesktop.portal.Screenshot` on a D-Bus connection, or on a bus that did not open.
pub struct DbusPortal {
    connection: Result<Connection, PortalError>,
    limit: Duration,
}

impl DbusPortal {
    /// Wraps `connection`, normally the user's session bus, waiting [`RESPONSE_LIMIT`].
    #[must_use]
    pub const fn new(connection: Connection) -> Self {
        Self::with_limit(connection, RESPONSE_LIMIT)
    }

    /// Wraps `connection`, waiting at most `limit` for each call's reply and `Response`.
    #[must_use]
    pub const fn with_limit(connection: Connection, limit: Duration) -> Self {
        Self {
            connection: Ok(connection),
            limit,
        }
    }

    /// Stands in for a bus that failed to open with `error`: every portal call fails with its text.
    #[must_use]
    pub fn absent(error: &zbus::Error) -> Self {
        Self {
            connection: Err(PortalError(error.to_string())),
            limit: RESPONSE_LIMIT,
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
        let options = HashMap::from([
            ("handle_token", Value::from(token)),
            ("interactive", Value::from(false)),
        ]);
        let body = ("", &options);
        let call = connection.inner().call_method(
            Some(DESTINATION),
            PATH,
            Some(SCREENSHOT),
            "Screenshot",
            &body,
        );
        let (code, results) = request(connection, handle, self.limit, Box::pin(call))?;
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

fn file_failure(step: &str, path: &Path, error: &std::io::Error) -> PortalError {
    PortalError(format!("could not {step} {}: {error}", path.display()))
}
