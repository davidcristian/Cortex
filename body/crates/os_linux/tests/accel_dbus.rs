#![cfg(target_os = "linux")]

use std::os::unix::net::UnixStream;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::Duration;

use body_core::{Hotkey, HotkeyChord};
use os_linux::zbus::blocking::Connection;
use os_linux::zbus::blocking::connection::Builder;
use os_linux::zbus::names::BusName;
use os_linux::zbus::{Guid, Message, fdo, interface};
use os_linux::{DbusGlobalAccel, GlobalAccel, LinuxKdeHotkey, Press, kglobalaccel_running};

/// The unique name of the fake `kglobalaccel`, which signs every signal it sends.
const OWNER: &str = ":1.0";
const COMPONENT_PATH: &str = "/component/cortex";
const SIGNALS: &str = "org.kde.kglobalaccel.Component";
const LIMIT: Duration = Duration::from_secs(3);

fn ok<T, E: std::fmt::Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("a setup step failed: {error:?}"))
}

/// Each call the fakes received, as text: the method, then each value in the order sent.
type Received = Arc<Mutex<Vec<Vec<String>>>>;

fn record(received: &Received, values: Vec<String>) {
    received
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .push(values);
}

/// A fake `kglobalaccel` that gives every key asked for, or refuses every call.
struct FakeAccel {
    refuse: bool,
    received: Received,
}

impl FakeAccel {
    fn check(&self, values: Vec<String>) -> fdo::Result<()> {
        record(&self.received, values);
        if self.refuse {
            return Err(fdo::Error::AccessDenied(String::from("not allowed")));
        }
        Ok(())
    }
}

#[interface(name = "org.kde.KGlobalAccel")]
impl FakeAccel {
    #[zbus(name = "doRegister")]
    fn do_register(&self, action: Vec<String>) -> fdo::Result<()> {
        self.check([vec![String::from("doRegister")], action].concat())
    }

    #[zbus(name = "setShortcut")]
    fn set_shortcut(
        &self,
        action: Vec<String>,
        keys: Vec<i32>,
        flags: u32,
    ) -> fdo::Result<Vec<i32>> {
        let shown = keys.iter().map(|key| format!("{key:#x}"));
        let values = [
            vec![String::from("setShortcut")],
            action,
            shown.collect(),
            vec![flags.to_string()],
        ];
        self.check(values.concat())?;
        Ok(keys)
    }

    #[zbus(name = "unregister")]
    fn unregister(&self, component: String, action: String) -> fdo::Result<bool> {
        self.check(vec![String::from("unregister"), component, action])?;
        Ok(true)
    }
}

/// A fake bus that names the owner, after naming none for its first `refusals` asks.
struct FakeBus {
    refusals: AtomicU32,
    received: Received,
}

#[interface(name = "org.freedesktop.DBus")]
impl FakeBus {
    fn get_name_owner(&self, name: String) -> fdo::Result<String> {
        record(&self.received, vec![String::from("owner"), name.clone()]);
        let next = |left: u32| left.checked_sub(1);
        match self
            .refusals
            .fetch_update(Ordering::SeqCst, Ordering::SeqCst, next)
        {
            Ok(_) => Err(fdo::Error::NameHasNoOwner(name)),
            Err(_) => Ok(String::from(OWNER)),
        }
    }
}

fn fake(refuse: bool, refusals: u32) -> (Connection, Connection, Received) {
    let received = Arc::new(Mutex::new(Vec::new()));
    let accel = FakeAccel {
        refuse,
        received: Arc::clone(&received),
    };
    let bus = FakeBus {
        refusals: AtomicU32::new(refusals),
        received: Arc::clone(&received),
    };
    let (client_end, server_end) = ok(UnixStream::pair());
    let serving = thread::spawn(move || {
        Builder::async_io_unix_stream(server_end)
            .server(Guid::generate())
            .and_then(|builder| builder.p2p().serve_at("/kglobalaccel", accel))
            .and_then(|builder| builder.serve_at("/org/freedesktop/DBus", bus))
            .and_then(Builder::build)
    });
    let client = ok(Builder::async_io_unix_stream(client_end).p2p().build());
    let server = ok(ok(serving.join()));
    ok(server.inner().set_unique_name(OWNER));
    (client, server, received)
}

fn working() -> (DbusGlobalAccel, Connection, Received) {
    let (client, server, received) = fake(false, 0);
    (DbusGlobalAccel::new(client), server, received)
}

fn received(record: &Received) -> Vec<Vec<String>> {
    record
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone()
}

