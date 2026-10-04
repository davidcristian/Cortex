#![cfg(target_os = "linux")]

use std::collections::HashMap;
use std::fs;
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use body_core::{CaptureError, CaptureRequest, ScreenCapture};
use os_linux::zbus::blocking::Connection;
use os_linux::zbus::blocking::connection::Builder;
use os_linux::zbus::message::Header;
use os_linux::zbus::names::BusName;
use os_linux::zbus::zvariant::{OwnedObjectPath, OwnedValue, Value};
use os_linux::zbus::{Guid, fdo, interface};
use os_linux::{DbusPortal, LinuxPortalCapture, PortalReply, ScreenshotPortal, request_path};

const PATH: &str = "/org/freedesktop/portal/desktop";
const SENDER: &str = ":1.16";
const REQUEST: &str = "org.freedesktop.portal.Request";
/// The limit every exchange that is answered runs under: far above a socket-pair round trip.
const LIMIT: Duration = Duration::from_secs(3);
/// The limit a test that expects no answer waits.
const SHORT: Duration = Duration::from_millis(100);

/// The value of a setup step that cannot fail in a working test environment.
fn ok<T, E: std::fmt::Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("a setup step failed: {error:?}"))
}

/// The `uri` result a fake portal puts in its `Response`.
#[derive(Clone)]
enum Uri {
    Text(String),
    Number(u32),
}

/// How a fake portal answers a `Screenshot` call.
#[derive(Clone)]
enum Answer {
    Respond(u32, Option<Uri>),
    Silent,
    Elsewhere,
    WrongSignal,
    Refuse,
}

/// The arguments of one `Screenshot` call: the parent window and every option.
type Received = (String, HashMap<String, OwnedValue>);

/// A fake portal frontend that emits its `Response` before its method reply, as a fast one can.
/// It gives its answers in order and repeats the last one.
struct FakePortal {
    answers: Mutex<Vec<Answer>>,
    received: Arc<Mutex<Vec<Received>>>,
}

impl FakePortal {
    fn next_answer(&self) -> Answer {
        let mut answers = self.answers.lock().unwrap_or_else(PoisonError::into_inner);
        if answers.len() > 1 {
            answers.remove(0)
        } else {
            answers[0].clone()
        }
    }
}

#[interface(name = "org.freedesktop.portal.Screenshot")]
impl FakePortal {
    async fn screenshot(
        &self,
        parent_window: String,
        options: HashMap<String, OwnedValue>,
        #[zbus(connection)] connection: &os_linux::zbus::Connection,
    ) -> fdo::Result<OwnedObjectPath> {
        let token = options
            .get("handle_token")
            .and_then(|value| String::try_from(&**value).ok())
            .unwrap_or_default();
        self.received
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push((parent_window, options));
        let handle = format!("{PATH}/request/1_16/{token}");
        let mut results: HashMap<&str, Value<'_>> = HashMap::new();
        let code = match self.next_answer() {
            Answer::Refuse => return Err(fdo::Error::AccessDenied(String::from("not allowed"))),
            Answer::Silent => return Ok(path(&handle)),
            Answer::Elsewhere => return Ok(path(&format!("{PATH}/request/1_16/other"))),
            Answer::WrongSignal => None,
            Answer::Respond(code, uri) => {
                match uri {
                    Some(Uri::Text(text)) => results.insert("uri", Value::from(text)),
                    Some(Uri::Number(number)) => results.insert("uri", Value::from(number)),
                    None => None,
                };
                Some(code)
            }
        };
        let emitted = match code {
            Some(code) => {
                connection
                    .emit_signal(
                        None::<BusName<'_>>,
                        handle.as_str(),
                        REQUEST,
                        "Response",
                        &(code, results),
                    )
                    .await
            }
            None => {
                connection
                    .emit_signal(
                        None::<BusName<'_>>,
                        handle.as_str(),
                        REQUEST,
                        "Response",
                        &("not a response",),
                    )
                    .await
            }
        };
        emitted.map_err(|error| fdo::Error::Failed(error.to_string()))?;
        Ok(path(&handle))
    }
}

