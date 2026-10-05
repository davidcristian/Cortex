//! The session-bus adapter for [`ScreenCastPortal`](crate::ScreenCastPortal), over `zbus`.

use std::collections::HashMap;
use std::sync::{Mutex, PoisonError};
use std::time::{Duration, Instant};

use zbus::blocking::Connection;
use zbus::zvariant::{self, OwnedObjectPath, OwnedValue, Value};

use crate::portal::PortalError;
use crate::portal_dbus::RESPONSE_LIMIT;
use crate::request::{Answer, DESTINATION, PATH, Pending, Results, answered, before, close};
use crate::screencast::{CastSession, ScreenCastPortal, Started, WINDOW_SOURCE, WindowStream};

const SCREENCAST: &str = "org.freedesktop.portal.ScreenCast";
const SESSION: &str = "org.freedesktop.portal.Session";
const PROPERTIES: &str = "org.freedesktop.DBus.Properties";
/// `cursor_mode` 1: the frame has no cursor drawn in it.
const HIDDEN_CURSOR: u32 = 1;
/// `persist_mode` 1: the portal keeps the grant while this program runs.
const WHILE_RUNNING: u32 = 1;

/// The streams a `Start` response lists: each node with its properties.
type Streams = Vec<(u32, HashMap<String, OwnedValue>)>;

/// `org.freedesktop.portal.ScreenCast` on a D-Bus connection, or on a bus that did not open.
pub struct DbusScreenCast {
    connection: Result<Connection, PortalError>,
    sessions: Mutex<u64>,
    limit: Duration,
}

/// The handles one session's calls use, under this connection's part of the handle paths.
struct Handles {
    session: OwnedObjectPath,
    base: String,
    token: String,
}

impl DbusScreenCast {
    /// Wraps `connection`, normally the user's session bus, waiting [`RESPONSE_LIMIT`] for the
    /// source types.
    #[must_use]
    pub const fn new(connection: Connection) -> Self {
        Self::with_limit(connection, RESPONSE_LIMIT)
    }

    /// Wraps `connection`, waiting at most `limit` for the source types.
    #[must_use]
    pub const fn with_limit(connection: Connection, limit: Duration) -> Self {
        Self {
            connection: Ok(connection),
            sessions: Mutex::new(0),
            limit,
        }
    }

    /// Stands in for a bus that failed to open with `error`: every portal call fails with its text.
    #[must_use]
    pub fn absent(error: &zbus::Error) -> Self {
        Self {
            connection: Err(PortalError(error.to_string())),
            sessions: Mutex::new(0),
            limit: RESPONSE_LIMIT,
        }
    }

    fn connection(&self) -> Result<&Connection, PortalError> {
        self.connection.as_ref().map_err(Clone::clone)
    }

    /// The handles of a session no earlier one of this adapter used.
    fn handles(&self, connection: &Connection) -> Result<Handles, PortalError> {
        let mut sessions = self.sessions.lock().unwrap_or_else(PoisonError::into_inner);
        *sessions += 1;
        // A prefix of its own: the shortcuts adapter may number its tokens on the same connection.
        let token = format!("cortexcast{sessions}");
        let base = connection
            .unique_name()
            .and_then(|name| name.strip_prefix(':'))
            .map(|name| name.replace('.', "_"))
            .ok_or_else(|| PortalError(String::from("the connection has no unique bus name")))?;
        let session = OwnedObjectPath::try_from(format!("{PATH}/session/{base}/{token}"))
            .map_err(|error| PortalError::from(zbus::Error::from(error)))?;
        Ok(Handles {
            session,
            base,
            token,
        })
    }
}

impl ScreenCastPortal for DbusScreenCast {
    fn source_types(&self) -> Result<u32, PortalError> {
        let connection = self.connection()?;
        let call = connection.inner().call_method(
            Some(DESTINATION),
            PATH,
            Some(PROPERTIES),
            "Get",
            &(SCREENCAST, "AvailableSourceTypes"),
        );
        let reply = before(Instant::now() + self.limit, Box::pin(call))?.ok_or_else(|| {
            PortalError(format!(
                "the portal sent no source types within {:?}",
                self.limit
            ))
        })?;
        reply
            .body()
            .deserialize::<OwnedValue>()
            .and_then(|value| u32::try_from(value).map_err(zbus::Error::from))
            .map_err(PortalError::from)
    }

