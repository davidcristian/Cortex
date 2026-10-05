#![cfg(target_os = "linux")]

use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use body_contract::hotkey::{HotkeyRig, HotkeySubject, run};
use body_core::{Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};
use os_linux::{AccelError, GlobalAccel, LinuxKdeHotkey, Press, qt_code, qt_key};

const DESCRIPTION: &str = "Show or hide the overlay";
/// A gap no test run reaches between two signals, so a hold ends only at its release.
const HOUR: Duration = Duration::from_hours(1);
/// The presses `kglobalaccel` sent for a chord held 1.5 s, before its release.
const HELD: usize = 24;

/// How a fake `kglobalaccel` answers a registration.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Answer {
    Given,
    Taken,
    Fails,
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum Call {
    Bind(String, String, i32),
    Unbind(String),
}

struct FakeAccel {
    answer: Answer,
    calls: Arc<Mutex<Vec<Call>>>,
    presses: Mutex<Receiver<Press>>,
    _alive: Arc<()>,
}

impl FakeAccel {
    fn record(&self, call: Call) {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(call);
    }
}

impl GlobalAccel for FakeAccel {
    fn bind(&self, action: &str, description: &str, key: i32) -> Result<Vec<i32>, AccelError> {
        self.record(Call::Bind(action.to_owned(), description.to_owned(), key));
        match self.answer {
            Answer::Given => Ok(vec![key]),
            Answer::Taken => Ok(vec![0]),
            Answer::Fails => Err(AccelError(String::from("ServiceUnknown"))),
        }
    }

    fn unbind(&self, action: &str) -> Result<(), AccelError> {
        self.record(Call::Unbind(action.to_owned()));
        match self.answer {
            Answer::Fails => Err(AccelError(String::from("ServiceUnknown"))),
            _ => Ok(()),
        }
    }

    fn next_press(&self) -> Result<Press, AccelError> {
        self.presses
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .recv()
            .map_err(|error| AccelError(error.to_string()))
    }
}

struct Rig {
    hotkey: LinuxKdeHotkey,
    calls: Arc<Mutex<Vec<Call>>>,
    presses: Sender<Press>,
    alive: Arc<()>,
}

fn rig(answer: Answer, gap: Option<Duration>) -> Rig {
    let calls = Arc::new(Mutex::new(Vec::new()));
    let (presses, received) = mpsc::channel();
    let alive = Arc::new(());
    let accel = FakeAccel {
        answer,
        calls: Arc::clone(&calls),
        presses: Mutex::new(received),
        _alive: Arc::clone(&alive),
    };
    let hotkey = match gap {
        Some(gap) => LinuxKdeHotkey::with_gap(accel, DESCRIPTION, gap),
        None => LinuxKdeHotkey::new(accel, DESCRIPTION),
    };
    Rig {
        hotkey,
        calls,
        presses,
        alive,
    }
}

fn working() -> Rig {
    rig(Answer::Given, Some(HOUR))
}

fn chord(text: &str) -> HotkeyChord {
    HotkeyChord::parse(text).unwrap_or_else(|error| panic!("{error:?}"))
}

impl Rig {
    fn calls(&self) -> Vec<Call> {
        calls(&self.calls)
    }

    fn register(&self, text: &str) -> (Result<(), HotkeyError>, Receiver<()>) {
        let (fired, on_fire) = mpsc::channel();
        let callback: HotkeyCallback = Box::new(move || {
            fired.send(()).unwrap_or_else(|error| panic!("{error:?}"));
        });
        (self.hotkey.register(&chord(text), callback), on_fire)
    }

    fn signal(&self, action: &str, active: bool) {
        let press = Press {
            action: action.to_owned(),
            active,
        };
        self.presses
            .send(press)
            .unwrap_or_else(|error| panic!("{error:?}"));
    }

    fn signals(&self, chord: &HotkeyChord, presses: usize) {
        for _ in 0..presses {
            self.signal(&chord.to_string(), true);
        }
        self.signal(&chord.to_string(), false);
    }

    /// Drops the backend, ends the listener and waits for it to drop the fake; returns the calls.
    fn close(self) -> Vec<Call> {
        let Self {
            hotkey,
            calls: made,
            presses,
            alive,
        } = self;
        drop(presses);
        drop(hotkey);
        let deadline = Instant::now() + Duration::from_secs(5);
        while Arc::strong_count(&alive) > 1 {
            assert!(Instant::now() < deadline, "the listener did not end");
            thread::sleep(Duration::from_millis(5));
        }
        calls(&made)
    }
}

fn calls(calls: &Mutex<Vec<Call>>) -> Vec<Call> {
    calls.lock().unwrap_or_else(PoisonError::into_inner).clone()
}

fn bind(action: &str, key: i32) -> Call {
    Call::Bind(action.to_owned(), DESCRIPTION.to_owned(), key)
}

fn unbind(action: &str) -> Call {
    Call::Unbind(action.to_owned())
}