/// A portal request object that writes down the path of every `Close` call it is sent.
struct FakeRequest {
    closed: Arc<Mutex<Vec<String>>>,
}

#[interface(name = "org.freedesktop.portal.Request")]
impl FakeRequest {
    #[allow(clippy::needless_pass_by_value)]
    fn close(&self, #[zbus(header)] header: Header<'_>) {
        let path = header.path().map(ToString::to_string).unwrap_or_default();
        self.closed
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(path);
    }
}

fn path(text: &str) -> OwnedObjectPath {
    ok(OwnedObjectPath::try_from(text))
}

/// A portal whose method reply is a string rather than a request handle.
struct WrongReplyPortal;

#[interface(name = "org.freedesktop.portal.Screenshot")]
impl WrongReplyPortal {
    #[allow(clippy::unused_self, clippy::needless_pass_by_value, unused_variables)]
    fn screenshot(&self, parent_window: String, options: HashMap<String, OwnedValue>) -> String {
        String::from("not a handle")
    }
}

/// Connects a client named `name` to `server` over a socket pair, with no bus daemon between.
fn peer<I: os_linux::zbus::object_server::Interface>(
    server: I,
    name: Option<&str>,
) -> (Connection, Connection) {
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
    let server = ok(ok(serving.join()));
    (client, server)
}

fn fake(answer: Answer) -> (Connection, Connection, Arc<Mutex<Vec<Received>>>) {
    fake_in_order(vec![answer])
}

fn fake_in_order(answers: Vec<Answer>) -> (Connection, Connection, Arc<Mutex<Vec<Received>>>) {
    let received = Arc::new(Mutex::new(Vec::new()));
    let server = FakePortal {
        answers: Mutex::new(answers),
        received: Arc::clone(&received),
    };
    let (client, server) = peer(server, Some(SENDER));
    (client, server, received)
}

fn portal(client: Connection) -> DbusPortal {
    DbusPortal::with_limit(client, LIMIT)
}

fn handle(token: &str) -> String {
    ok(request_path(SENDER, token))
}

fn uri(text: &str) -> Uri {
    Uri::Text(String::from(text))
}

#[test]
fn the_sender_is_the_connection_unique_name() {
    let (client, _server, _) = fake(Answer::Elsewhere);

    assert_eq!(DbusPortal::new(client).sender(), Ok(String::from(SENDER)));
}

#[test]
fn a_connection_with_no_unique_name_has_no_sender() {
    let (client, _server) = peer(WrongReplyPortal, None);

    let error = DbusPortal::new(client).sender().unwrap_err();

    assert!(error.0.contains("no unique bus name"), "{error:?}");
}

#[test]
fn a_response_sent_before_the_method_reply_reaches_the_client() {
    let (client, _server, received) = fake(Answer::Respond(0, Some(uri("file:///tmp/out.png"))));

    let reply = portal(client).screenshot(&handle("cortex7"), "cortex7");

    assert_eq!(
        reply,
        Ok(PortalReply {
            code: 0,
            uri: Some(String::from("file:///tmp/out.png")),
        })
    );
    let calls = received.lock().unwrap();
    let (parent_window, options) = &calls[0];
    assert_eq!(parent_window, "");
    assert_eq!(options.len(), 2);
    assert_eq!(
        String::try_from(&*options["handle_token"]).unwrap(),
        "cortex7"
    );
    assert!(!bool::try_from(&*options["interactive"]).unwrap());
}

#[test]
fn a_uri_that_is_not_a_string_or_is_missing_is_no_uri() {
    for (code, uri) in [(0, Some(Uri::Number(5))), (2, None)] {
        let (client, _server, _) = fake(Answer::Respond(code, uri));

        let reply = portal(client).screenshot(&handle("t"), "t");

        assert_eq!(reply, Ok(PortalReply { code, uri: None }));
    }
}