    fn start(&self, restore: Option<&str>, limit: Duration) -> Result<CastSession, PortalError> {
        let connection = self.connection()?;
        let handles = self.handles(connection)?;
        let deadline = Instant::now() + limit;
        match open(connection, &handles, restore, deadline) {
            Ok(started) => Ok(CastSession {
                handle: handles.session.to_string(),
                started,
            }),
            Err(error) => {
                close(connection, handles.session.as_str(), SESSION);
                Err(error)
            }
        }
    }

    fn close(&self, handle: &str) {
        if let Ok(connection) = self.connection() {
            close(connection, handle, SESSION);
        }
    }
}

/// Creates the session, selects one window source, starts it, and opens its `PipeWire` remote.
fn open(
    connection: &Connection,
    handles: &Handles,
    restore: Option<&str>,
    deadline: Instant,
) -> Result<Started, PortalError> {
    let session = &handles.session;
    let (handle, token) = handles.request("create");
    let options = HashMap::from([
        ("handle_token", Value::from(token.as_str())),
        ("session_handle_token", Value::from(handles.token.as_str())),
    ]);
    let body = (&options,);
    let reply = screencast(connection, "CreateSession", &body);
    let (code, _) = wait(connection, &handle, deadline, reply)??;
    succeeded("CreateSession", code)?;
    let (handle, token) = handles.request("select");
    let mut options = HashMap::from([
        ("handle_token", Value::from(token.as_str())),
        ("types", Value::from(WINDOW_SOURCE)),
        ("multiple", Value::from(false)),
        ("cursor_mode", Value::from(HIDDEN_CURSOR)),
        ("persist_mode", Value::from(WHILE_RUNNING)),
    ]);
    if let Some(restore) = restore {
        options.insert("restore_token", Value::from(restore));
    }
    let body = (session, &options);
    let reply = screencast(connection, "SelectSources", &body);
    let (code, _) = wait(connection, &handle, deadline, reply)??;
    succeeded("SelectSources", code)?;
    let (handle, token) = handles.request("start");
    let options = HashMap::from([("handle_token", Value::from(token.as_str()))]);
    let body = (session, "", &options);
    let reply = screencast(connection, "Start", &body);
    let Ok((code, results)) = wait(connection, &handle, deadline, reply)? else {
        return Ok(Started::Expired);
    };
    if code != 0 {
        return Ok(Started::Refused(code));
    }
    let node = first_node(&results)
        .ok_or_else(|| PortalError(String::from("the portal started a session with no stream")))?;
    let restore = results
        .get("restore_token")
        .and_then(|value| String::try_from(&**value).ok());
    let body = (session, HashMap::<&str, Value<'_>>::new());
    let remote = before(
        deadline,
        screencast(connection, "OpenPipeWireRemote", &body),
    )?
    .ok_or_else(|| PortalError(String::from("the portal sent no PipeWire remote in time")))
    .and_then(|reply| {
        let remote = reply.body().deserialize::<zvariant::OwnedFd>();
        remote.map_err(PortalError::from)
    })?;
    Ok(Started::Stream(WindowStream {
        node,
        restore,
        remote: remote.into(),
    }))
}

impl Handles {
    /// The handle and token of this session's request for `step`.
    fn request(&self, step: &str) -> (String, String) {
        let token = format!("{}_{step}", self.token);
        (format!("{PATH}/request/{}/{token}", self.base), token)
    }
}

/// The call of `method` on the portal's `ScreenCast` interface with `body`, not yet sent.
fn screencast<'a, B>(connection: &'a Connection, method: &'a str, body: &'a B) -> Pending<'a>
where
    B: zbus::export::serde::Serialize + zvariant::DynamicType,
{
    Box::pin(connection.inner().call_method(
        Some(DESTINATION),
        PATH,
        Some(SCREENCAST),
        method,
        body,
    ))
}

/// Waits until `deadline` for the `Response` on `handle` that the portal sends.
fn wait(
    connection: &Connection,
    handle: &str,
    deadline: Instant,
    reply: Pending<'_>,
) -> Result<Answer, PortalError> {
    let limit = deadline.saturating_duration_since(Instant::now());
    answered(connection, handle, limit, reply)
}

/// Refuses a response code other than 0 to a call before `Start`.
fn succeeded(method: &str, code: u32) -> Result<(), PortalError> {
    if code == 0 {
        Ok(())
    } else {
        Err(PortalError(format!(
            "the portal answered {method} with response {code}"
        )))
    }
}

/// The node of the first stream a `Start` response lists, or `None` when it lists none.
fn first_node(results: &Results) -> Option<u32> {
    results
        .get("streams")
        .and_then(|value| value.try_clone().ok())
        .and_then(|value| Streams::try_from(value).ok())
        .and_then(|streams| streams.first().map(|(node, _)| *node))
}
