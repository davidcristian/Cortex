#![cfg(target_os = "linux")]

use std::collections::HashMap;
use std::os::unix::net::UnixStream;
use std::sync::mpsc;
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::Duration;

use body_core::{Hotkey, HotkeyChord};
use os_linux::zbus::blocking::Connection;
use os_linux::zbus::blocking::connection::Builder;
use os_linux::zbus::names::BusName;
use os_linux::zbus::zvariant::{ObjectPath, OwnedObjectPath, OwnedValue, Value};
use os_linux::zbus::{Guid, fdo, interface};
use os_linux::{
    Activation, DbusShortcuts, LinuxPortalHotkey, Shortcut, ShortcutsPortal, ShortcutsReply,
};

const PATH: &str = "/org/freedesktop/portal/desktop";
const SENDER: &str = ":1.16";
const SHORTCUTS: &str = "org.freedesktop.portal.GlobalShortcuts";
const SESSION: &str = "/org/freedesktop/portal/desktop/session/1_16/cortex1";
/// The limit every exchange runs under: far above a socket-pair round trip.
const LIMIT: Duration = Duration::from_secs(3);

fn ok<T, E: std::fmt::Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("a setup step failed: {error:?}"))
}

/// How a fake portal writes the session handle in its `CreateSession` response.
#[derive(Clone, Copy)]
enum Session {
    Text,
    Path,
    Number,
}

/// The arguments of each call, as text: the method, then each value in the order sent.
type Received = Arc<Mutex<Vec<Vec<String>>>>;

/// A fake portal frontend that emits its `Response` before its method reply.
struct FakeShortcuts {
    session: Session,
    malformed: bool,
    refuse: bool,
    received: Received,
}

fn option(options: &HashMap<String, OwnedValue>, key: &str) -> String {
    options
        .get(key)
        .and_then(|value| String::try_from(&**value).ok())
        .unwrap_or_default()
}

impl FakeShortcuts {
    async fn respond(
        &self,
        connection: &os_linux::zbus::Connection,
        token: &str,
        results: HashMap<&str, Value<'_>>,
    ) -> fdo::Result<OwnedObjectPath> {
        if self.refuse {
            return Err(fdo::Error::AccessDenied(String::from("not allowed")));
        }
        let handle = format!("{PATH}/request/1_16/{token}");
        connection
            .emit_signal(
                None::<BusName<'_>>,
                handle.as_str(),
                "org.freedesktop.portal.Request",
                "Response",
                &(0_u32, results),
            )
            .await
            .map_err(|error| fdo::Error::Failed(error.to_string()))?;
        Ok(ok(OwnedObjectPath::try_from(handle)))
    }

    fn record(&self, values: Vec<String>) {
        self.received
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(values);
    }
}

#[interface(name = "org.freedesktop.portal.GlobalShortcuts")]
impl FakeShortcuts {
    async fn create_session(
        &self,
        options: HashMap<String, OwnedValue>,
        #[zbus(connection)] connection: &os_linux::zbus::Connection,
    ) -> fdo::Result<OwnedObjectPath> {
        let token = option(&options, "handle_token");
        let session = option(&options, "session_handle_token");
        self.record(vec![String::from("create"), token.clone(), session.clone()]);
        let handle = format!("{PATH}/session/1_16/{session}");
        let value = match self.session {
            Session::Text => Value::from(handle),
            // A malformed handle goes back as text, so a test fails rather than hanging the call.
            Session::Path => {
                ObjectPath::try_from(handle.clone()).map_or(Value::from(handle), Value::from)
            }
            Session::Number => Value::from(5_u32),
        };
        let results = HashMap::from([("session_handle", value)]);
        self.respond(connection, &token, results).await
    }

    async fn bind_shortcuts(
        &self,
        session_handle: OwnedObjectPath,
        shortcuts: Vec<(String, HashMap<String, OwnedValue>)>,
        parent_window: String,
        options: HashMap<String, OwnedValue>,
        #[zbus(connection)] connection: &os_linux::zbus::Connection,
    ) -> fdo::Result<OwnedObjectPath> {
        let token = option(&options, "handle_token");
        let mut values = vec![String::from("bind"), session_handle.to_string()];
        for (id, details) in &shortcuts {
            values.push(id.clone());
            values.push(option(details, "description"));
            values.push(option(details, "preferred_trigger"));
        }
        values.extend([parent_window, token.clone()]);
        self.record(values);
        let listed = if self.malformed {
            Value::from(vec![String::from("ctrl+alt+space")])
        } else {
            let ids = shortcuts.into_iter().map(|(id, _)| {
                let trigger = Value::from("Ctrl+Alt+Space");
                (id, HashMap::from([("trigger_description", trigger)]))
            });
            Value::from(ids.collect::<Vec<_>>())
        };
        let results = HashMap::from([("shortcuts", listed)]);
        self.respond(connection, &token, results).await
    }
}