#[test]
fn a_failed_exchange_is_an_error_with_its_text() {
    let cases = [
        (Answer::Refuse, "not allowed"),
        (
            Answer::Elsewhere,
            "answered on /org/freedesktop/portal/desktop/request/1_16/other",
        ),
        (Answer::WrongSignal, "Signature mismatch"),
    ];
    for (answer, expected) in cases {
        let (client, _server, _) = fake(answer);

        let error = portal(client).screenshot(&handle("t"), "t").unwrap_err();

        assert!(error.0.contains(expected), "{expected}: {error:?}");
    }
}

#[test]
fn a_method_reply_that_is_not_a_handle_is_an_error() {
    let (client, _server) = peer(WrongReplyPortal, Some(SENDER));

    let error = portal(client).screenshot(&handle("t"), "t").unwrap_err();

    assert!(error.0.contains("Signature mismatch"), "{error:?}");
}

#[test]
fn a_handle_that_is_not_an_object_path_is_an_error_before_any_call() {
    let (client, _server, received) = fake(Answer::Respond(0, None));

    let error = portal(client).screenshot("not a path", "t").unwrap_err();

    assert!(!error.0.is_empty());
    assert!(received.lock().unwrap().is_empty());
}

#[test]
fn every_portal_call_on_a_bus_that_did_not_open_fails_with_its_text() {
    let Err(error) =
        Builder::address("unix:path=/nonexistent-cortex-test/bus").and_then(Builder::build)
    else {
        panic!("a bus with no socket opened");
    };
    let portal = DbusPortal::absent(&error);

    assert_eq!(portal.sender().unwrap_err().0, error.to_string());
    assert_eq!(
        portal.screenshot(&handle("t"), "t").unwrap_err().0,
        error.to_string()
    );
}

fn scratch(name: &str) -> PathBuf {
    std::env::temp_dir().join(format!("cortex-portal-{}-{name}", std::process::id()))
}

#[test]
fn a_file_is_read_then_removed_and_a_missing_one_names_its_path() {
    let file = scratch("read");
    fs::write(&file, b"picture").unwrap();
    let (client, _server, _) = fake(Answer::Elsewhere);
    let portal = portal(client);

    assert_eq!(portal.read(&file), Ok(b"picture".to_vec()));
    assert_eq!(portal.remove(&file), Ok(()));
    assert!(!file.exists());

    let unread = portal.read(&file).unwrap_err().0;
    let kept = portal.remove(&file).unwrap_err().0;
    assert!(
        unread.starts_with(&format!("could not read {}", file.display())),
        "{unread}"
    );
    assert!(
        kept.starts_with(&format!("could not remove {}", file.display())),
        "{kept}"
    );
}

fn rgb_png(path: &Path) {
    let mut bytes = Vec::new();
    let mut encoder = png::Encoder::new(&mut bytes, 1, 1);
    encoder.set_color(png::ColorType::Rgb);
    let mut writer = ok(encoder.write_header());
    ok(writer.write_image_data(&[51, 102, 204]));
    ok(writer.finish());
    ok(fs::write(path, bytes));
}

#[test]
fn the_backend_captures_through_the_portal_end_to_end() {
    let file = scratch("out.png");
    rgb_png(&file);
    let answer = Answer::Respond(0, Some(uri(&format!("file://{}", file.display()))));
    let (client, _server, received) = fake(answer);
    let backend = LinuxPortalCapture::new(DbusPortal::new(client));

    let captured = backend.capture(&CaptureRequest::new(0)).unwrap();

    assert_eq!(captured.frame().pixels(), [204, 102, 51, 255]);
    assert!(!file.exists());
    let calls = received.lock().unwrap();
    assert_eq!(
        String::try_from(&*calls[0].1["handle_token"]).unwrap(),
        "cortex0"
    );
}

