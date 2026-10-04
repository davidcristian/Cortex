//! The `Request` and `Response` exchange every desktop portal call makes, over `zbus`.

use std::collections::HashMap;
use std::pin::Pin;
use std::time::{Duration, Instant};

use async_io::Timer;
use futures_lite::{StreamExt, future};
use zbus::blocking::{Connection, MessageIterator};
use zbus::message::{Flags, Type};
use zbus::zvariant::{OwnedObjectPath, OwnedValue};
use zbus::{MatchRule, Message};

use crate::portal::PortalError;

pub const DESTINATION: &str = "org.freedesktop.portal.Desktop";
pub const PATH: &str = "/org/freedesktop/portal/desktop";
const REQUEST: &str = "org.freedesktop.portal.Request";

/// The results a portal sends beside the response code.
pub type Results = HashMap<String, OwnedValue>;

/// A portal method call, or a wait for a message, that has not started yet.
pub type Pending<'a> = Pin<Box<dyn Future<Output = zbus::Result<Message>> + 'a>>;

/// Subscribes to `Response` on `handle`, sends `call`, and waits at most `limit` in all for the
/// method reply and then the response.
pub fn request(
    connection: &Connection,
    handle: &str,
    limit: Duration,
    call: Pending<'_>,
) -> Result<(u32, Results), PortalError> {
    let deadline = Instant::now() + limit;
    // The portal may answer before its method reply arrives, so the match comes first.
    let mut responses = MatchRule::builder()
        .msg_type(Type::Signal)
        .interface(REQUEST)
        .and_then(|rule| rule.member("Response"))
        .and_then(|rule| rule.path(handle))
        .and_then(|rule| MessageIterator::for_match_rule(rule.build(), connection, None))
        .map(MessageIterator::into_inner)
        .map_err(PortalError::from)?;
    let Some(reply) = before(deadline, call)? else {
        return Err(expired(connection, handle, "method reply", limit));
    };
    let returned: OwnedObjectPath = reply.body().deserialize().map_err(PortalError::from)?;
    if returned.as_str() != handle {
        return Err(PortalError(format!(
            "the portal answered on {returned}, not on {handle}"
        )));
    }
    let closed = zbus::Error::Failure(String::from("the bus closed before the response"));
    let answered = Box::pin(async { responses.next().await.unwrap_or(Err(closed)) });
    let Some(message) = before(deadline, answered)? else {
        return Err(expired(connection, handle, "response", limit));
    };
    message.body().deserialize().map_err(PortalError::from)
}

/// Runs `work` until `deadline`, or returns `None` when the deadline comes first.
fn before(deadline: Instant, work: Pending<'_>) -> Result<Option<Message>, PortalError> {
    let done = async { work.await.map(Some) };
    let expired = async {
        Timer::at(deadline).await;
        Ok(None)
    };
    async_io::block_on(future::or(done, expired)).map_err(PortalError::from)
}

/// Closes the request on `handle` and names the message that did not arrive within `limit`.
fn expired(connection: &Connection, handle: &str, missing: &str, limit: Duration) -> PortalError {
    close(connection, handle);
    PortalError(format!(
        "the portal sent no {missing} on {handle} within {limit:?}"
    ))
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

impl From<zbus::Error> for PortalError {
    fn from(error: zbus::Error) -> Self {
        Self(error.to_string())
    }
}
