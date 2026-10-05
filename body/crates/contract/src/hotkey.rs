//! The `Hotkey` check list: what every hotkey backend owes, read through the port and a press.

use std::mem::{Discriminant, discriminant};
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use body_core::{Hotkey, HotkeyCallback, HotkeyChord, HotkeyError};

/// A hotkey backend and the keyboard it listens to.
pub trait HotkeyRig {
    /// The implementation under test.
    fn hotkey(&self) -> &dyn Hotkey;

    /// Presses `chord` once on the keyboard the backend listens to.
    fn press(&self, chord: &HotkeyChord);

    /// Presses `chord` and holds it until the keyboard has sent auto-repeats, then releases it.
    fn hold(&self, chord: &HotkeyChord);

    /// Ends the backend once every press so far has reached it.
    fn finish(self: Box<Self>);
}

/// Builds the implementation under test in each condition a check needs.
pub trait HotkeySubject {
    /// A backend on a keyboard with every key and modifier [`CHORDS`] names.
    fn listening(&self) -> Box<dyn HotkeyRig>;

    /// A backend where another program holds [`HotkeyChord::default`], so registering it fails.
    fn taken(&self) -> Box<dyn HotkeyRig>;

    /// A backend that fails every registration for any other reason.
    fn broken(&self) -> Box<dyn HotkeyRig>;
}

/// One check and its name, run against a subject.
pub type HotkeyCheck = (&'static str, fn(&dyn HotkeySubject));

/// Every check a hotkey backend owes, in the order a driver runs them.
pub const HOTKEY_CHECKS: [HotkeyCheck; 7] = named![fn(&dyn HotkeySubject);
    a_press_runs_the_callback_once,
    a_held_chord_runs_the_callback_once,
    registering_runs_nothing_until_a_press,
    each_press_runs_only_its_own_chords_callback,
    a_key_with_no_code_is_unsupported,
    a_taken_chord_fails_and_never_runs,
    a_broken_backend_fails_as_a_registration_error,
];

/// Runs every check against `subject`, naming each on stderr first so a failure shows which.
pub fn run(subject: &dyn HotkeySubject) {
    for (name, check) in HOTKEY_CHECKS {
        eprintln!("hotkey check: {name}");
        check(subject);
    }
}

/// The chords the checks name besides the default: two keys under one modifier, the second key
/// under another, and a key with no code.
pub const CHORDS: [&str; 4] = ["super+a", "super+1", "shift+1", "ctrl+home"];

fn chords() -> Vec<HotkeyChord> {
    let parsed: Vec<HotkeyChord> = CHORDS.into_iter().flat_map(HotkeyChord::parse).collect();
    assert_eq!(parsed.len(), CHORDS.len(), "every fixture chord parses");
    parsed
}

/// A callback and the count of its runs.
fn counted() -> (Arc<AtomicUsize>, HotkeyCallback) {
    let runs = Arc::new(AtomicUsize::new(0));
    let counter = Arc::clone(&runs);
    let callback = Box::new(move || {
        counter.fetch_add(1, Ordering::SeqCst);
    });
    (runs, callback)
}

fn runs(count: &AtomicUsize) -> usize {
    count.load(Ordering::SeqCst)
}

/// Which error a call failed with, without its text, which each backend writes its own way.
fn kind(result: &Result<(), HotkeyError>) -> Option<Discriminant<HotkeyError>> {
    result.as_ref().err().map(discriminant)
}

fn refused() -> Discriminant<HotkeyError> {
    discriminant(&HotkeyError::Registration(String::new()))
}

fn a_press_runs_the_callback_once(subject: &dyn HotkeySubject) {
    let rig = subject.listening();
    let (count, callback) = counted();
    let chord = HotkeyChord::default();
    assert_eq!(kind(&rig.hotkey().register(&chord, callback)), None);
    for _ in 0..3 {
        rig.press(&chord);
    }
    rig.finish();
    assert_eq!(runs(&count), 3);
}

fn a_held_chord_runs_the_callback_once(subject: &dyn HotkeySubject) {
    let rig = subject.listening();
    let (count, callback) = counted();
    let chord = HotkeyChord::default();
    assert_eq!(kind(&rig.hotkey().register(&chord, callback)), None);
    rig.hold(&chord);
    rig.press(&chord);
    rig.finish();
    assert_eq!(runs(&count), 2);
}

fn registering_runs_nothing_until_a_press(subject: &dyn HotkeySubject) {
    let rig = subject.listening();
    let (count, callback) = counted();
    assert_eq!(
        kind(&rig.hotkey().register(&HotkeyChord::default(), callback)),
        None
    );
    rig.finish();
    assert_eq!(runs(&count), 0);
}

fn each_press_runs_only_its_own_chords_callback(subject: &dyn HotkeySubject) {
    let chords = chords();
    let rig = subject.listening();
    let (letter, on_letter) = counted();
    let (digit, on_digit) = counted();
    assert_eq!(kind(&rig.hotkey().register(&chords[0], on_letter)), None);
    assert_eq!(kind(&rig.hotkey().register(&chords[1], on_digit)), None);
    for pressed in [0, 2, 0, 1] {
        rig.press(&chords[pressed]);
    }
    rig.press(&HotkeyChord::default());
    rig.finish();
    assert_eq!((runs(&letter), runs(&digit)), (2, 1));
}

fn a_key_with_no_code_is_unsupported(subject: &dyn HotkeySubject) {
    let rig = subject.listening();
    let (count, callback) = counted();
    let unsupported = Some(discriminant(&HotkeyError::UnsupportedKey(String::new())));
    assert_eq!(
        kind(&rig.hotkey().register(&chords()[3], callback)),
        unsupported
    );
    rig.finish();
    assert_eq!(runs(&count), 0);
}

fn a_taken_chord_fails_and_never_runs(subject: &dyn HotkeySubject) {
    let rig = subject.taken();
    let (count, callback) = counted();
    let chord = HotkeyChord::default();
    assert_eq!(
        kind(&rig.hotkey().register(&chord, callback)),
        Some(refused())
    );
    rig.press(&chord);
    rig.finish();
    assert_eq!(runs(&count), 0);
}

fn a_broken_backend_fails_as_a_registration_error(subject: &dyn HotkeySubject) {
    let rig = subject.broken();
    let (_, callback) = counted();
    let result = rig.hotkey().register(&HotkeyChord::default(), callback);
    assert_eq!(kind(&result), Some(refused()));
    rig.finish();
}
