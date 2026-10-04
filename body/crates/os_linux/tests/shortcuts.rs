#![cfg(target_os = "linux")]

use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use body_contract::hotkey::{HotkeyRig, HotkeySubject, run};
use body_core::{Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};
use os_linux::{
    Activation, LinuxPortalHotkey, PortalError, Shortcut, ShortcutsPortal, ShortcutsReply,
    keysym_name, trigger,
};

const SENDER: &str = ":1.16";
const ROOT: &str = "/org/freedesktop/portal/desktop";
const DESCRIPTION: &str = "Show or hide the overlay";

/// How a fake portal answers one kind of request.
#[derive(Clone)]
enum Answer {
    /// The code, naming what the backend asked for.
    Named(u32),
    /// The code, naming this instead.
    Other(u32, &'static str),
    Fails,
}

/// One call the backend made, with its arguments.
#[derive(Clone, Debug, PartialEq, Eq)]
enum Call {
    Create(String, String, String),
    Bind(String, String, String, Shortcut),
}

struct FakePortal {
    sender: Result<String, PortalError>,
    create: Answer,
    bind: Answer,
    calls: Arc<Mutex<Vec<Call>>>,
    activations: Mutex<Receiver<Activation>>,
    _alive: Arc<()>,
}

fn reply(answer: &Answer, expected: &str) -> Result<ShortcutsReply, PortalError> {
    match answer {
        Answer::Named(code) => Ok(ShortcutsReply {
            code: *code,
            names: vec![String::from(expected)],
        }),
        Answer::Other(code, name) => Ok(ShortcutsReply {
            code: *code,
            names: vec![String::from(*name)],
        }),
        Answer::Fails => Err(PortalError(String::from("UnknownMethod"))),
    }
}

impl FakePortal {
    fn record(&self, call: Call) {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(call);
    }
}

impl ShortcutsPortal for FakePortal {
    fn sender(&self) -> Result<String, PortalError> {
        self.sender.clone()
    }

    fn create_session(
        &self,
        handle: &str,
        token: &str,
        session_token: &str,
    ) -> Result<ShortcutsReply, PortalError> {
        self.record(Call::Create(
            handle.to_owned(),
            token.to_owned(),
            session_token.to_owned(),
        ));
        reply(
            &self.create,
            &format!("{ROOT}/session/1_16/{session_token}"),
        )
    }

    fn bind(
        &self,
        session: &str,
        handle: &str,
        token: &str,
        shortcut: &Shortcut,
    ) -> Result<ShortcutsReply, PortalError> {
        let call = Call::Bind(
            session.to_owned(),
            handle.to_owned(),
            token.to_owned(),
            shortcut.clone(),
        );
        self.record(call);
        reply(&self.bind, &shortcut.id)
    }

    fn next_activation(&self) -> Result<Activation, PortalError> {
        self.activations
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .recv()
            .map_err(|error| PortalError(error.to_string()))
    }
}

struct Rig {
    hotkey: LinuxPortalHotkey,
    calls: Arc<Mutex<Vec<Call>>>,
    activations: Sender<Activation>,
    alive: Arc<()>,
}

fn rig(sender: &str, create: Answer, bind: Answer) -> Rig {
    let calls = Arc::new(Mutex::new(Vec::new()));
    let (activations, received) = mpsc::channel();
    let alive = Arc::new(());
    let sender = match sender {
        "" => Err(PortalError(String::from("no session bus"))),
        name => Ok(String::from(name)),
    };
    let portal = FakePortal {
        sender,
        create,
        bind,
        calls: Arc::clone(&calls),
        activations: Mutex::new(received),
        _alive: Arc::clone(&alive),
    };
    Rig {
        hotkey: LinuxPortalHotkey::new(portal, DESCRIPTION),
        calls,
        activations,
        alive,
    }
}

fn working() -> Rig {
    rig(SENDER, Answer::Named(0), Answer::Named(0))
}

fn chord(text: &str) -> HotkeyChord {
    HotkeyChord::parse(text).unwrap_or_else(|error| panic!("{error:?}"))
}

impl Rig {
    fn calls(&self) -> Vec<Call> {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }

