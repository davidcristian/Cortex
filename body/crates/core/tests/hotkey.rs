//! Behavioral tests for `body_core::hotkey` covering every parse branch, every
//! error variant, canonicalization, round-tripping, and the default chord.

use std::cmp::Ordering;

use body_core::{HotkeyChord, HotkeyParseError, Modifier};

#[test]
fn default_chord_is_ctrl_alt_space() {
    let chord = HotkeyChord::default();
    let expected: &[Modifier] = &[Modifier::Ctrl, Modifier::Alt];
    assert_eq!(chord.modifiers(), expected);
    assert_eq!(chord.key(), "space");
    assert_eq!(chord.to_string(), "ctrl+alt+space");
    assert_eq!(HotkeyChord::parse("ctrl+alt+space").unwrap(), chord);
}

#[test]
fn parse_accepts_a_simple_chord() {
    let chord = HotkeyChord::parse("ctrl+shift+f5").unwrap();
    let expected: &[Modifier] = &[Modifier::Ctrl, Modifier::Shift];
    assert_eq!(chord.modifiers(), expected);
    assert_eq!(chord.key(), "f5");
}

#[test]
fn parse_accepts_a_bare_key_without_modifiers() {
    let chord = HotkeyChord::parse("escape").unwrap();
    assert_eq!(chord.modifiers(), &[] as &[Modifier]);
    assert_eq!(chord.key(), "escape");
    assert_eq!(chord.to_string(), "escape");
}

#[test]
fn parse_is_case_insensitive() {
    assert_eq!(
        HotkeyChord::parse("CTRL+ALT+SPACE").unwrap(),
        HotkeyChord::default()
    );
    assert_eq!(
        HotkeyChord::parse("Control+Alt+Space").unwrap(),
        HotkeyChord::default()
    );
    let chord = HotkeyChord::parse("Shift+F5").unwrap();
    assert_eq!(chord.key(), "f5");
}

#[test]
fn parse_trims_whitespace_around_segments() {
    assert_eq!(
        HotkeyChord::parse("  ctrl + alt +  space \t").unwrap(),
        HotkeyChord::default()
    );
}

#[test]
fn parse_resolves_modifier_aliases() {
    let cases = [
        ("control+x", Modifier::Ctrl),
        ("ctrl+x", Modifier::Ctrl),
        ("alt+x", Modifier::Alt),
        ("shift+x", Modifier::Shift),
        ("super+x", Modifier::Super),
        ("win+x", Modifier::Super),
        ("cmd+x", Modifier::Super),
        ("meta+x", Modifier::Super),
    ];
    for (input, modifier) in cases {
        let chord = HotkeyChord::parse(input).unwrap();
        let expected: &[Modifier] = &[modifier];
        assert_eq!(chord.modifiers(), expected, "input: {input}");
        assert_eq!(chord.key(), "x", "input: {input}");
    }
}

#[test]
fn parse_canonicalizes_modifier_order() {
    let chord = HotkeyChord::parse("shift+super+alt+ctrl+k").unwrap();
    let expected: &[Modifier] = &[
        Modifier::Ctrl,
        Modifier::Alt,
        Modifier::Shift,
        Modifier::Super,
    ];
    assert_eq!(chord.modifiers(), expected);
    assert_eq!(chord.to_string(), "ctrl+alt+shift+super+k");
    assert_eq!(
        HotkeyChord::parse("alt+ctrl+space").unwrap(),
        HotkeyChord::default()
    );
}

#[test]
fn parse_display_round_trip_holds() {
    let inputs = [
        "ctrl+alt+space",
        "Shift + F5",
        "SUPER+ALT+ctrl+shift+Z",
        "escape",
        "Win+Tab",
    ];
    for input in inputs {
        let chord = HotkeyChord::parse(input).unwrap();
        let rendered = chord.to_string();
        let reparsed = HotkeyChord::parse(&rendered).unwrap();
        assert_eq!(reparsed, chord, "input: {input}");
        assert_eq!(reparsed.to_string(), rendered, "input: {input}");
    }
}

