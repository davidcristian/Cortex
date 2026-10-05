#![cfg(target_os = "linux")]

use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use body_contract::hotkey::{HotkeyRig, HotkeySubject, run};
use body_core::{Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};
use os_linux::{KeyError, KeyEvent, KeyGrab, Keyboard, LinuxHotkey, keysym};

const ESCAPE: u8 = 9;
const A: u8 = 10;
const SPACE: u8 = 14;
const ONE: u8 = 15;
const SHIFT: u16 = 1;
const LOCK: u16 = 2;
const CONTROL: u16 = 4;
const MOD1: u16 = 8;
const MOD2: u16 = 16;
const MOD4: u16 = 64;
const BUTTON1: u16 = 256;

/// A US-like keyboard: Alt on Mod1, Num Lock on Mod2, Super on Mod4, two keycodes per modifier.
fn keyboard() -> Keyboard {
    let keysyms = [
        [0, 0],
        [0xff1b, 0],
        [0x61, 0x41],
        [0xffe9, 0xffe7],
        [0xffeb, 0],
        [0xff7f, 0],
        [0x20, 0],
        [0x31, 0x21],
        [0xffc2, 0],
        [0xffe3, 0],
        [0xffe1, 0],
        [0xffe5, 0],
    ];
    Keyboard {
        min_keycode: 8,
        keysyms_per_keycode: 2,
        keysyms: keysyms.concat(),
        modifiers: vec![18, 0, 19, 0, 17, 0, 11, 0, 13, 0, 0, 0, 12, 0, 0, 0],
    }
}

fn without_modifier(row: usize) -> Keyboard {
    let mut keyboard = keyboard();
    keyboard.modifiers[row * 2] = 0;
    keyboard
}

struct FakeKeys {
    keyboard: Result<Keyboard, KeyError>,
    refused: Option<u16>,
    grabs: Arc<Mutex<Vec<(u8, u16)>>>,
    presses: Mutex<Receiver<KeyEvent>>,
    _alive: Arc<()>,
}

impl KeyGrab for FakeKeys {
    fn keyboard(&self) -> Result<Keyboard, KeyError> {
        self.keyboard.clone()
    }

    fn grab(&self, keycode: u8, modifiers: u16) -> Result<(), KeyError> {
        self.grabs
            .lock()
            .unwrap_or_else(|error| panic!("{error:?}"))
            .push((keycode, modifiers));
        if self.refused == Some(modifiers) {
            return Err(KeyError(String::from("BadAccess")));
        }
        Ok(())
    }

    fn next_key(&self) -> Result<KeyEvent, KeyError> {
        self.presses
            .lock()
            .unwrap_or_else(|error| panic!("{error:?}"))
            .recv()
            .map_err(|error| KeyError(error.to_string()))
    }
}

struct Rig {
    hotkey: LinuxHotkey,
    grabs: Arc<Mutex<Vec<(u8, u16)>>>,
    presses: Sender<KeyEvent>,
    alive: Arc<()>,
}

fn rig(keyboard: Result<Keyboard, KeyError>, refused: Option<u16>) -> Rig {
    let grabs = Arc::new(Mutex::new(Vec::new()));
    let (presses, received) = mpsc::channel();
    let alive = Arc::new(());
    let hotkey = LinuxHotkey::new(FakeKeys {
        keyboard,
        refused,
        grabs: Arc::clone(&grabs),
        presses: Mutex::new(received),
        _alive: Arc::clone(&alive),
    });
    Rig {
        hotkey,
        grabs,
        presses,
        alive,
    }
}

impl Rig {
    fn grabs(&self) -> Vec<(u8, u16)> {
        self.grabs
            .lock()
            .unwrap_or_else(|error| panic!("{error:?}"))
            .clone()
    }

    fn register(&self, chord: &str) -> (Result<(), HotkeyError>, Receiver<()>) {
        let (fired, on_fire) = mpsc::channel();
        let callback: HotkeyCallback = Box::new(move || {
            fired.send(()).unwrap_or_else(|error| panic!("{error:?}"));
        });
        let chord = HotkeyChord::parse(chord).unwrap_or_else(|error| panic!("{error:?}"));
        (self.hotkey.register(&chord, callback), on_fire)
    }

    fn key(&self, keycode: u8, state: u16, time: u32, pressed: bool) {
        self.presses
            .send(KeyEvent {
                keycode,
                state,
                time,
                pressed,
            })
            .unwrap_or_else(|error| panic!("{error:?}"));
    }

    fn press(&self, keycode: u8, state: u16) {
        self.key(keycode, state, 0, true);
    }

