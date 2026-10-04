//! The session-bus adapter for [`ScreenshotPortal`](crate::ScreenshotPortal), over `zbus`.

use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::time::Duration;

use async_io::Timer;
use futures_lite::{StreamExt, future};
use zbus::blocking::{Connection, MessageIterator};
use zbus::message::{Flags, Type};
use zbus::zvariant::{OwnedObjectPath, OwnedValue, Value};
use zbus::{MatchRule, Message};

use crate::portal::{PortalError, PortalReply, ScreenshotPortal};

const DESTINATION: &str = "org.freedesktop.portal.Desktop";
const PATH: &str = "/org/freedesktop/portal/desktop";
const SCREENSHOT: &str = "org.freedesktop.portal.Screenshot";
const REQUEST: &str = "org.freedesktop.portal.Request";

/// How long [`DbusPortal::new`] waits for a `Response`: the brain's default capture deadline.
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

    /// Wraps `connection`, waiting at most `limit` for each `Response`.
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
        // The portal may answer before its method reply arrives, so the match comes first.
        let mut responses = MatchRule::builder()
            .msg_type(Type::Signal)
            .interface(REQUEST)
            .and_then(|rule| rule.member("Response"))
            .and_then(|rule| rule.path(handle))
            .and_then(|rule| MessageIterator::for_match_rule(rule.build(), connection, None))
            .map(MessageIterator::into_inner)
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
        let answered = async { responses.next().await.unwrap_or(Err(closed)).map(Some) };
        let expired = async {
            Timer::after(self.limit).await;
            Ok(None)
        };
        let Some(message) =
            async_io::block_on(future::or(answered, expired)).map_err(|error| failure(&error))?
        else {
            close(connection, handle);
            return Err(PortalError(format!(
                "the portal sent no response on {handle} within {:?}",
                self.limit
            )));
        };
        let (code, results): (u32, HashMap<String, OwnedValue>) = message
            .body()
            .deserialize()
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

/// Asks the portal to end a request this side stopped waiting for, so it sends no late answer.
fn close(connection: &Connection, handle: &str) {
    // No reply is awaited, so a portal that stopped answering cannot hold this call as well. A
    // send error is dropped: the caller gets the timeout, and a broken bus fails the next call.
    let _ = Message::method_call(handle, "Close")
        .and_then(|call| call.destination(DESTINATION))
        .and_then(|call| call.interface(REQUEST))
        .and_then(|call| call.with_flags(Flags::NoReplyExpected))
        .and_then(|call| call.build(&()))
        .and_then(|message| connection.send(&message));
}

fn failure(error: &zbus::Error) -> PortalError {
    PortalError(error.to_string())
}

fn file_failure(step: &str, path: &Path, error: &std::io::Error) -> PortalError {
    PortalError(format!("could not {step} {}: {error}", path.display()))
}