#[test]
fn parse_rejects_empty_input() {
    assert_eq!(HotkeyChord::parse(""), Err(HotkeyParseError::Empty));
    assert_eq!(HotkeyChord::parse("   \t "), Err(HotkeyParseError::Empty));
}

#[test]
fn parse_rejects_empty_segments() {
    // Empty modifier segment in the middle, at the front, and on its own.
    assert_eq!(
        HotkeyChord::parse("ctrl++space"),
        Err(HotkeyParseError::EmptySegment)
    );
    assert_eq!(
        HotkeyChord::parse("+space"),
        Err(HotkeyParseError::EmptySegment)
    );
    assert_eq!(
        HotkeyChord::parse("ctrl+ +space"),
        Err(HotkeyParseError::EmptySegment)
    );
    assert_eq!(HotkeyChord::parse("+"), Err(HotkeyParseError::EmptySegment));
    // Empty key segment after a trailing separator.
    assert_eq!(
        HotkeyChord::parse("ctrl+"),
        Err(HotkeyParseError::EmptySegment)
    );
    assert_eq!(
        HotkeyChord::parse("ctrl+  "),
        Err(HotkeyParseError::EmptySegment)
    );
}

#[test]
fn parse_rejects_unknown_modifiers() {
    assert_eq!(
        HotkeyChord::parse("foo+space"),
        Err(HotkeyParseError::UnknownModifier(String::from("foo")))
    );
    // The offending segment is reported lowercased.
    assert_eq!(
        HotkeyChord::parse("Fn+alt+space"),
        Err(HotkeyParseError::UnknownModifier(String::from("fn")))
    );
}

#[test]
fn parse_rejects_duplicate_modifiers() {
    assert_eq!(
        HotkeyChord::parse("ctrl+ctrl+space"),
        Err(HotkeyParseError::DuplicateModifier(String::from("ctrl")))
    );
    // Duplicates via aliases are caught too; the second spelling is reported.
    assert_eq!(
        HotkeyChord::parse("ctrl+Control+space"),
        Err(HotkeyParseError::DuplicateModifier(String::from("control")))
    );
    assert_eq!(
        HotkeyChord::parse("win+cmd+x"),
        Err(HotkeyParseError::DuplicateModifier(String::from("cmd")))
    );
}

#[test]
fn parse_rejects_chords_that_end_in_a_modifier() {
    assert_eq!(
        HotkeyChord::parse("ctrl+alt"),
        Err(HotkeyParseError::MissingKey(String::from("alt")))
    );
    // A single bare modifier is a missing key, not a key.
    assert_eq!(
        HotkeyChord::parse("ctrl"),
        Err(HotkeyParseError::MissingKey(String::from("ctrl")))
    );
    // Aliases in key position are still modifiers, case-insensitively.
    assert_eq!(
        HotkeyChord::parse("ctrl+WIN"),
        Err(HotkeyParseError::MissingKey(String::from("win")))
    );
}

#[test]
fn error_messages_are_descriptive() {
    let cases = [
        (HotkeyParseError::Empty, "hotkey chord is empty"),
        (
            HotkeyParseError::EmptySegment,
            "hotkey chord has an empty segment (stray `+`?)",
        ),
        (
            HotkeyParseError::UnknownModifier(String::from("foo")),
            "`foo` is not a modifier (expected ctrl, alt, shift, or super)",
        ),
        (
            HotkeyParseError::DuplicateModifier(String::from("ctrl")),
            "modifier `ctrl` appears more than once in the chord",
        ),
        (
            HotkeyParseError::MissingKey(String::from("alt")),
            "chord ends in modifier `alt` but must end in a key, e.g. `ctrl+alt+space`",
        ),
    ];
    for (error, message) in cases {
        assert_eq!(error.to_string(), message);
    }
}

#[test]
fn error_debug_output_names_the_variant() {
    let cases = [
        (HotkeyParseError::Empty, "Empty"),
        (HotkeyParseError::EmptySegment, "EmptySegment"),
        (
            HotkeyParseError::UnknownModifier(String::from("foo")),
            "UnknownModifier",
        ),
        (
            HotkeyParseError::DuplicateModifier(String::from("ctrl")),
            "DuplicateModifier",
        ),
        (
            HotkeyParseError::MissingKey(String::from("alt")),
            "MissingKey",
        ),
    ];
    for (error, name) in cases {
        let debug = format!("{error:?}");
        assert!(debug.contains(name), "{debug} should contain {name}");
    }
}

