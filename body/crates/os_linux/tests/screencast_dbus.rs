#![cfg(target_os = "linux")]

use std::collections::HashMap;
use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use os_linux::zbus::blocking::Connection;
use os_linux::zbus::blocking::connection::Builder;
use os_linux::zbus::message::Header;
use os_linux::zbus::names::BusName;
use os_linux::zbus::zvariant::{self, OwnedObjectPath, OwnedValue, Value};
use os_linux::zbus::{Guid, Message, fdo, interface};
use os_linux::{CastSession, DbusScreenCast, ScreenCastPortal, Started, offers_window};

const PATH: &str = "/org/freedesktop/portal/desktop";
const SENDER: &str = ":1.16";
/// The unique name of the fake portal, which signs every signal it sends.
const PORTAL: &str = ":1.7";
const REQUEST: &str = "org.freedesktop.portal.Request";
const SESSION: &str = "/org/freedesktop/portal/desktop/session/1_16/cortexcast1";
/// The limit every exchange that is answered runs under: far above a socket-pair round trip.
const LIMIT: Duration = Duration::from_secs(3);
/// The limit a test that expects no answer waits.
const SHORT: Duration = Duration::from_millis(100);

fn ok<T, E: std::fmt::Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("a setup step failed: {error:?}"))
}

/// The call a fake portal answers in another way than with success.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Step {
    Sources,
    Create,
    Select,
    Start,
    Remote,
}

/// How a fake portal answers that call.
#[derive(Clone, Copy, Debug)]
enum Fault {
    Code(u32),
    /// A request's method reply with no `Response`, or no reply at all to a plain call.
    Silent,
    Refuse,
    Late(Duration),
    NoStream,
}

type Calls = Arc<Mutex<Vec<Vec<String>>>>;

/// A fake portal frontend that answers each request with a `Response` before its method reply.
struct FakeCast {
    faults: Vec<(Step, Fault)>,
    calls: Calls,
    peers: Arc<Mutex<Vec<UnixStream>>>,
}

fn record(calls: &Calls, values: Vec<String>) {
    calls
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .push(values);
}

fn listed(calls: &Calls) -> Vec<Vec<String>> {
    calls.lock().unwrap_or_else(PoisonError::into_inner).clone()
}

/// Each option as `key=value`, sorted by key.
fn options(options: &HashMap<String, OwnedValue>) -> Vec<String> {
    let mut texts: Vec<String> = options
        .iter()
        .map(|(key, value)| format!("{key}={}", Value::from(ok(value.try_clone()))))
        .collect();
    texts.sort();
    texts
}

impl FakeCast {
    fn fault(&self, step: Step) -> Option<Fault> {
        let mut faults = self.faults.iter();
        faults.find(|(at, _)| *at == step).map(|(_, fault)| *fault)
    }

    async fn respond(
        &self,
        step: Step,
        connection: &os_linux::zbus::Connection,
        options: &HashMap<String, OwnedValue>,
        results: HashMap<&str, Value<'_>>,
    ) -> fdo::Result<OwnedObjectPath> {
        let token = options
            .get("handle_token")
            .and_then(|value| String::try_from(&**value).ok())
            .unwrap_or_default();
        let handle = format!("{PATH}/request/1_16/{token}");
        let code = match self.fault(step) {
            Some(Fault::Refuse) => {
                return Err(fdo::Error::AccessDenied(String::from("not allowed")));
            }
            Some(Fault::Silent) => return Ok(ok(OwnedObjectPath::try_from(handle))),
            Some(Fault::Late(delay)) => {
                async_io::Timer::after(delay).await;
                0
            }
            Some(Fault::Code(code)) => code,
            _ => 0,
        };
        let failed = |error: os_linux::zbus::Error| fdo::Error::Failed(error.to_string());
        if step == Step::Start {
            // Any process on the bus can send a `Response` on the handle; the adapter reads only the
            // portal's.
            let forged = Message::signal(handle.as_str(), REQUEST, "Response")
                .and_then(|builder| builder.sender(":1.99"))
                .and_then(|builder| builder.build(&(0_u32, stream(99, "forged"))))
                .map_err(failed)?;
            connection.send(&forged).await.map_err(failed)?;
        }
        connection
            .emit_signal(
                None::<BusName<'_>>,
                handle.as_str(),
                REQUEST,
                "Response",
                &(code, results),
            )
            .await
            .map_err(failed)?;
        Ok(ok(OwnedObjectPath::try_from(handle)))
    }
}