#[test]
fn a_registration_binds_the_chords_text_to_its_qt_key_code() {
    let rig = working();

    let (registered, _) = rig.register("ctrl+alt+space");

    assert_eq!(registered, Ok(()));
    assert_eq!(rig.calls(), vec![bind("ctrl+alt+space", 0x0C00_0020)]);
}

#[test]
fn a_qt_key_code_adds_each_modifiers_bit_to_the_keys_code() {
    let cases = [
        ("ctrl+alt+space", 0x0C00_0020),
        ("super+a", 0x1000_0041),
        ("shift+1", 0x0200_0031),
        ("alt+f5", 0x0800_0000 | 0x0100_0034),
    ];
    for (text, code) in cases {
        assert_eq!(qt_key(&chord(text)), Ok(code), "{text}");
    }
}

#[test]
fn every_named_code_has_its_qt_key_value() {
    let cases = [
        ("Space", 0x20),
        ("Escape", 0x0100_0000),
        ("Tab", 0x0100_0001),
        ("Backspace", 0x0100_0003),
        ("Enter", 0x0100_0004),
        ("ArrowLeft", 0x0100_0012),
        ("ArrowUp", 0x0100_0013),
        ("ArrowRight", 0x0100_0014),
        ("ArrowDown", 0x0100_0015),
        ("KeyZ", 0x5A),
        ("Digit0", 0x30),
        ("F1", 0x0100_0030),
        ("F35", 0x0100_0052),
    ];
    for (code, value) in cases {
        assert_eq!(qt_code(code), Some(value), "{code}");
    }
}

#[test]
fn a_code_with_no_qt_key_value_here_is_none() {
    for code in ["Home", "F0", "F36", "Fx", "Keya", "Digit", "KeyAB"] {
        assert_eq!(qt_code(code), None, "{code}");
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
fn a_key_another_action_holds_fails_and_removes_the_action_it_made() {
    let rig = rig(Answer::Taken, Some(HOUR));

    let (registered, fired) = rig.register("ctrl+alt+space");
    rig.signals(&chord("ctrl+alt+space"), 1);
    let made = rig.close();

    let expected = String::from("ctrl+alt+space: kglobalaccel gave the key to another action");
    assert_eq!(registered, Err(HotkeyError::Registration(expected)));
    let space = "ctrl+alt+space";
    assert_eq!(made, vec![bind(space, 0x0C00_0020), unbind(space)]);
    assert!(fired.try_recv().is_err());
}

#[test]
fn a_failed_call_fails_naming_the_chord_and_the_bus_error() {
    let rig = rig(Answer::Fails, None);

    let (registered, _) = rig.register("ctrl+alt+space");
    let made = rig.close();

    let expected = String::from("ctrl+alt+space: ServiceUnknown");
    assert_eq!(registered, Err(HotkeyError::Registration(expected)));
    assert_eq!(made, vec![bind("ctrl+alt+space", 0x0C00_0020)]);
}

#[test]
fn dropping_the_backend_removes_each_action_it_bound_once() {
    let rig = working();
    rig.register("ctrl+alt+space")
        .0
        .unwrap_or_else(|error| panic!("{error:?}"));
    rig.register("super+a")
        .0
        .unwrap_or_else(|error| panic!("{error:?}"));

    let made = rig.close();

    let removed: Vec<Call> = made
        .into_iter()
        .filter(|call| matches!(call, Call::Unbind(_)))
        .collect();
    assert_eq!(removed, vec![unbind("ctrl+alt+space"), unbind("super+a")]);
}

#[test]
fn with_no_release_a_press_runs_again_only_after_the_gap() {
    for (gap, runs) in [(Duration::ZERO, 3), (HOUR, 1)] {
        let rig = rig(Answer::Given, Some(gap));
        let (_, fired) = rig.register("ctrl+alt+space");

        for _ in 0..3 {
            rig.signal("ctrl+alt+space", true);
        }
        rig.close();

        assert_eq!(fired.try_iter().count(), runs, "{gap:?}");
    }
}

impl HotkeyRig for Rig {
    fn hotkey(&self) -> &dyn Hotkey {
        &self.hotkey
    }

    fn press(&self, chord: &HotkeyChord) {
        self.signals(chord, 1);
    }

    fn hold(&self, chord: &HotkeyChord) {
        self.signals(chord, HELD);
    }

    fn finish(self: Box<Self>) {
        self.close();
    }
}

struct Kde;

impl HotkeySubject for Kde {
    fn listening(&self) -> Box<dyn HotkeyRig> {
        Box::new(rig(Answer::Given, None))
    }

    fn taken(&self) -> Box<dyn HotkeyRig> {
        Box::new(rig(Answer::Taken, None))
    }

    fn broken(&self) -> Box<dyn HotkeyRig> {
        Box::new(rig(Answer::Fails, None))
    }
}

#[test]
fn the_kde_backend_meets_every_hotkey_check() {
    run(&Kde);
}