    fn register(&self, text: &str) -> (Result<(), HotkeyError>, Receiver<()>) {
        let (fired, on_fire) = mpsc::channel();
        let callback: HotkeyCallback = Box::new(move || {
            fired.send(()).unwrap_or_else(|error| panic!("{error:?}"));
        });
        (self.hotkey.register(&chord(text), callback), on_fire)
    }

    fn activate(&self, session: &str, shortcut: &str) {
        self.activations
            .send(Activation {
                session: session.to_owned(),
                shortcut: shortcut.to_owned(),
            })
            .unwrap_or_else(|error| panic!("{error:?}"));
    }

    /// Ends the listener and waits for it to drop the fake, so every signal sent has been read.
    fn close(self) {
        let Self {
            hotkey,
            activations,
            alive,
            ..
        } = self;
        drop(activations);
        drop(hotkey);
        let deadline = Instant::now() + Duration::from_secs(5);
        while Arc::strong_count(&alive) > 1 {
            assert!(Instant::now() < deadline, "the listener did not end");
            thread::sleep(Duration::from_millis(5));
        }
    }
}

fn error_text(result: Result<(), HotkeyError>) -> String {
    match result {
        Err(HotkeyError::Registration(text)) => text,
        other => panic!("expected a registration error, got {other:?}"),
    }
}

#[test]
fn a_registration_creates_a_session_then_binds_the_chord_in_it() {
    let rig = working();

    let (registered, _) = rig.register("ctrl+alt+space");

    assert_eq!(registered, Ok(()));
    let session = format!("{ROOT}/session/1_16/cortex1");
    assert_eq!(
        rig.calls(),
        vec![
            Call::Create(
                format!("{ROOT}/request/1_16/cortex1"),
                String::from("cortex1"),
                String::from("cortex1")
            ),
            Call::Bind(
                session,
                format!("{ROOT}/request/1_16/cortex2"),
                String::from("cortex2"),
                Shortcut {
                    id: String::from("ctrl+alt+space"),
                    description: String::from(DESCRIPTION),
                    trigger: String::from("CTRL+ALT+space"),
                }
            ),
        ]
    );
}

#[test]
fn each_registration_takes_fresh_tokens() {
    let rig = working();

    let _ = rig.register("super+a");
    let _ = rig.register("super+1");

    let calls = rig.calls();
    assert_eq!(
        calls[2],
        Call::Create(
            format!("{ROOT}/request/1_16/cortex3"),
            String::from("cortex3"),
            String::from("cortex3")
        )
    );
}

#[test]
fn a_trigger_names_the_modifiers_in_order_then_the_keysym() {
    let cases = [
        ("super+shift+f12", "SHIFT+LOGO+F12"),
        ("ctrl+alt+shift+super+a", "CTRL+ALT+SHIFT+LOGO+a"),
        ("alt+7", "ALT+7"),
        ("f1", "F1"),
    ];
    for (text, expected) in cases {
        assert_eq!(trigger(&chord(text)), Ok(String::from(expected)), "{text}");
    }
}

#[test]
fn every_named_code_has_its_keysym_name() {
    let cases = [
        ("Space", "space"),
        ("Enter", "Return"),
        ("Escape", "Escape"),
        ("Tab", "Tab"),
        ("Backspace", "BackSpace"),
        ("ArrowUp", "Up"),
        ("ArrowDown", "Down"),
        ("ArrowLeft", "Left"),
        ("ArrowRight", "Right"),
        ("KeyQ", "q"),
        ("Digit0", "0"),
        ("F24", "F24"),
        ("F35", "F35"),
    ];
    for (code, name) in cases {
        assert_eq!(keysym_name(code).as_deref(), Some(name), "{code}");
    }
}

#[test]
fn a_code_with_no_keysym_name_here_is_none() {
    for code in ["Home", "F0", "F36", "Fx", "Keya", "Digit", "KeyAB"] {
        assert_eq!(keysym_name(code), None, "{code}");
    }
}

#[test]
fn a_key_with_no_code_is_unsupported_before_any_call() {
    let rig = working();

    let (registered, _) = rig.register("ctrl+home");

    assert_eq!(
        registered,
        Err(HotkeyError::UnsupportedKey(String::from("home")))
    );
    assert_eq!(rig.calls(), vec![]);
}

#[test]
fn a_sender_that_is_not_a_unique_name_is_refused_before_any_call() {
    let rig = rig("org.example", Answer::Named(0), Answer::Named(0));

    let text = error_text(rig.register("ctrl+alt+space").0);

    assert!(text.contains("\"org.example\""), "{text}");
    assert_eq!(rig.calls(), vec![]);
}

#[test]
fn a_bus_that_did_not_open_fails_naming_the_chord() {
    let rig = rig("", Answer::Named(0), Answer::Named(0));

    let text = error_text(rig.register("ctrl+alt+space").0);

    assert_eq!(text, "ctrl+alt+space: no session bus");
}

#[test]
fn a_session_that_is_not_created_binds_nothing() {
    let cases = [
        (Answer::Fails, "ctrl+alt+space: UnknownMethod"),
        (Answer::Named(1), "the user cancelled the session"),
        (Answer::Named(2), "with response 2"),
        (
            Answer::Other(0, "/elsewhere"),
            "success without the session",
        ),
    ];
    for (answer, expected) in cases {
        let rig = rig(SENDER, answer, Answer::Named(0));

        let text = error_text(rig.register("ctrl+alt+space").0);

        assert!(text.contains(expected), "{text}");
        assert_eq!(rig.calls().len(), 1);
    }
}

#[test]
fn a_shortcut_that_is_not_bound_never_runs() {
    let cases = [
        (Answer::Fails, "ctrl+alt+space: UnknownMethod"),
        (
            Answer::Named(1),
            "the user cancelled the shortcut ctrl+alt+space",
        ),
        (Answer::Named(3), "with response 3"),
        (Answer::Other(0, "other"), "success without the shortcut"),
    ];
    for (answer, expected) in cases {
        let rig = rig(SENDER, Answer::Named(0), answer);

        let (registered, fired) = rig.register("ctrl+alt+space");
        rig.activate(&format!("{ROOT}/session/1_16/cortex1"), "ctrl+alt+space");
        rig.close();

        let text = error_text(registered);
        assert!(text.contains(expected), "{text}");
        assert!(fired.try_recv().is_err());
    }
}

#[test]
fn an_activation_runs_only_the_binding_with_its_session_and_id() {
    let rig = working();
    let (registered, fired) = rig.register("ctrl+alt+space");
    let session = format!("{ROOT}/session/1_16/cortex1");

    rig.activate(&session, "super+a");
    rig.activate(&format!("{ROOT}/session/1_16/cortex9"), "ctrl+alt+space");
    rig.activate(&session, "ctrl+alt+space");
    rig.close();

    assert_eq!(registered, Ok(()));
    assert_eq!(fired.try_iter().count(), 1);
}

impl HotkeyRig for Rig {
    fn hotkey(&self) -> &dyn Hotkey {
        &self.hotkey
    }

    fn press(&self, chord: &HotkeyChord) {
        let id = chord.to_string();
        for call in self.calls() {
            if let Call::Bind(session, _, _, shortcut) = call
                && shortcut.id == id
            {
                self.activate(&session, &id);
            }
        }
    }

    fn finish(self: Box<Self>) {
        self.close();
    }
}

struct Portal;

impl HotkeySubject for Portal {
    fn listening(&self) -> Box<dyn HotkeyRig> {
        Box::new(working())
    }

    fn taken(&self) -> Box<dyn HotkeyRig> {
        Box::new(rig(SENDER, Answer::Named(0), Answer::Named(2)))
    }

    fn broken(&self) -> Box<dyn HotkeyRig> {
        Box::new(rig("", Answer::Named(0), Answer::Named(0)))
    }
}

#[test]
fn the_portal_backend_meets_every_hotkey_check() {
    run(&Portal);
}