/// Waits up to [`LIMIT`] for `done`, checking it every few milliseconds.
fn eventually(done: impl Fn() -> bool) -> bool {
    let started = Instant::now();
    while started.elapsed() < LIMIT {
        if done() {
            return true;
        }
        thread::sleep(Duration::from_millis(5));
    }
    done()
}

/// Runs `call` on its own thread and returns its value, failing the test if it takes [`LIMIT`].
fn within_limit<T: Send + 'static>(call: impl FnOnce() -> T + Send + 'static) -> T {
    let (sender, receiver) = std::sync::mpsc::channel();
    thread::spawn(move || sender.send(call()));
    receiver
        .recv_timeout(LIMIT)
        .unwrap_or_else(|error| panic!("the call did not return within {LIMIT:?}: {error}"))
}

#[test]
fn a_portal_that_never_answers_fails_at_the_limit_and_its_request_is_closed() {
    let (client, server, _) = fake(Answer::Silent);
    let closed = Arc::new(Mutex::new(Vec::new()));
    let request = FakeRequest {
        closed: Arc::clone(&closed),
    };
    assert!(ok(server.object_server().at(handle("t"), request)));
    let started = Instant::now();

    let error =
        within_limit(move || DbusPortal::with_limit(client, SHORT).screenshot(&handle("t"), "t"))
            .unwrap_err();

    let waited = started.elapsed();
    assert!(waited >= SHORT && waited < LIMIT, "{waited:?}");
    assert!(
        error.0.contains(&format!("no response on {}", handle("t"))),
        "{error:?}"
    );
    assert!(eventually(|| closed.lock().unwrap().len() == 1));
    assert_eq!(*closed.lock().unwrap(), [handle("t")]);
}

#[test]
fn a_capture_after_one_that_timed_out_succeeds_and_reads_no_late_answer() {
    let file = scratch("late.png");
    rgb_png(&file);
    let answer = Answer::Respond(0, Some(uri(&format!("file://{}", file.display()))));
    let (client, server, received) = fake_in_order(vec![Answer::Silent, answer]);
    let backend = Arc::new(LinuxPortalCapture::new(DbusPortal::with_limit(
        client, SHORT,
    )));

    let capturing = Arc::clone(&backend);
    let first = within_limit(move || capturing.capture(&CaptureRequest::new(0))).unwrap_err();
    let late = HashMap::from([("uri", Value::from("file:///nonexistent-cortex-late.png"))]);
    let late_path = handle("cortex0");
    ok(server.emit_signal(
        None::<BusName<'_>>,
        late_path.as_str(),
        REQUEST,
        "Response",
        &(0_u32, late),
    ));
    let second = backend.capture(&CaptureRequest::new(0)).unwrap();

    assert!(
        matches!(&first, CaptureError::Backend(text) if text.contains("no response on")),
        "{first:?}"
    );
    assert_eq!(second.frame().pixels(), [204, 102, 51, 255]);
    assert!(!file.exists());
    let calls = received.lock().unwrap();
    let tokens: Vec<String> = calls
        .iter()
        .map(|(_, options)| String::try_from(&*options["handle_token"]).unwrap())
        .collect();
    assert_eq!(tokens, ["cortex0", "cortex1"]);
}

#[test]
fn a_bus_that_closes_before_the_response_is_an_error_before_the_limit() {
    let (client, server, received) = fake(Answer::Silent);
    let closing = thread::spawn(move || {
        assert!(eventually(|| received.lock().unwrap().len() == 1));
        thread::sleep(Duration::from_millis(200));
        ok(server.close());
    });
    let started = Instant::now();

    let error = portal(client).screenshot(&handle("t"), "t").unwrap_err();

    assert!(started.elapsed() < LIMIT, "{:?}", started.elapsed());
    assert!(!error.0.contains("no response"), "{error:?}");
    ok(closing.join());
}