#[test]
fn error_equality_compares_variant_and_payload() {
    // Same variant, same payload.
    assert_eq!(
        HotkeyParseError::UnknownModifier(String::from("a")),
        HotkeyParseError::UnknownModifier(String::from("a"))
    );
    let empty = HotkeyParseError::Empty;
    assert_eq!(empty, HotkeyParseError::Empty);
    // Same variant, different payload.
    assert_ne!(
        HotkeyParseError::UnknownModifier(String::from("a")),
        HotkeyParseError::UnknownModifier(String::from("b"))
    );
    assert_ne!(
        HotkeyParseError::DuplicateModifier(String::from("a")),
        HotkeyParseError::DuplicateModifier(String::from("b"))
    );
    assert_ne!(
        HotkeyParseError::MissingKey(String::from("a")),
        HotkeyParseError::MissingKey(String::from("b"))
    );
    // Different variants.
    assert_ne!(HotkeyParseError::Empty, HotkeyParseError::EmptySegment);
}

#[test]
fn modifier_names_and_display_are_canonical_lowercase() {
    let cases = [
        (Modifier::Ctrl, "ctrl"),
        (Modifier::Alt, "alt"),
        (Modifier::Shift, "shift"),
        (Modifier::Super, "super"),
    ];
    for (modifier, name) in cases {
        assert_eq!(modifier.as_str(), name);
        assert_eq!(modifier.to_string(), name);
    }
}

#[test]
fn modifier_debug_output_names_the_variant() {
    assert_eq!(format!("{:?}", Modifier::Ctrl), "Ctrl");
    assert_eq!(format!("{:?}", Modifier::Alt), "Alt");
    assert_eq!(format!("{:?}", Modifier::Shift), "Shift");
    assert_eq!(format!("{:?}", Modifier::Super), "Super");
}

#[test]
#[allow(clippy::clone_on_copy)] // exercises the derived `Clone` impl explicitly
fn modifier_is_copy_clone_eq_and_ordered_canonically() {
    let ctrl = Modifier::Ctrl;
    let copied = ctrl;
    let cloned = ctrl.clone();
    assert_eq!(copied, cloned);
    assert_ne!(Modifier::Ctrl, Modifier::Super);
    assert!(Modifier::Ctrl < Modifier::Alt);
    assert!(Modifier::Alt < Modifier::Shift);
    assert!(Modifier::Shift < Modifier::Super);
    assert_eq!(Modifier::Alt.cmp(&Modifier::Alt), Ordering::Equal);
    assert_eq!(
        Modifier::Super.partial_cmp(&Modifier::Ctrl),
        Some(Ordering::Greater)
    );
    let mut modifiers = [
        Modifier::Super,
        Modifier::Ctrl,
        Modifier::Shift,
        Modifier::Alt,
    ];
    modifiers.sort_unstable();
    assert_eq!(
        modifiers,
        [
            Modifier::Ctrl,
            Modifier::Alt,
            Modifier::Shift,
            Modifier::Super,
        ]
    );
}

#[test]
fn chord_clone_debug_and_equality_behave() {
    let base = HotkeyChord::parse("ctrl+a").unwrap();
    let same = HotkeyChord::parse("ctrl+a").unwrap();
    let different_key = HotkeyChord::parse("ctrl+b").unwrap();
    let different_modifiers = HotkeyChord::parse("alt+a").unwrap();
    assert_eq!(base, same);
    assert_ne!(base, different_key);
    assert_ne!(base, different_modifiers);
    let cloned = base.clone();
    assert_eq!(cloned, base);
    let debug = format!("{base:?}");
    assert!(debug.contains("HotkeyChord"), "{debug}");
    assert!(debug.contains("Ctrl"), "{debug}");
    assert!(debug.contains("\"a\""), "{debug}");
}
