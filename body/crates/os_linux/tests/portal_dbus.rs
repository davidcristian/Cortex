#![cfg(target_os = "linux")]

use std::collections::HashMap;
use std::fs;
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;

use body_core::{CaptureRequest, ScreenCapture};
use os_linux::zbus::blocking::Connection;
use os_linux::zbus::blocking::connection::Builder;
use os_linux::zbus::names::BusName;
use os_linux::zbus::zvariant::{OwnedObjectPath, OwnedValue, Value};
use os_linux::zbus::{Guid, fdo, interface};
use os_linux::{DbusPortal, LinuxPortalCapture, PortalReply, ScreenshotPortal, request_path};

const PATH: &str = "/org/freedesktop/portal/desktop";
const SENDER: &str = ":1.16";
const REQUEST: &str = "org.freedesktop.portal.Request";

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
    Elsewhere,
    WrongSignal,
    Refuse,
}

/// The arguments of one `Screenshot` call: the parent window and every option.
type Received = (String, HashMap<String, OwnedValue>);

/// A fake portal frontend that emits its `Response` before its method reply, as a fast one can.
struct FakePortal {
    answer: Answer,
    received: Arc<Mutex<Vec<Received>>>,
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
        let code = match self.answer.clone() {
            Answer::Refuse => return Err(fdo::Error::AccessDenied(String::from("not allowed"))),
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
    let received = Arc::new(Mutex::new(Vec::new()));
    let server = FakePortal {
        answer,
        received: Arc::clone(&received),
    };
    let (client, server) = peer(server, Some(SENDER));
    (client, server, received)
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

    let reply = DbusPortal::new(client).screenshot(&handle("cortex7"), "cortex7");

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

        let reply = DbusPortal::new(client).screenshot(&handle("t"), "t");

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

        let error = DbusPortal::new(client)
            .screenshot(&handle("t"), "t")
            .unwrap_err();

        assert!(error.0.contains(expected), "{expected}: {error:?}");
    }
}

#[test]
fn a_method_reply_that_is_not_a_handle_is_an_error() {
    let (client, _server) = peer(WrongReplyPortal, Some(SENDER));

    let error = DbusPortal::new(client)
        .screenshot(&handle("t"), "t")
        .unwrap_err();

    assert!(error.0.contains("Signature mismatch"), "{error:?}");
}

#[test]
fn a_handle_that_is_not_an_object_path_is_an_error_before_any_call() {
    let (client, _server, received) = fake(Answer::Respond(0, None));

    let error = DbusPortal::new(client)
        .screenshot("not a path", "t")
        .unwrap_err();

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
    let portal = DbusPortal::new(client);

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
