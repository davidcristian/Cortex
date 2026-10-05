//! The session-bus adapter for [`ShortcutsPortal`](crate::ShortcutsPortal), over `zbus`.

use std::collections::HashMap;
use std::sync::{Mutex, PoisonError};
use std::time::Duration;

use zbus::MatchRule;
use zbus::blocking::{Connection, MessageIterator};
use zbus::message::Type;
use zbus::zvariant::{ObjectPath, OwnedObjectPath, OwnedValue, Value};

use crate::portal::PortalError;
use crate::request::{DESTINATION, PATH, Results, request};
use crate::shortcuts::{Activation, Shortcut, ShortcutsPortal, ShortcutsReply};

const SHORTCUTS: &str = "org.freedesktop.portal.GlobalShortcuts";

/// How long [`DbusShortcuts::new`] waits for each call's reply and `Response` together; a
/// compositor may first ask the user to confirm or change the trigger.
pub const SHORTCUTS_LIMIT: Duration = Duration::from_mins(1);

/// The arguments of an `Activated` or `Deactivated` signal: session, shortcut id, timestamp and
/// options.
type Signal = (OwnedObjectPath, String, u64, HashMap<String, OwnedValue>);

/// `org.freedesktop.portal.GlobalShortcuts` on a D-Bus connection, or on a bus that did not open.
pub struct DbusShortcuts {
    connection: Result<Connection, PortalError>,
    activations: Mutex<Result<MessageIterator, PortalError>>,
    limit: Duration,
}

impl DbusShortcuts {
    /// Wraps `connection`, normally the user's session bus, waiting [`SHORTCUTS_LIMIT`].
    #[must_use]
    pub fn new(connection: Connection) -> Self {
        Self::with_limit(connection, SHORTCUTS_LIMIT)
    }

    /// Wraps `connection`, waiting at most `limit` for each call's reply and `Response`.
    #[must_use]
    pub fn with_limit(connection: Connection, limit: Duration) -> Self {
        // Subscribed before any bind, so a press between a bind and the first read is kept, and
        // to every signal on one stream, so a release is never read before the press it ends.
        let activations = MatchRule::builder()
            .msg_type(Type::Signal)
            .interface(SHORTCUTS)
            .and_then(|rule| rule.path(PATH))
            .and_then(|rule| MessageIterator::for_match_rule(rule.build(), &connection, None))
            .map_err(PortalError::from);
        Self {
            connection: Ok(connection),
            activations: Mutex::new(activations),
            limit,
        }
    }

    /// Stands in for a bus that failed to open with `error`: every portal call fails with its text.
    #[must_use]
    pub fn absent(error: &zbus::Error) -> Self {
        let error = PortalError(error.to_string());
        Self {
            connection: Err(error.clone()),
            activations: Mutex::new(Err(error)),
            limit: SHORTCUTS_LIMIT,
        }
    }

    fn connection(&self) -> Result<&Connection, PortalError> {
        self.connection.as_ref().map_err(Clone::clone)
    }
}

impl ShortcutsPortal for DbusShortcuts {
    fn sender(&self) -> Result<String, PortalError> {
        self.connection()?
            .unique_name()
            .map(ToString::to_string)
            .ok_or_else(|| PortalError(String::from("the connection has no unique bus name")))
    }

    fn create_session(
        &self,
        handle: &str,
        token: &str,
        session_token: &str,
    ) -> Result<ShortcutsReply, PortalError> {
        let connection = self.connection()?;
        let options = HashMap::from([
            ("handle_token", Value::from(token)),
            ("session_handle_token", Value::from(session_token)),
        ]);
        let body = (&options,);
        let call = connection.inner().call_method(
            Some(DESTINATION),
            PATH,
            Some(SHORTCUTS),
            "CreateSession",
            &body,
        );
        let (code, results) = request(connection, handle, self.limit, Box::pin(call))?;
        let names = results.get("session_handle").and_then(text);
        Ok(ShortcutsReply {
            code,
            names: names.into_iter().collect(),
        })
    }

    fn bind(
        &self,
        session: &str,
        handle: &str,
        token: &str,
        shortcut: &Shortcut,
    ) -> Result<ShortcutsReply, PortalError> {
        let connection = self.connection()?;
        let session = ObjectPath::try_from(session)
            .map_err(|error| PortalError::from(zbus::Error::from(error)))?;
        let details = HashMap::from([
            ("description", Value::from(shortcut.description.as_str())),
            ("preferred_trigger", Value::from(shortcut.trigger.as_str())),
        ]);
        let shortcuts = vec![(shortcut.id.as_str(), details)];
        let options = HashMap::from([("handle_token", Value::from(token))]);
        let body = (&session, &shortcuts, "", &options);
        let call = connection.inner().call_method(
            Some(DESTINATION),
            PATH,
            Some(SHORTCUTS),
            "BindShortcuts",
            &body,
        );
        let (code, results) = request(connection, handle, self.limit, Box::pin(call))?;
        Ok(ShortcutsReply {
            code,
            names: bound(&results),
        })
    }

    fn next_activation(&self) -> Result<Activation, PortalError> {
        let mut activations = self
            .activations
            .lock()
            .unwrap_or_else(PoisonError::into_inner);
        let signals = activations.as_mut().map_err(|error| error.clone())?;
        loop {
            let closed = || Err(zbus::Error::Failure(String::from("the bus closed")));
            let message = signals
                .next()
                .unwrap_or_else(closed)
                .map_err(PortalError::from)?;
            let active = match message
                .header()
                .member()
                .map(zbus::names::MemberName::as_str)
            {
                Some("Activated") => true,
                Some("Deactivated") => false,
                _ => continue,
            };
            let (session, shortcut, _, _): Signal =
                message.body().deserialize().map_err(PortalError::from)?;
            return Ok(Activation {
                session: session.to_string(),
                shortcut,
                active,
            });
        }
    }
}

/// A result that is a string or an object path, as text; the frontend sends a session handle as
/// a string.
fn text(value: &OwnedValue) -> Option<String> {
    String::try_from(&**value).ok().or_else(|| {
        <&ObjectPath<'_>>::try_from(&**value)
            .ok()
            .map(ToString::to_string)
    })
}

/// The id of each shortcut a `BindShortcuts` response lists, or none when it lists none.
fn bound(results: &Results) -> Vec<String> {
    results
        .get("shortcuts")
        .and_then(|value| value.try_clone().ok())
        .and_then(|value| Vec::<(String, HashMap<String, OwnedValue>)>::try_from(value).ok())
        .map(|shortcuts| shortcuts.into_iter().map(|(id, _)| id).collect())
        .unwrap_or_default()
}
