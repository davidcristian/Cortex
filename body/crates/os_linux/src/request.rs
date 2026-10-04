//! The `Request` and `Response` exchange every desktop portal call makes, over `zbus`.

use std::collections::HashMap;
use std::time::Duration;

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

/// Subscribes to `Response` on `handle`, runs `call`, and waits at most `limit` for the response.
pub fn request(
    connection: &Connection,
    handle: &str,
    limit: Duration,
    call: &dyn Fn() -> zbus::Result<Message>,
) -> Result<(u32, Results), PortalError> {
    // The portal may answer before its method reply arrives, so the match comes first.
    let mut responses = MatchRule::builder()
        .msg_type(Type::Signal)
        .interface(REQUEST)
        .and_then(|rule| rule.member("Response"))
        .and_then(|rule| rule.path(handle))
        .and_then(|rule| MessageIterator::for_match_rule(rule.build(), connection, None))
        .map(MessageIterator::into_inner)
        .map_err(PortalError::from)?;
    let returned: OwnedObjectPath = call()
        .and_then(|reply| reply.body().deserialize())
        .map_err(PortalError::from)?;
    if returned.as_str() != handle {
        return Err(PortalError(format!(
            "the portal answered on {returned}, not on {handle}"
        )));
    }
    let closed = zbus::Error::Failure(String::from("the bus closed before the response"));
    let answered = async { responses.next().await.unwrap_or(Err(closed)).map(Some) };
    let expired = async {
        Timer::after(limit).await;
        Ok(None)
    };
    let Some(message) =
        async_io::block_on(future::or(answered, expired)).map_err(PortalError::from)?
    else {
        close(connection, handle);
        return Err(PortalError(format!(
            "the portal sent no response on {handle} within {limit:?}"
        )));
    };
    message.body().deserialize().map_err(PortalError::from)
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