fn stream(node: u32, restore: &str) -> HashMap<&str, Value<'_>> {
    let streams = vec![(node, HashMap::from([("source_type", Value::from(2_u32))]))];
    HashMap::from([
        ("streams", Value::from(streams)),
        ("restore_token", Value::from(restore)),
    ])
}

#[interface(name = "org.freedesktop.portal.ScreenCast")]
impl FakeCast {
    #[zbus(property)]
    async fn available_source_types(&self) -> fdo::Result<u32> {
        match self.fault(Step::Sources) {
            Some(Fault::Refuse) => Err(fdo::Error::AccessDenied(String::from("not allowed"))),
            Some(Fault::Silent) => Ok(std::future::pending().await),
            _ => Ok(3),
        }
    }

    async fn create_session(
        &self,
        options: HashMap<String, OwnedValue>,
        #[zbus(connection)] connection: &os_linux::zbus::Connection,
    ) -> fdo::Result<OwnedObjectPath> {
        let mut values = vec![String::from("CreateSession")];
        values.extend(self::options(&options));
        record(&self.calls, values);
        let results = HashMap::from([("session_handle", Value::from(SESSION))]);
        self.respond(Step::Create, connection, &options, results)
            .await
    }

    async fn select_sources(
        &self,
        session_handle: OwnedObjectPath,
        options: HashMap<String, OwnedValue>,
        #[zbus(connection)] connection: &os_linux::zbus::Connection,
    ) -> fdo::Result<OwnedObjectPath> {
        let mut values = vec![String::from("SelectSources"), session_handle.to_string()];
        values.extend(self::options(&options));
        record(&self.calls, values);
        self.respond(Step::Select, connection, &options, HashMap::new())
            .await
    }

    async fn start(
        &self,
        session_handle: OwnedObjectPath,
        parent_window: String,
        options: HashMap<String, OwnedValue>,
        #[zbus(connection)] connection: &os_linux::zbus::Connection,
    ) -> fdo::Result<OwnedObjectPath> {
        let mut values = vec![
            String::from("Start"),
            session_handle.to_string(),
            parent_window,
        ];
        values.extend(self::options(&options));
        record(&self.calls, values);
        let results = match self.fault(Step::Start) {
            Some(Fault::NoStream) => HashMap::from([("streams", Value::from(7_u32))]),
            _ => stream(42, "kept"),
        };
        self.respond(Step::Start, connection, &options, results)
            .await
    }

    async fn open_pipe_wire_remote(
        &self,
        session_handle: OwnedObjectPath,
        options: HashMap<String, OwnedValue>,
    ) -> fdo::Result<zvariant::OwnedFd> {
        let mut values = vec![
            String::from("OpenPipeWireRemote"),
            session_handle.to_string(),
        ];
        values.extend(self::options(&options));
        record(&self.calls, values);
        match self.fault(Step::Remote) {
            Some(Fault::Refuse) => Err(fdo::Error::AccessDenied(String::from("not allowed"))),
            Some(Fault::Silent) => Ok(std::future::pending().await),
            _ => {
                let (ours, theirs) =
                    UnixStream::pair().map_err(|error| fdo::Error::Failed(error.to_string()))?;
                self.peers
                    .lock()
                    .unwrap_or_else(PoisonError::into_inner)
                    .push(ours);
                Ok(zvariant::OwnedFd::from(std::os::fd::OwnedFd::from(theirs)))
            }
        }
    }
}

/// A portal session object that writes down the path of every `Close` call it is sent.
struct FakeSession {
    calls: Calls,
}

#[interface(name = "org.freedesktop.portal.Session")]
impl FakeSession {
    #[allow(clippy::needless_pass_by_value)]
    fn close(&self, #[zbus(header)] header: Header<'_>) {
        let path = header.path().map(ToString::to_string).unwrap_or_default();
        record(&self.calls, vec![String::from("Close"), path]);
    }
}

struct Fake {
    client: Connection,
    _server: Connection,
    calls: Calls,
    peers: Arc<Mutex<Vec<UnixStream>>>,
}