fn fake(session: Session, malformed: bool, refuse: bool) -> (Connection, Connection, Received) {
    named(session, malformed, refuse, Some(SENDER))
}

fn named(
    session: Session,
    malformed: bool,
    refuse: bool,
    name: Option<&str>,
) -> (Connection, Connection, Received) {
    let received = Arc::new(Mutex::new(Vec::new()));
    let server = FakeShortcuts {
        session,
        malformed,
        refuse,
        received: Arc::clone(&received),
    };
    let (client_end, server_end) = ok(UnixStream::pair());
    let serving = thread::spawn(move || {
        Builder::async_io_unix_stream(server_end)
            .server(Guid::generate())
            .and_then(|builder| builder.p2p().serve_at(PATH, server))
            .and_then(Builder::build)
    });
    let client = ok(Builder::async_io_unix_stream(client_end).p2p().build());
    if let Some(name) = name {
        ok(client.inner().set_unique_name(name));
    }
    (client, ok(ok(serving.join())), received)
}

fn working() -> (DbusShortcuts, Connection, Received) {
    let (client, server, received) = fake(Session::Text, false, false);
    (DbusShortcuts::with_limit(client, LIMIT), server, received)
}

fn request(token: &str) -> String {
    format!("{PATH}/request/1_16/{token}")
}

fn shortcut() -> Shortcut {
    Shortcut {
        id: String::from("ctrl+alt+space"),
        description: String::from("Show or hide the overlay"),
        trigger: String::from("CTRL+ALT+space"),
    }
}

fn received(record: &Received) -> Vec<Vec<String>> {
    record
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone()
}

