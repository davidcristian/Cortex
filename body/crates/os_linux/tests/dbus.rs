#![cfg(target_os = "linux")]

use std::collections::HashMap;
use std::os::unix::net::UnixStream;
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;

use body_core::{Notification, Notify, NotifyError};
use os_linux::zbus::blocking::Connection;
use os_linux::zbus::blocking::connection::Builder;
use os_linux::zbus::zvariant::OwnedValue;
use os_linux::zbus::{Guid, fdo, interface};
use os_linux::{BusMessage, DbusNotifications, LinuxNotify, NotificationBus};

const PATH: &str = "/org/freedesktop/Notifications";

/// Every argument of one `Notify` call the fake server received.
#[derive(Clone, Debug, PartialEq)]
struct Received {
    app_name: String,
    replaces_id: u32,
    app_icon: String,
    summary: String,
    body: String,
    actions: Vec<String>,
    hints: usize,
    expire_timeout: i32,
}

/// A fake `org.freedesktop.Notifications` server, answering or failing each call as scripted.
struct FakeServer {
    capabilities: Option<Vec<String>>,
    fail_notify: bool,
    received: Arc<Mutex<Vec<Received>>>,
}

#[interface(name = "org.freedesktop.Notifications")]
impl FakeServer {
    fn get_capabilities(&self) -> fdo::Result<Vec<String>> {
        self.capabilities
            .clone()
            .ok_or_else(|| fdo::Error::ServiceUnknown(String::from("no notification server")))
    }

    #[allow(clippy::too_many_arguments, clippy::needless_pass_by_value)]
    fn notify(
        &self,
        app_name: String,
        replaces_id: u32,
        app_icon: String,
        summary: String,
        body: String,
        actions: Vec<String>,
        hints: HashMap<String, OwnedValue>,
        expire_timeout: i32,
    ) -> fdo::Result<u32> {
        if self.fail_notify {
            return Err(fdo::Error::Failed(String::from("the server refused")));
        }
        self.received
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(Received {
                app_name,
                replaces_id,
                app_icon,
                summary,
                body,
                actions,
                hints: hints.len(),
                expire_timeout,
            });
        Ok(42)
    }
}

/// A server whose replies have the wrong type, so the client cannot read them.
struct WrongReplyServer;

#[interface(name = "org.freedesktop.Notifications")]
impl WrongReplyServer {
    #[allow(clippy::unused_self)]
    fn get_capabilities(&self) -> u32 {
        1
    }

    #[allow(
        unused_variables,
        clippy::too_many_arguments,
        clippy::needless_pass_by_value,
        clippy::unused_self
    )]
    fn notify(
        &self,
        app_name: String,
        replaces_id: u32,
        app_icon: String,
        summary: String,
        body: String,
        actions: Vec<String>,
        hints: HashMap<String, OwnedValue>,
        expire_timeout: i32,
    ) -> String {
        String::from("not an id")
    }
}

/// Connects a client to `server` over a socket pair, with no bus daemon between them.
fn peer<I: os_linux::zbus::object_server::Interface>(server: I) -> (Connection, Connection) {
    let (client_end, server_end) =
        UnixStream::pair().unwrap_or_else(|error| panic!("no socket pair: {error}"));
    let serving = thread::spawn(move || {
        Builder::async_io_unix_stream(server_end)
            .server(Guid::generate())
            .and_then(|builder| builder.p2p().serve_at(PATH, server))
            .and_then(Builder::build)
    });
    let client = Builder::async_io_unix_stream(client_end)
        .p2p()
        .build()
        .unwrap_or_else(|error| panic!("the client did not connect: {error}"));
    let server = serving
        .join()
        .unwrap_or_else(|_| panic!("the server thread panicked"))
        .unwrap_or_else(|error| panic!("the server did not start: {error}"));
    (client, server)
}

