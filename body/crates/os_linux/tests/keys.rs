#![cfg(target_os = "linux")]

use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::thread;
use std::time::Duration;

use os_linux::x11rb::errors::{ConnectError, DisplayParsingError};
use os_linux::x11rb::protocol::xproto::{
    GetInputFocusReply, GetKeyboardMappingReply, GetModifierMappingReply, InputFocus, KeyButMask,
    KeyPressEvent, Screen, Setup,
};
use os_linux::x11rb::rust_connection::{DefaultStream, RustConnection};
use os_linux::x11rb::x11_utils::Serialize;
use os_linux::{KeyError, KeyEvent, KeyGrab, Keyboard, X11Keys};

const ROOT: u32 = 0x0000_0100;
const GRAB_KEY: u8 = 33;
const GET_KEYBOARD_MAPPING: u8 = 101;
const GET_MODIFIER_MAPPING: u8 = 119;
const KEY_PRESS: u8 = 2;
const KEY_RELEASE: u8 = 3;
const BAD_ACCESS: u8 = 10;

/// One step of the fake server's script.
enum Step {
    /// Reads one request, then writes these bytes.
    Answer(Vec<u8>),
    /// Writes these bytes without reading.
    Push(Vec<u8>),
    /// Closes the connection.
    Hangup,
}

fn setup() -> Setup {
    let mut setup = Setup {
        status: 1,
        protocol_major_version: 11,
        resource_id_mask: 0x001f_ffff,
        maximum_request_length: u16::MAX,
        min_keycode: 8,
        max_keycode: 10,
        roots: vec![Screen {
            root: ROOT,
            ..Screen::default()
        }],
        ..Setup::default()
    };
    setup.length = u16::try_from((setup.serialize().len() - 8) / 4)
        .unwrap_or_else(|error| panic!("{error:?}"));
    setup
}

fn error(sequence: u16, code: u8, major: u8) -> Vec<u8> {
    let mut error = vec![0_u8; 32];
    error[1] = code;
    error[2..4].copy_from_slice(&sequence.to_le_bytes());
    error[10] = major;
    error
}

fn mapping() -> Vec<u8> {
    GetKeyboardMappingReply {
        keysyms_per_keycode: 2,
        sequence: 1,
        keysyms: vec![0xff1b, 0, 0x61, 0x41, 0xffe9, 0],
    }
    .serialize()
}

fn modifiers() -> Vec<u8> {
    let keycodes = vec![0, 0, 0, 0, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0, 0, 0];
    GetModifierMappingReply {
        sequence: 2,
        length: 4,
        keycodes,
    }
    .serialize()
}

/// The reply to the `GetInputFocus` a checked request is followed by, padded to the 32 bytes
/// every reply has.
fn synced(sequence: u16) -> Vec<u8> {
    let reply = GetInputFocusReply {
        revert_to: InputFocus::POINTER_ROOT,
        sequence,
        length: 0,
        focus: ROOT,
    };
    let mut bytes = reply.serialize().to_vec();
    bytes.resize(32, 0);
    bytes
}

fn key(response_type: u8, detail: u8, state: u16, time: u32) -> Vec<u8> {
    let event = KeyPressEvent {
        response_type,
        detail,
        sequence: 0,
        time,
        root: ROOT,
        event: ROOT,
        child: 0,
        root_x: 0,
        root_y: 0,
        event_x: 0,
        event_y: 0,
        state: KeyButMask::from(state),
        same_screen: true,
    };
    event.serialize().to_vec()
}

fn read_request(peer: &mut UnixStream) -> Vec<u8> {
    let mut request = vec![0_u8; 4];
    peer.read_exact(&mut request)
        .unwrap_or_else(|error| panic!("{error:?}"));
    let words = usize::from(u16::from_le_bytes([request[2], request[3]]));
    request.resize(words * 4, 0);
    peer.read_exact(&mut request[4..])
        .unwrap_or_else(|error| panic!("{error:?}"));
    request
}

/// Serves the handshake and the script, then reads until the client closes, for at most 5 s.
fn serve(mut peer: UnixStream, setup: &Setup, script: Vec<Step>) -> Vec<Vec<u8>> {
    let mut handshake = [0_u8; 12];
    peer.read_exact(&mut handshake)
        .unwrap_or_else(|error| panic!("{error:?}"));
    peer.write_all(&setup.serialize())
        .unwrap_or_else(|error| panic!("{error:?}"));
    let mut requests = Vec::new();
    for step in script {
        let bytes = match step {
            Step::Answer(bytes) => {
                requests.push(read_request(&mut peer));
                bytes
            }
            Step::Push(bytes) => bytes,
            Step::Hangup => return requests,
        };
        peer.write_all(&bytes)
            .unwrap_or_else(|error| panic!("{error:?}"));
    }
    peer.set_read_timeout(Some(Duration::from_secs(5)))
        .unwrap_or_else(|error| panic!("{error:?}"));
    let mut rest = Vec::new();
    peer.read_to_end(&mut rest)
        .unwrap_or_else(|error| panic!("the client did not close: {error:?}"));
    requests
}