    /// Ends the listener and waits for it to drop the fake, so every event sent has been read.
    fn close(self) {
        let Self {
            hotkey,
            presses,
            alive,
            ..
        } = self;
        drop(presses);
        drop(hotkey);
        let deadline = Instant::now() + Duration::from_secs(5);
        while Arc::strong_count(&alive) > 1 {
            assert!(Instant::now() < deadline, "the listener did not end");
            thread::sleep(Duration::from_millis(5));
        }
    }
}

#[test]
fn a_chord_grabs_its_key_with_every_lock_combination() {
    let rig = rig(Ok(keyboard()), None);

    let (registered, _) = rig.register("ctrl+alt+space");

    assert_eq!(registered, Ok(()));
    let chord = CONTROL | MOD1;
    assert_eq!(
        rig.grabs(),
        vec![
            (SPACE, chord),
            (SPACE, chord | LOCK),
            (SPACE, chord | MOD2),
            (SPACE, chord | LOCK | MOD2)
        ]
    );
}

#[test]
fn super_and_shift_take_their_bits_from_the_keyboard() {
    let rig = rig(Ok(keyboard()), None);

    let (letter, _) = rig.register("super+a");
    let (digit, _) = rig.register("shift+1");

    assert_eq!((letter, digit), (Ok(()), Ok(())));
    let grabs = rig.grabs();
    assert_eq!(grabs[0], (A, MOD4));
    assert_eq!(grabs[4], (ONE, SHIFT));
    assert_eq!(grabs.len(), 8);
}

#[test]
fn a_keyboard_without_num_lock_grabs_only_the_caps_lock_variant() {
    let rig = rig(Ok(without_modifier(4)), None);

    let (registered, _) = rig.register("escape");

    assert_eq!(registered, Ok(()));
    assert_eq!(rig.grabs(), vec![(ESCAPE, 0), (ESCAPE, LOCK)]);
}

#[test]
fn a_key_with_no_code_is_unsupported_before_any_request() {
    let rig = rig(Err(KeyError(String::from("unread"))), None);

    let (registered, _) = rig.register("ctrl+home");

    assert_eq!(
        registered,
        Err(HotkeyError::UnsupportedKey(String::from("home")))
    );
    assert!(rig.grabs().is_empty());
}

#[test]
fn a_key_the_keyboard_does_not_have_is_refused_without_a_grab() {
    let rig = rig(Ok(keyboard()), None);

    let (registered, _) = rig.register("ctrl+f6");

    assert_eq!(
        registered,
        Err(HotkeyError::Registration(String::from(
            "no key on this keyboard types ctrl+f6"
        )))
    );
    assert!(rig.grabs().is_empty());
}

#[test]
fn a_failed_keyboard_read_is_a_registration_error() {
    let rig = rig(Err(KeyError(String::from("DISPLAY not set"))), None);

    let (registered, _) = rig.register("ctrl+alt+space");

    assert_eq!(
        registered,
        Err(HotkeyError::Registration(String::from(
            "ctrl+alt+space: DISPLAY not set"
        )))
    );
}

#[test]
fn a_modifier_no_key_holds_is_refused_without_a_grab() {
    for (row, chord, name) in [(3, "alt+space", "Alt"), (6, "super+space", "Super")] {
        let rig = rig(Ok(without_modifier(row)), None);

        let (registered, _) = rig.register(chord);

        assert_eq!(
            registered,
            Err(HotkeyError::Registration(format!(
                "no modifier on this keyboard is {name}"
            )))
        );
        assert!(rig.grabs().is_empty());
    }
}

#[test]
fn a_refused_grab_fails_the_registration_and_stops_grabbing() {
    let rig = rig(Ok(keyboard()), Some(CONTROL | LOCK));

    let (registered, _) = rig.register("ctrl+space");

    assert_eq!(
        registered,
        Err(HotkeyError::Registration(String::from(
            "ctrl+space: BadAccess"
        )))
    );
    assert_eq!(rig.grabs(), vec![(SPACE, CONTROL), (SPACE, CONTROL | LOCK)]);
}

#[test]
fn a_press_runs_the_callback_whatever_locks_or_buttons_are_held() {
    let rig = rig(Ok(keyboard()), None);
    let (_, fired) = rig.register("ctrl+alt+space");
    let chord = CONTROL | MOD1;

    rig.press(SPACE, chord);
    rig.press(A, chord);
    rig.press(SPACE, chord | SHIFT);
    rig.press(SPACE, chord | LOCK | MOD2 | BUTTON1);
    rig.close();

    assert_eq!(fired.try_iter().count(), 2);
}