fn fake(
    capabilities: Option<&[&str]>,
    fail_notify: bool,
) -> (FakeServer, Arc<Mutex<Vec<Received>>>) {
    let received = Arc::new(Mutex::new(Vec::new()));
    let server = FakeServer {
        capabilities: capabilities
            .map(|names| names.iter().map(|name| String::from(*name)).collect()),
        fail_notify,
        received: Arc::clone(&received),
    };
    (server, received)
}

#[test]
fn capabilities_are_read_from_the_server() {
    let (server, _) = fake(Some(&["body", "body-markup"]), false);
    let (client, _server) = peer(server);

    let capabilities = DbusNotifications::new(client).capabilities();

    assert_eq!(
        capabilities,
        Ok(vec![String::from("body"), String::from("body-markup")])
    );
}

#[test]
fn a_notification_reaches_the_server_with_every_argument() {
    let (server, received) = fake(Some(&["body"]), false);
    let (client, _server) = peer(server);
    let message = BusMessage {
        app_name: String::from("Cortex"),
        summary: String::from("Stand up"),
        body: String::from("Walk"),
    };

    let id = DbusNotifications::new(client).notify(&message);

    assert_eq!(id, Ok(42));
    assert_eq!(
        *received.lock().unwrap(),
        vec![Received {
            app_name: String::from("Cortex"),
            replaces_id: 0,
            app_icon: String::new(),
            summary: String::from("Stand up"),
            body: String::from("Walk"),
            actions: Vec::new(),
            hints: 0,
            expire_timeout: -1,
        }]
    );
}

#[test]
fn the_backend_shows_through_the_bus_end_to_end() {
    let (server, received) = fake(Some(&["body-markup"]), false);
    let (client, _server) = peer(server);
    let notify = LinuxNotify::new("Cortex", DbusNotifications::new(client));

    let shown = notify.show(&Notification::new("t", "a<b", "r1", true));

    assert_eq!(shown, Ok(true));
    let body = received.lock().unwrap()[0].body.clone();
    assert_eq!(body, "a&lt;b\nfrom an untrusted source");
}

#[test]
fn a_service_unknown_reply_is_unavailable() {
    let (server, _) = fake(None, false);
    let (client, _server) = peer(server);
    let notify = LinuxNotify::new("Cortex", DbusNotifications::new(client));

    let result = notify.show(&Notification::new("t", "b", "r1", false));

    let Err(NotifyError::Unavailable(message)) = result else {
        panic!("expected Unavailable, got {result:?}");
    };
    assert!(message.contains("no notification server"), "{message}");
}

#[test]
fn a_refused_notify_names_its_error() {
    let (server, received) = fake(Some(&[]), true);
    let (client, _server) = peer(server);

    let error = DbusNotifications::new(client)
        .notify(&BusMessage {
            app_name: String::from("Cortex"),
            summary: String::from("t"),
            body: String::from("b"),
        })
        .unwrap_err();

    assert_eq!(
        error.name.as_deref(),
        Some("org.freedesktop.DBus.Error.Failed")
    );
    assert!(
        error.message.contains("the server refused"),
        "{}",
        error.message
    );
    assert!(received.lock().unwrap().is_empty());
}

#[test]
fn a_reply_of_the_wrong_type_is_an_unnamed_failure() {
    let (client, _server) = peer(WrongReplyServer);

    let error = DbusNotifications::new(client).capabilities().unwrap_err();

    assert_eq!(error.name, None);
    assert!(!error.message.is_empty());
}

#[test]
fn a_notify_reply_of_the_wrong_type_is_an_unnamed_failure() {
    let (client, _server) = peer(WrongReplyServer);

    let error = DbusNotifications::new(client)
        .notify(&BusMessage {
            app_name: String::from("Cortex"),
            summary: String::from("t"),
            body: String::from("b"),
        })
        .unwrap_err();

    assert_eq!(error.name, None);
    assert!(!error.message.is_empty());
}
