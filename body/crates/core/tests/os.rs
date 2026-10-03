use body_core::{
    Accelerator, AudioError, HotkeyChord, HotkeyError, Modifier, VolumeChange, VolumeState,
};

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
fn accelerator_has_the_canonical_modifiers() {
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
fn volume_change_clamps_a_present_level() {
    assert_eq!(
        VolumeChange::new(Some(0.5), Some(true)),
        VolumeChange {
            level: Some(0.5),
            mute: Some(true),
        },
    );
    assert_eq!(VolumeChange::new(Some(1.5), None).level, Some(1.0));
    assert_eq!(VolumeChange::new(Some(-0.2), None).level, Some(0.0));
    assert_eq!(VolumeChange::new(Some(f32::NAN), None).level, Some(0.0));
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