fn emit(server: &Connection, member: &str, action: &str) {
    let body = ("cortex", action, 7_i64);
    ok(server.emit_signal(None::<BusName<'_>>, COMPONENT_PATH, SIGNALS, member, &body));
}

/// Sends a press for `action` that names `sender`, or no sender, in place of the owner's.
fn forged(server: &Connection, sender: Option<&str>, action: &str) {
    let mut builder = ok(Message::signal(
        COMPONENT_PATH,
        SIGNALS,
        "globalShortcutPressed",
    ));
    if let Some(sender) = sender {
        builder = ok(builder.sender(sender));
    }
    ok(server.send(&ok(builder.build(&("cortex", action, 7_i64)))));
}

fn press(action: &str, active: bool) -> Press {
    Press {
        action: String::from(action),
        active,
    }
}

#[test]
fn a_bind_registers_the_action_then_sets_its_key_as_given_and_present() {
    let (accel, _server, record) = working();

    let keys = accel.bind("ctrl+alt+space", "Show or hide the overlay", 0x0C00_0020);

    assert_eq!(keys, Ok(vec![0x0C00_0020]));
    let id = [
        "cortex",
        "ctrl+alt+space",
        "Cortex",
        "Show or hide the overlay",
    ];
    let register = [&["doRegister"][..], &id].concat();
    let set = [&["setShortcut"][..], &id, &["0xc000020", "6"]].concat();
    assert_eq!(received(&record), vec![register, set]);
}

#[test]
fn an_unbind_removes_the_action_from_the_component() {
    let (accel, _server, record) = working();

    assert_eq!(accel.unbind("super+a"), Ok(()));

    assert_eq!(
        received(&record),
        vec![vec!["unregister", "cortex", "super+a"]]
    );
}

#[test]
fn a_refused_call_fails_with_the_bus_error_and_sets_no_key() {
    let (client, _server, record) = fake(true, 0);
    let accel = DbusGlobalAccel::new(client);

    let errors = [
        accel.bind("ctrl+alt+space", "Show", 0x20).unwrap_err(),
        accel.unbind("ctrl+alt+space").unwrap_err(),
    ];

    for error in errors {
        assert!(error.0.contains("not allowed"), "{error:?}");
    }
    let calls: Vec<String> = received(&record)
        .into_iter()
        .map(|call| call[0].clone())
        .collect();
    assert_eq!(calls, vec!["doRegister", "unregister"]);
}

#[test]
fn each_press_and_release_is_read_in_order_and_other_or_forged_signals_are_skipped() {
    let (accel, server, _) = working();

    ok(server.emit_signal(
        None::<BusName<'_>>,
        COMPONENT_PATH,
        SIGNALS,
        "globalShortcutPressed",
        &("wrong",),
    ));
    emit(
        &server,
        "globalShortcutAvailabilityChanged",
        "ctrl+alt+space",
    );
    forged(&server, Some(":1.99"), "ctrl+alt+space");
    forged(&server, None, "ctrl+alt+space");
    emit(&server, "globalShortcutPressed", "ctrl+alt+space");
    emit(&server, "globalShortcutReleased", "ctrl+alt+space");

    assert_eq!(accel.next_press(), Ok(press("ctrl+alt+space", true)));
    assert_eq!(accel.next_press(), Ok(press("ctrl+alt+space", false)));
}

#[test]
fn the_owner_is_asked_until_the_bus_names_one_then_kept() {
    let (client, server, record) = fake(false, 1);
    let accel = DbusGlobalAccel::new(client);

    forged(&server, None, "ctrl+alt+space");
    emit(&server, "globalShortcutPressed", "super+a");
    emit(&server, "globalShortcutReleased", "super+a");

    assert_eq!(accel.next_press(), Ok(press("super+a", true)));
    assert_eq!(accel.next_press(), Ok(press("super+a", false)));
    let asked = vec!["owner", "org.kde.kglobalaccel"];
    assert_eq!(received(&record), vec![asked.clone(), asked]);
}

#[test]
fn kglobalaccel_runs_only_where_the_bus_names_its_owner() {
    for (refusals, running) in [(0, true), (1, false)] {
        let (client, _server, _) = fake(false, refusals);

        assert_eq!(kglobalaccel_running(&client), running, "{refusals}");
    }
}

#[test]
fn a_closed_connection_ends_the_presses() {
    let (accel, server, _) = working();

    drop(server);

    let errors = [accel.next_press(), accel.next_press()].map(Result::unwrap_err);
    assert!(errors[0].0.contains("failed to read"), "{errors:?}");
    assert!(errors[1].0.contains("the bus closed"), "{errors:?}");
}

#[test]
fn a_bus_that_did_not_open_fails_every_call_with_its_text() {
    let accel = DbusGlobalAccel::absent(&os_linux::zbus::Error::Failure(String::from("no bus")));

    let errors = [
        accel.bind("ctrl+alt+space", "Show", 0x20).unwrap_err(),
        accel.unbind("ctrl+alt+space").unwrap_err(),
        accel.next_press().unwrap_err(),
    ];

    for error in errors {
        assert!(error.0.contains("no bus"), "{error:?}");
    }
}

#[test]
fn the_hotkey_over_the_bus_runs_once_per_press_and_removes_its_action_when_dropped() {
    let (accel, server, record) = working();
    let hotkey =
        LinuxKdeHotkey::with_gap(accel, "Show or hide the overlay", Duration::from_hours(1));
    let (fired, on_fire) = mpsc::channel();
    let chord = ok(HotkeyChord::parse("ctrl+alt+space"));

    let registered = hotkey.register(
        &chord,
        Box::new(move || fired.send(()).unwrap_or_else(|error| panic!("{error:?}"))),
    );
    for presses in [3, 1] {
        for _ in 0..presses {
            emit(&server, "globalShortcutPressed", "ctrl+alt+space");
        }
        emit(&server, "globalShortcutReleased", "ctrl+alt+space");
    }

    assert_eq!(registered, Ok(()));
    for _ in 0..2 {
        assert_eq!(on_fire.recv_timeout(LIMIT), Ok(()));
    }
    assert!(on_fire.recv_timeout(Duration::from_millis(200)).is_err());
    drop(hotkey);
    let last = received(&record).pop();
    assert_eq!(
        last,
        Some(vec![
            String::from("unregister"),
            String::from("cortex"),
            String::from("ctrl+alt+space")
        ])
    );
}
