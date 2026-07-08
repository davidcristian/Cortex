//! Behavioral tests for `body_core::os` covering the `Accelerator` chord→code mapping
//! (every supported key kind and the unsupported paths), the `HotkeyError`
//! messages, and a contract-style check that `Hotkey` works as a generic bound
//! through a fake (success fires the callback; failure does not).

use std::cell::RefCell;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, PoisonError};

use body_core::{
    Accelerator, AudioControl, AudioError, Hotkey, HotkeyCallback, HotkeyChord, HotkeyError,
    Modifier, VolumeChange, VolumeState,
};

/// A fake `Hotkey` backend: records the chords it registers and fires the
/// callback once per successful registration; scripted to fail on demand.
/// `RefCell` (not `Mutex`) since the `Hotkey` port requires no `Sync` and the
/// tests are single-threaded. It also keeps `unwrap` out of this non-`#[test]`
/// method, where clippy would deny it.
struct FakeHotkey {
    fail: Option<HotkeyError>,
    registered: RefCell<Vec<String>>,
}

impl Hotkey for FakeHotkey {
    fn register(
        &self,
        chord: &HotkeyChord,
        on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        if let Some(error) = &self.fail {
            return Err(error.clone());
        }
        self.registered.borrow_mut().push(chord.to_string());
        on_activate();
        Ok(())
    }
}

/// Registers through a generic bound, the way the app will.
fn register_via<H: Hotkey>(
    backend: &H,
    chord: &HotkeyChord,
    on_activate: HotkeyCallback,
) -> Result<(), HotkeyError> {
    backend.register(chord, on_activate)
}

#[test]
fn accelerator_maps_supported_keys_to_codes() {
    let cases = [
        ("a", "KeyA"),
        ("z", "KeyZ"),
        ("0", "Digit0"),
        ("9", "Digit9"),
        ("f", "KeyF"),
        ("f1", "F1"),
        ("f24", "F24"),
        ("space", "Space"),
        ("enter", "Enter"),
        ("return", "Enter"),
        ("escape", "Escape"),
        ("esc", "Escape"),
        ("tab", "Tab"),
        ("backspace", "Backspace"),
        ("up", "ArrowUp"),
        ("down", "ArrowDown"),
        ("left", "ArrowLeft"),
        ("right", "ArrowRight"),
    ];
    for (key, code) in cases {
        let chord = HotkeyChord::parse(key).unwrap();
        let accelerator = Accelerator::from_chord(&chord).unwrap();
        assert_eq!(accelerator.code, code, "key {key}");
        assert!(accelerator.modifiers.is_empty(), "key {key}");
    }
}

#[test]
fn accelerator_rejects_unsupported_keys() {
    // Covers the single-char non-alnum path (`-`), an out-of-range f-key
    // (`f0`/`f25`/`f99` parse ok but fail the range check), and a non-numeric f-word
    // (`foo` fails to parse), all falling through to the empty named match.
    for key in ["-", "f0", "f25", "f99", "foo"] {
        let chord = HotkeyChord::parse(key).unwrap();
        assert_eq!(
            Accelerator::from_chord(&chord).unwrap_err(),
            HotkeyError::UnsupportedKey(String::from(key)),
            "key {key}",
        );
    }
}

#[test]
fn accelerator_carries_the_canonical_modifiers() {
    let chord = HotkeyChord::parse("alt+ctrl+space").unwrap();
    let accelerator = Accelerator::from_chord(&chord).unwrap();
    assert_eq!(accelerator.modifiers, vec![Modifier::Ctrl, Modifier::Alt]);
    assert_eq!(accelerator.code, "Space");
}

#[test]
fn accelerator_is_clone_eq_and_debug() {
    let accelerator = Accelerator {
        modifiers: vec![Modifier::Ctrl],
        code: String::from("Space"),
    };
    assert_eq!(accelerator.clone(), accelerator);
    assert_ne!(
        accelerator,
        Accelerator {
            modifiers: Vec::new(),
            code: String::from("Space"),
        }
    );
    assert!(format!("{accelerator:?}").contains("Accelerator"));
}

#[test]
fn hotkey_error_messages_and_debug() {
    assert_eq!(
        HotkeyError::UnsupportedKey(String::from("f99")).to_string(),
        "hotkey key `f99` is not supported",
    );
    assert_eq!(
        HotkeyError::Registration(String::from("taken")).to_string(),
        "registering the hotkey failed: taken",
    );
    let unsupported = HotkeyError::UnsupportedKey(String::from("x"));
    assert!(format!("{unsupported:?}").contains("UnsupportedKey"));
    assert_ne!(unsupported, HotkeyError::Registration(String::from("x")));
}

#[test]
fn hotkey_backend_registers_and_fires_the_callback() {
    let backend = FakeHotkey {
        fail: None,
        registered: RefCell::new(Vec::new()),
    };
    let hits = Arc::new(AtomicUsize::new(0));
    let hits_cb = Arc::clone(&hits);
    register_via(
        &backend,
        &HotkeyChord::default(),
        Box::new(move || {
            hits_cb.fetch_add(1, Ordering::SeqCst);
        }),
    )
    .unwrap();
    assert_eq!(hits.load(Ordering::SeqCst), 1);
    assert_eq!(backend.registered.borrow().as_slice(), ["ctrl+alt+space"],);
}