fn emit(server: &Connection, member: &str, id: &str) {
    let session = ok(ObjectPath::try_from(SESSION));
    let options = HashMap::<&str, Value<'_>>::new();
    let body = (session, id, 7_u64, options);
    ok(server.emit_signal(None::<BusName<'_>>, PATH, SHORTCUTS, member, &body));
}

fn activated(server: &Connection, id: &str) {
    emit(server, "Activated", id);
}

fn deactivated(server: &Connection, id: &str) {
    emit(server, "Deactivated", id);
}

fn signal(id: &str, active: bool) -> Activation {
    Activation {
        session: String::from(SESSION),
        shortcut: String::from(id),
        active,
    }
}

#[test]
fn the_sender_is_the_connection_unique_name() {
    let (portal, _server, _) = working();

    assert_eq!(portal.sender(), Ok(String::from(SENDER)));
}

#[test]
fn a_connection_with_no_unique_name_has_no_sender() {
    let (client, _server, _) = named(Session::Text, false, false, None);

    let error = DbusShortcuts::new(client).sender().unwrap_err();

    assert!(error.0.contains("no unique bus name"), "{error:?}");
}

#[test]
fn a_session_is_created_with_both_tokens_and_its_handle_read() {
    let (portal, _server, record) = working();

    let reply = portal.create_session(&request("cortex1"), "cortex1", "cortex1");

    let names = vec![String::from(SESSION)];
    assert_eq!(reply, Ok(ShortcutsReply { code: 0, names }));
    assert_eq!(
        received(&record),
        vec![vec!["create", "cortex1", "cortex1"]]
    );
}

#[test]
fn a_session_handle_sent_as_a_path_is_read_and_one_of_another_type_is_none() {
    for (session, names) in [
        (Session::Path, vec![String::from(SESSION)]),
        (Session::Number, vec![]),
    ] {
        let (client, _server, _) = fake(session, false, false);
        let portal = DbusShortcuts::new(client);

        let reply = portal.create_session(&request("cortex1"), "cortex1", "cortex1");

        assert_eq!(reply, Ok(ShortcutsReply { code: 0, names }));
    }
}

#[test]
fn a_bind_sends_the_session_and_one_shortcut_and_reads_the_ids_bound() {
    let (portal, _server, record) = working();

    let reply = portal.bind(SESSION, &request("cortex2"), "cortex2", &shortcut());

    let names = vec![String::from("ctrl+alt+space")];
    assert_eq!(reply, Ok(ShortcutsReply { code: 0, names }));
    let call = [
        "bind",
        SESSION,
        "ctrl+alt+space",
        "Show or hide the overlay",
        "CTRL+ALT+space",
        "",
        "cortex2",
    ];
    assert_eq!(received(&record), vec![call.to_vec()]);
}

#[test]
fn a_shortcut_list_of_another_type_binds_none() {
    let (client, _server, _) = fake(Session::Text, true, false);

    let reply = DbusShortcuts::with_limit(client, LIMIT).bind(
        SESSION,
        &request("cortex2"),
        "cortex2",
        &shortcut(),
    );

    assert_eq!(
        reply,
        Ok(ShortcutsReply {
            code: 0,
            names: vec![]
        })
    );
}

#[test]
fn a_session_that_is_not_an_object_path_fails_before_any_call() {
    let (portal, _server, record) = working();

    let reply = portal.bind("not a path", &request("cortex2"), "cortex2", &shortcut());

    assert!(reply.is_err());
    assert_eq!(received(&record), Vec::<Vec<String>>::new());
}

#[test]
fn a_refused_call_fails_with_the_portal_error() {
    let (client, _server, _) = fake(Session::Text, false, true);
    let portal = DbusShortcuts::with_limit(client, LIMIT);

    let created = portal.create_session(&request("cortex1"), "cortex1", "cortex1");
    let bound = portal.bind(SESSION, &request("cortex2"), "cortex2", &shortcut());

    for error in [created.unwrap_err(), bound.unwrap_err()] {
        assert!(error.0.contains("not allowed"), "{error:?}");
    }
}

#[test]
fn each_press_and_release_is_read_in_order_and_other_signals_are_skipped() {
    let (portal, server, _) = working();
    let wrong = ("not an activation",);
    let changed = (
        ok(ObjectPath::try_from(SESSION)),
        Vec::<(String, HashMap<String, Value<'_>>)>::new(),
    );

    ok(server.emit_signal(None::<BusName<'_>>, PATH, SHORTCUTS, "Activated", &wrong));
    ok(server.emit_signal(
        None::<BusName<'_>>,
        PATH,
        SHORTCUTS,
        "ShortcutsChanged",
        &changed,
    ));
    activated(&server, "ctrl+alt+space");
    deactivated(&server, "ctrl+alt+space");
    activated(&server, "super+a");

    assert!(portal.next_activation().is_err());
    assert_eq!(portal.next_activation(), Ok(signal("ctrl+alt+space", true)));
    assert_eq!(
        portal.next_activation(),
        Ok(signal("ctrl+alt+space", false))
    );
}

#[test]
fn a_closed_connection_ends_the_activations() {
    let (portal, server, _) = working();

    drop(server);

    let errors = [portal.next_activation(), portal.next_activation()].map(Result::unwrap_err);
    assert!(errors[0].0.contains("failed to read"), "{errors:?}");
    assert!(errors[1].0.contains("the bus closed"), "{errors:?}");
}

#[test]
fn a_bus_that_did_not_open_fails_every_call_with_its_text() {
    let portal = DbusShortcuts::absent(&os_linux::zbus::Error::Failure(String::from("no bus")));

    let errors = [
        portal.sender().unwrap_err(),
        portal.create_session(&request("t"), "t", "t").unwrap_err(),
        portal
            .bind(SESSION, &request("t"), "t", &shortcut())
            .unwrap_err(),
        portal.next_activation().unwrap_err(),
    ];

    for error in errors {
        assert!(error.0.contains("no bus"), "{error:?}");
    }
}

#[test]
fn the_hotkey_over_the_bus_runs_once_per_press_however_long_it_is_held() {
    let (portal, server, _) = working();
    let hour = Duration::from_hours(1);
    let hotkey = LinuxPortalHotkey::with_gap(portal, "Show or hide the overlay", hour);
    let (fired, on_fire) = mpsc::channel();
    let chord = ok(HotkeyChord::parse("ctrl+alt+space"));

    let registered = hotkey.register(
        &chord,
        Box::new(move || fired.send(()).unwrap_or_else(|error| panic!("{error:?}"))),
    );
    for presses in [3, 1, 1] {
        for _ in 0..presses {
            activated(&server, "ctrl+alt+space");
        }
        deactivated(&server, "ctrl+alt+space");
    }

    assert_eq!(registered, Ok(()));
    for _ in 0..3 {
        assert_eq!(on_fire.recv_timeout(LIMIT), Ok(()));
    }
    assert!(on_fire.recv_timeout(Duration::from_millis(200)).is_err());
}