fn against<T>(
    screen: usize,
    script: Vec<Step>,
    call: impl FnOnce(&X11Keys) -> T,
) -> (T, Vec<Vec<u8>>) {
    let (ours, theirs) = UnixStream::pair().unwrap_or_else(|error| panic!("{error:?}"));
    let server = thread::spawn(move || serve(theirs, &setup(), script));
    let (stream, _) =
        DefaultStream::from_unix_stream(ours).unwrap_or_else(|error| panic!("{error:?}"));
    let connection =
        RustConnection::connect_to_stream(stream, 0).unwrap_or_else(|error| panic!("{error:?}"));
    let keys = X11Keys::new(connection, screen);
    let result = call(&keys);
    drop(keys);
    (
        result,
        server.join().unwrap_or_else(|error| panic!("{error:?}")),
    )
}

#[test]
fn the_keyboard_is_read_from_both_mappings() {
    let (keyboard, requests) = against(
        0,
        vec![Step::Answer(mapping()), Step::Answer(modifiers())],
        X11Keys::keyboard,
    );

    assert_eq!(
        keyboard,
        Ok(Keyboard {
            min_keycode: 8,
            keysyms_per_keycode: 2,
            keysyms: vec![0xff1b, 0, 0x61, 0x41, 0xffe9, 0],
            modifiers: vec![0, 0, 0, 0, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0, 0, 0],
        })
    );
    assert_eq!(&requests[0][..1], &[GET_KEYBOARD_MAPPING]);
    assert_eq!(&requests[0][4..6], &[8, 3]);
    assert_eq!(&requests[1][..1], &[GET_MODIFIER_MAPPING]);
}

#[test]
fn a_server_that_closes_before_the_key_mapping_fails_the_read() {
    let (keyboard, _) = against(0, vec![Step::Hangup], X11Keys::keyboard);

    assert!(keyboard.is_err(), "{keyboard:?}");
}

#[test]
fn an_x_error_to_the_modifier_mapping_fails_the_read() {
    let bad_implementation = 17;

    let (keyboard, _) = against(
        0,
        vec![
            Step::Answer(mapping()),
            Step::Answer(error(2, bad_implementation, GET_MODIFIER_MAPPING)),
        ],
        X11Keys::keyboard,
    );

    let Err(KeyError(reason)) = keyboard else {
        panic!("expected a failed read, got {keyboard:?}");
    };
    assert!(reason.contains("Implementation"), "{reason}");
}

#[test]
fn a_grab_is_a_passive_asynchronous_grab_on_the_root() {
    let (grabbed, requests) = against(
        0,
        vec![Step::Answer(Vec::new()), Step::Answer(synced(2))],
        |keys| keys.grab(65, 0x0c | 0x10),
    );

    assert_eq!(grabbed, Ok(()));
    let request = &requests[0];
    let not_owner_events = 0;
    let asynchronous = 1;
    assert_eq!(&request[..2], &[GRAB_KEY, not_owner_events]);
    assert_eq!(&request[4..8], &ROOT.to_le_bytes());
    assert_eq!(&request[8..10], &0x1c_u16.to_le_bytes());
    assert_eq!(&request[10..13], &[65, asynchronous, asynchronous]);
}

#[test]
fn a_grab_another_client_holds_is_refused() {
    let (grabbed, _) = against(
        0,
        vec![Step::Answer(error(1, BAD_ACCESS, GRAB_KEY))],
        |keys| keys.grab(65, 0),
    );

    let Err(KeyError(reason)) = grabbed else {
        panic!("expected a refused grab, got {grabbed:?}");
    };
    assert!(reason.contains("Access"), "{reason}");
}

#[test]
fn a_release_is_read_past_other_events() {
    let shift_and_button1 = 0x0101;

    let (released, _) = against(
        0,
        vec![
            Step::Push(error(0, BAD_ACCESS, GRAB_KEY)),
            Step::Push(key(KEY_RELEASE, 65, shift_and_button1, 7)),
        ],
        X11Keys::next_key,
    );

    assert_eq!(
        released,
        Ok(KeyEvent {
            keycode: 65,
            state: shift_and_button1,
            time: 7,
            pressed: false,
        })
    );
}

#[test]
fn a_press_is_read_as_one() {
    let (pressed, _) = against(
        0,
        vec![Step::Push(key(KEY_PRESS, 9, 0x0c, 8))],
        X11Keys::next_key,
    );

    assert_eq!(
        pressed,
        Ok(KeyEvent {
            keycode: 9,
            state: 0x0c,
            time: 8,
            pressed: true,
        })
    );
}

#[test]
fn a_server_that_closes_ends_the_presses() {
    let (pressed, _) = against(0, vec![Step::Hangup], X11Keys::next_key);

    assert!(pressed.is_err(), "{pressed:?}");
}

#[test]
fn a_screen_the_server_does_not_have_fails_every_request() {
    let (results, requests) = against(3, Vec::new(), |keys| {
        (keys.keyboard(), keys.grab(65, 0), keys.next_key())
    });

    let missing = KeyError(String::from("the X server has no screen 3"));
    assert_eq!(
        results,
        (Err(missing.clone()), Err(missing.clone()), Err(missing))
    );
    assert!(requests.is_empty());
}

#[test]
fn a_session_with_no_display_set_fails_every_request() {
    let error = ConnectError::DisplayParsingError(DisplayParsingError::DisplayNotSet);

    let keys = X11Keys::absent(&error);

    let absent = KeyError(error.to_string());
    assert_eq!(keys.keyboard(), Err(absent.clone()));
    assert_eq!(keys.grab(65, 0), Err(absent.clone()));
    assert_eq!(keys.next_key(), Err(absent));
}