#[test]
fn hotkey_backend_reports_registration_failure_without_firing() {
    let backend = FakeHotkey {
        fail: Some(HotkeyError::Registration(String::from("taken"))),
        registered: RefCell::new(Vec::new()),
    };
    let hits = Arc::new(AtomicUsize::new(0));
    let hits_cb = Arc::clone(&hits);
    let error = register_via(
        &backend,
        &HotkeyChord::default(),
        Box::new(move || {
            hits_cb.fetch_add(1, Ordering::SeqCst);
        }),
    )
    .unwrap_err();
    assert_eq!(error, HotkeyError::Registration(String::from("taken")));
    assert_eq!(hits.load(Ordering::SeqCst), 0);
    assert!(backend.registered.borrow().is_empty());
}

/// A fake `AudioControl` backend: reads/writes a `Mutex`-held state (the port requires
/// `Send + Sync`, so (unlike `FakeHotkey`'s `RefCell`) the interior mutability is a `Mutex`),
/// or returns a scripted error.
struct FakeAudio {
    state: Mutex<VolumeState>,
    fail: Option<AudioError>,
}

impl AudioControl for FakeAudio {
    fn get_volume(&self) -> Result<VolumeState, AudioError> {
        if let Some(error) = &self.fail {
            return Err(error.clone());
        }
        Ok(*self.state.lock().unwrap_or_else(PoisonError::into_inner))
    }

    fn set_volume(&self, change: VolumeChange) -> Result<VolumeState, AudioError> {
        if let Some(error) = &self.fail {
            return Err(error.clone());
        }
        let mut state = self.state.lock().unwrap_or_else(PoisonError::into_inner);
        if let Some(level) = change.level {
            state.level = level;
        }
        if let Some(mute) = change.mute {
            state.muted = mute;
        }
        Ok(*state)
    }
}

/// Reads through a generic bound, the way the `BodyService` server does.
fn get_via<A: AudioControl>(backend: &A) -> Result<VolumeState, AudioError> {
    backend.get_volume()
}

/// Writes through a generic bound.
fn set_via<A: AudioControl>(backend: &A, change: VolumeChange) -> Result<VolumeState, AudioError> {
    backend.set_volume(change)
}

#[test]
fn audio_backend_reads_and_writes_through_the_bound() {
    let backend = FakeAudio {
        state: Mutex::new(VolumeState {
            level: 0.4,
            muted: false,
        }),
        fail: None,
    };
    assert_eq!(
        get_via(&backend).unwrap(),
        VolumeState {
            level: 0.4,
            muted: false,
        },
    );
    // Level and mute both set.
    assert_eq!(
        set_via(&backend, VolumeChange::new(Some(0.9), Some(true))).unwrap(),
        VolumeState {
            level: 0.9,
            muted: true,
        },
    );
    // A None field leaves that dimension untouched (mute changes, level stays 0.9).
    assert_eq!(
        set_via(&backend, VolumeChange::new(None, Some(false))).unwrap(),
        VolumeState {
            level: 0.9,
            muted: false,
        },
    );
}

#[test]
fn audio_backend_surfaces_its_error() {
    let backend = FakeAudio {
        state: Mutex::new(VolumeState {
            level: 0.5,
            muted: false,
        }),
        fail: Some(AudioError::NoEndpoint(String::from("no device"))),
    };
    assert_eq!(
        get_via(&backend).unwrap_err(),
        AudioError::NoEndpoint(String::from("no device")),
    );
    assert_eq!(
        set_via(&backend, VolumeChange::new(Some(0.1), None)).unwrap_err(),
        AudioError::NoEndpoint(String::from("no device")),
    );
}

#[test]
fn volume_change_clamps_a_present_level() {
    // Both fields set; in-range level is preserved.
    assert_eq!(
        VolumeChange::new(Some(0.5), Some(true)),
        VolumeChange {
            level: Some(0.5),
            mute: Some(true),
        },
    );
    // Out-of-range clamps to the nearest bound; NaN clamps to the silent floor.
    assert_eq!(VolumeChange::new(Some(1.5), None).level, Some(1.0));
    assert_eq!(VolumeChange::new(Some(-0.2), None).level, Some(0.0));
    assert_eq!(VolumeChange::new(Some(f32::NAN), None).level, Some(0.0));
    // A missing level stays absent; mute rides alone.
    assert_eq!(
        VolumeChange::new(None, Some(false)),
        VolumeChange {
            level: None,
            mute: Some(false),
        },
    );
}

#[test]
fn volume_values_are_debug_and_eq() {
    let state = VolumeState {
        level: 0.3,
        muted: true,
    };
    assert!(format!("{state:?}").contains("VolumeState"));
    assert_ne!(
        state,
        VolumeState {
            level: 0.3,
            muted: false,
        },
    );
    let change = VolumeChange::new(Some(0.3), None);
    assert!(format!("{change:?}").contains("VolumeChange"));
}

#[test]
fn audio_error_messages_and_debug() {
    assert_eq!(
        AudioError::NoEndpoint(String::from("no device")).to_string(),
        "no audio output endpoint is available: no device",
    );
    assert_eq!(
        AudioError::Backend(String::from("COM 0x1")).to_string(),
        "the audio backend failed: COM 0x1",
    );
    let error = AudioError::Backend(String::from("x"));
    assert!(format!("{error:?}").contains("Backend"));
    assert_ne!(error, AudioError::NoEndpoint(String::from("x")));
}