#[test]
fn each_press_runs_only_its_own_chords_callback() {
    let rig = rig(Ok(keyboard()), None);
    let (_, space) = rig.register("ctrl+alt+space");
    let (_, letter) = rig.register("super+a");

    rig.press(A, MOD4);
    rig.close();

    assert_eq!(space.try_iter().count(), 0);
    assert_eq!(letter.try_iter().count(), 1);
}

#[test]
fn every_named_code_has_its_keysym() {
    let named = [
        ("Space", 0x0020),
        ("Enter", 0xff0d),
        ("Escape", 0xff1b),
        ("Tab", 0xff09),
        ("Backspace", 0xff08),
        ("ArrowUp", 0xff52),
        ("ArrowDown", 0xff54),
        ("ArrowLeft", 0xff51),
        ("ArrowRight", 0xff53),
    ];
    for (code, expected) in named {
        assert_eq!(keysym(code), Some(expected), "{code}");
    }
}

#[test]
fn letters_digits_and_function_keys_map_by_their_position() {
    let mapped = [
        ("KeyA", 0x61),
        ("KeyZ", 0x7a),
        ("Digit0", 0x30),
        ("Digit9", 0x39),
        ("F1", 0xffbe),
        ("F24", 0xffd5),
        ("F35", 0xffe0),
    ];
    for (code, expected) in mapped {
        assert_eq!(keysym(code), Some(expected), "{code}");
    }
}

#[test]
fn a_code_with_no_keysym_here_is_none() {
    for code in [
        "Keya", "Key1", "DigitA", "F0", "F36", "Fx", "F", "Numpad1", "",
    ] {
        assert_eq!(keysym(code), None, "{code}");
    }
}

#[test]
fn an_auto_repeat_runs_the_callback_once_and_a_new_press_again() {
    let rig = rig(Ok(keyboard()), None);
    let (_, space) = rig.register("ctrl+space");
    let (_, letter) = rig.register("ctrl+a");

    rig.key(SPACE, CONTROL, 100, true);
    rig.key(SPACE, CONTROL, 600, false);
    rig.key(SPACE, CONTROL, 600, true);
    rig.key(SPACE, CONTROL, 640, false);
    rig.key(SPACE, CONTROL, 640, true);
    rig.key(SPACE, CONTROL, 650, false);
    rig.key(A, CONTROL, 650, true);
    rig.key(SPACE, CONTROL, 650, true);
    rig.key(SPACE, CONTROL, 820, false);
    rig.key(SPACE, CONTROL, 900, true);
    rig.close();

    assert_eq!(space.try_iter().count(), 3);
    assert_eq!(letter.try_iter().count(), 1);
}

#[test]
fn a_release_alone_runs_nothing() {
    let rig = rig(Ok(keyboard()), None);
    let (_, fired) = rig.register("ctrl+space");

    rig.key(SPACE, CONTROL, 100, false);
    rig.close();

    assert_eq!(fired.try_iter().count(), 0);
}

/// The key and modifier state a press of each chord the shared list names sends on [`keyboard`].
const PRESSES: [(&str, u8, u16); 4] = [
    ("ctrl+alt+space", SPACE, CONTROL | MOD1),
    ("super+a", A, MOD4),
    ("super+1", ONE, MOD4),
    ("shift+1", ONE, SHIFT),
];

impl HotkeyRig for Rig {
    fn hotkey(&self) -> &dyn Hotkey {
        &self.hotkey
    }

    fn press(&self, chord: &HotkeyChord) {
        let name = chord.to_string();
        PRESSES
            .iter()
            .filter(|(pressed, _, _)| *pressed == name)
            .for_each(|&(_, keycode, state)| Self::press(self, keycode, state));
    }

    fn hold(&self, chord: &HotkeyChord) {
        let name = chord.to_string();
        for &(_, keycode, state) in PRESSES.iter().filter(|(held, _, _)| *held == name) {
            self.key(keycode, state, 100, true);
            for time in [700, 740, 780] {
                self.key(keycode, state, time, false);
                self.key(keycode, state, time, true);
            }
            self.key(keycode, state, 800, false);
        }
    }

    fn finish(self: Box<Self>) {
        self.close();
    }
}

struct Linux;

impl HotkeySubject for Linux {
    fn listening(&self) -> Box<dyn HotkeyRig> {
        Box::new(rig(Ok(keyboard()), None))
    }

    fn taken(&self) -> Box<dyn HotkeyRig> {
        Box::new(rig(Ok(keyboard()), Some(CONTROL | MOD1)))
    }

    fn broken(&self) -> Box<dyn HotkeyRig> {
        Box::new(rig(Err(KeyError(String::from("DISPLAY not set"))), None))
    }
}

#[test]
fn the_linux_backend_meets_every_hotkey_check() {
    run(&Linux);
}