fn serve(faults: Vec<(Step, Fault)>, name: Option<&str>) -> Fake {
    let calls = Arc::new(Mutex::new(Vec::new()));
    let peers = Arc::new(Mutex::new(Vec::new()));
    let cast = FakeCast {
        faults,
        calls: Arc::clone(&calls),
        peers: Arc::clone(&peers),
    };
    let session = FakeSession {
        calls: Arc::clone(&calls),
    };
    let (client_end, server_end) = ok(UnixStream::pair());
    let serving = thread::spawn(move || {
        Builder::async_io_unix_stream(server_end)
            .server(Guid::generate())
            .and_then(|builder| builder.p2p().serve_at(PATH, cast))
            .and_then(|builder| builder.serve_at(SESSION, session))
            .and_then(Builder::build)
    });
    let client = ok(Builder::async_io_unix_stream(client_end).p2p().build());
    if let Some(name) = name {
        ok(client.inner().set_unique_name(name));
    }
    let server = ok(ok(serving.join()));
    ok(server.inner().set_unique_name(PORTAL));
    Fake {
        client,
        _server: server,
        calls,
        peers,
    }
}

fn working(fault: Option<(Step, Fault)>) -> (DbusScreenCast, Fake) {
    let fake = serve(fault.into_iter().collect(), Some(SENDER));
    (DbusScreenCast::with_limit(fake.client.clone(), SHORT), fake)
}

/// Waits up to [`LIMIT`] for `done` to hold, since a `Close` is sent with no reply to wait for.
fn eventually(done: impl Fn() -> bool) -> bool {
    let started = Instant::now();
    while started.elapsed() < LIMIT && !done() {
        thread::sleep(Duration::from_millis(5));
    }
    done()
}

fn closes(calls: &Calls) -> usize {
    listed(calls)
        .iter()
        .filter(|call| call[0] == "Close")
        .count()
}

fn strings(values: &[&str]) -> Vec<String> {
    values.iter().map(ToString::to_string).collect()
}

#[test]
fn the_source_types_are_read_from_the_property() {
    let (portal, _fake) = working(None);

    assert_eq!(portal.source_types(), Ok(3));
    assert_eq!(offers_window(&portal), Ok(true));
}

#[test]
fn a_refused_or_unanswered_property_read_fails() {
    let (refused, _fake) = working(Some((Step::Sources, Fault::Refuse)));
    let (silent, _other) = working(Some((Step::Sources, Fault::Silent)));
    let started = Instant::now();

    let errors = [refused.source_types(), silent.source_types()].map(Result::unwrap_err);

    assert!(started.elapsed() < LIMIT, "{:?}", started.elapsed());
    assert!(errors[0].0.contains("not allowed"), "{errors:?}");
    assert!(
        errors[1].0.contains("no source types within 100ms"),
        "{errors:?}"
    );
}

#[test]
fn a_restored_session_selects_one_window_and_gives_its_node_token_and_remote() {
    let (portal, fake) = working(None);

    let CastSession { handle, started } = ok(portal.start(Some("given"), LIMIT));

    assert_eq!(handle, SESSION);
    let Started::Stream(stream) = started else {
        panic!("no stream: {started:?}");
    };
    assert_eq!((stream.node, stream.restore.as_deref()), (42, Some("kept")));
    let request = |step: &str| format!("handle_token=\"cortexcast1_{step}\"");
    let calls = vec![
        vec![
            String::from("CreateSession"),
            request("create"),
            String::from("session_handle_token=\"cortexcast1\""),
        ],
        strings(&[
            "SelectSources",
            SESSION,
            "cursor_mode=uint32 1",
            &request("select"),
            "multiple=false",
            "persist_mode=uint32 1",
            "restore_token=\"given\"",
            "types=uint32 2",
        ]),
        strings(&["Start", SESSION, "", &request("start")]),
        strings(&["OpenPipeWireRemote", SESSION]),
    ];
    assert_eq!(listed(&fake.calls), calls);
    let mut ours = ok(fake.peers.lock()).remove(0);
    ok(ours.write_all(b"frame"));
    let mut read = [0_u8; 5];
    ok(UnixStream::from(stream.remote).read_exact(&mut read));
    assert_eq!(&read, b"frame");
}

#[test]
fn a_session_with_no_token_sends_none_and_each_session_has_its_own_tokens() {
    let (portal, fake) = working(None);

    let first = portal.start(None, LIMIT);
    let second = portal.start(None, LIMIT);

    assert!(first.is_ok() && second.is_ok(), "{first:?} {second:?}");
    let calls = listed(&fake.calls);
    assert!(
        !calls[1]
            .iter()
            .any(|value| value.starts_with("restore_token"))
    );
    assert_eq!(calls[4][1], "handle_token=\"cortexcast2_create\"");
    assert_eq!(calls[4][2], "session_handle_token=\"cortexcast2\"");
}

#[test]
fn a_refused_or_unanswered_start_is_returned_and_its_session_left_to_the_caller() {
    for (fault, ended) in [(Fault::Code(1), "Refused(1)"), (Fault::Silent, "Expired")] {
        let (portal, fake) = working(Some((Step::Start, fault)));

        let session = ok(portal.start(None, SHORT));

        assert_eq!(session.handle, SESSION);
        assert_eq!(format!("{:?}", session.started), ended);
        thread::sleep(SHORT);
        assert_eq!(closes(&fake.calls), 0);
    }
}

#[test]
fn a_failure_before_the_remote_is_open_closes_the_session() {
    let cases = [
        (
            Step::Create,
            Fault::Code(2),
            "answered CreateSession with response 2",
        ),
        (Step::Create, Fault::Silent, "no response on"),
        (Step::Create, Fault::Refuse, "not allowed"),
        (Step::Select, Fault::Silent, "no response on"),
        (
            Step::Select,
            Fault::Code(1),
            "answered SelectSources with response 1",
        ),
        (Step::Select, Fault::Refuse, "not allowed"),
        (Step::Start, Fault::Refuse, "not allowed"),
        (Step::Start, Fault::NoStream, "a session with no stream"),
        (Step::Remote, Fault::Refuse, "not allowed"),
        (Step::Remote, Fault::Silent, "no PipeWire remote in time"),
    ];
    for (step, fault, message) in cases {
        let (portal, fake) = working(Some((step, fault)));

        let error = portal.start(None, Duration::from_millis(300)).unwrap_err();

        assert!(error.0.contains(message), "{step:?} {fault:?}: {error:?}");
        let closed = vec![String::from("Close"), String::from(SESSION)];
        assert!(eventually(|| listed(&fake.calls).contains(&closed)));
        assert_eq!(closes(&fake.calls), 1);
    }
}

#[test]
fn one_limit_bounds_every_call_of_a_session_together() {
    let (limit, delay) = (Duration::from_millis(800), Duration::from_millis(500));
    let faults = vec![
        (Step::Create, Fault::Late(delay)),
        (Step::Start, Fault::Silent),
    ];
    let fake = serve(faults, Some(SENDER));
    let portal = DbusScreenCast::new(fake.client.clone());
    let started = Instant::now();

    let session = ok(portal.start(None, limit));

    let waited = started.elapsed();
    assert!(matches!(session.started, Started::Expired), "{session:?}");
    assert!(waited >= limit && waited < limit + delay / 2, "{waited:?}");
}

#[test]
fn a_nameless_connection_fails_before_any_call() {
    let cases = [
        (None, "no unique bus name"),
        (Some(":1-6.16"), "Invalid object path"),
    ];
    for (name, message) in cases {
        let fake = serve(Vec::new(), name);
        let portal = DbusScreenCast::new(fake.client.clone());

        let error = portal.start(None, LIMIT).unwrap_err();

        assert!(error.0.contains(message), "{error:?}");
        assert_eq!(listed(&fake.calls), Vec::<Vec<String>>::new());
    }
}

#[test]
fn close_sends_close_on_the_session() {
    let (portal, fake) = working(None);

    portal.close(SESSION);

    let closed = vec![String::from("Close"), String::from(SESSION)];
    assert!(eventually(|| listed(&fake.calls) == vec![closed.clone()]));
}

#[test]
fn a_bus_that_did_not_open_fails_every_call_with_its_text() {
    let portal = DbusScreenCast::absent(&os_linux::zbus::Error::Failure(String::from("no bus")));

    portal.close(SESSION);
    let errors = [
        portal.source_types().unwrap_err(),
        portal.start(None, LIMIT).unwrap_err(),
    ];

    for error in errors {
        assert!(error.0.contains("no bus"), "{error:?}");
    }
}
