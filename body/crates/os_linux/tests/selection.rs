#![cfg(target_os = "linux")]

use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::thread;
use std::time::Duration;

use os_linux::x11rb::errors::{ConnectError, DisplayParsingError};
use os_linux::x11rb::protocol::xproto::{
    GetAtomNameReply, GetPropertyReply, InternAtomReply, Property, PropertyNotifyEvent, Screen,
    SelectionNotifyEvent, Setup,
};
use os_linux::x11rb::rust_connection::{DefaultStream, RustConnection};
use os_linux::x11rb::x11_utils::Serialize;
use os_linux::{SELECTION_LIMIT, SelectionError, SelectionRead, X11Selection};

const ROOT: u32 = 0x0000_0100;
const WINDOW: u32 = 0x0040_0000;
const OTHER: u32 = 0x0060_0001;
const CLIPBOARD: u32 = 300;
const PNG: u32 = 301;
const PROPERTY: u32 = 302;
const INCR: u32 = 303;
const CREATE_WINDOW: u8 = 1;
const DESTROY_WINDOW: u8 = 4;
const INTERN_ATOM: u8 = 16;
const GET_PROPERTY: u8 = 20;
const CONVERT_SELECTION: u8 = 24;
const BAD_WINDOW: u8 = 3;
const LIMIT: usize = 64;

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
        resource_id_base: WINDOW,
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

fn padded(mut bytes: Vec<u8>) -> Vec<u8> {
    bytes.resize(bytes.len().max(32), 0);
    bytes
}

fn intern(sequence: u16, atom: u32) -> Step {
    let reply = InternAtomReply {
        sequence,
        length: 0,
        atom,
    };
    Step::Answer(padded(reply.serialize().to_vec()))
}

/// The answers to the four names every read interns, the first four requests on a connection.
fn interned() -> Vec<Step> {
    vec![
        intern(1, CLIPBOARD),
        intern(2, PNG),
        intern(3, PROPERTY),
        intern(4, INCR),
    ]
}

fn notify(sequence: u16, requestor: u32, property: u32) -> Vec<u8> {
    let event = SelectionNotifyEvent {
        response_type: 31,
        sequence,
        time: 0,
        requestor,
        selection: CLIPBOARD,
        target: PNG,
        property,
    };
    padded(event.serialize().to_vec())
}

fn changed(sequence: u16, window: u32, state: Property) -> Step {
    let event = PropertyNotifyEvent {
        response_type: 28,
        sequence,
        window,
        atom: PROPERTY,
        time: 0,
        state,
    };
    Step::Push(padded(event.serialize().to_vec()))
}

fn property(sequence: u16, type_: u32, value: &[u8], bytes_after: u32) -> Step {
    let mut value = value.to_vec();
    let value_len = u32::try_from(value.len()).unwrap_or_else(|error| panic!("{error:?}"));
    value.resize(value.len().div_ceil(4) * 4, 0);
    let reply = GetPropertyReply {
        format: 8,
        sequence,
        length: u32::try_from(value.len() / 4).unwrap_or_else(|error| panic!("{error:?}")),
        type_,
        bytes_after,
        value_len,
        value: value[..usize::try_from(value_len).unwrap_or(0)].to_vec(),
    };
    let mut bytes = reply.serialize();
    bytes.resize(32 + value.len(), 0);
    Step::Answer(bytes)
}

fn error(sequence: u16, code: u8, major: u8) -> Vec<u8> {
    let mut error = vec![0_u8; 32];
    error[1] = code;
    error[2..4].copy_from_slice(&sequence.to_le_bytes());
    error[10] = major;
    error
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
fn serve(mut peer: UnixStream, script: Vec<Step>) -> Vec<Vec<u8>> {
    let mut handshake = [0_u8; 12];
    peer.read_exact(&mut handshake)
        .unwrap_or_else(|error| panic!("{error:?}"));
    peer.write_all(&setup().serialize())
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

type Converted = Result<Option<Vec<u8>>, SelectionError>;

fn against(screen: usize, patience: Duration, script: Vec<Step>) -> (Converted, Vec<Vec<u8>>) {
    against_with(screen, patience, script, |selection| {
        selection.convert("image/png", LIMIT)
    })
}

fn against_with<T>(
    screen: usize,
    patience: Duration,
    script: Vec<Step>,
    call: impl FnOnce(&X11Selection) -> T,
) -> (T, Vec<Vec<u8>>) {
    let (ours, theirs) = UnixStream::pair().unwrap_or_else(|error| panic!("{error:?}"));
    let server = thread::spawn(move || serve(theirs, script));
    let (stream, _) =
        DefaultStream::from_unix_stream(ours).unwrap_or_else(|error| panic!("{error:?}"));
    let connection =
        RustConnection::connect_to_stream(stream, 0).unwrap_or_else(|error| panic!("{error:?}"));
    let selection = if patience == SELECTION_LIMIT {
        X11Selection::new(connection, screen)
    } else {
        X11Selection::with_limit(connection, screen, patience)
    };
    let result = call(&selection);
    drop(selection);
    (
        result,
        server.join().unwrap_or_else(|error| panic!("{error:?}")),
    )
}

/// A script that interns the names, creates the window and has the owner write to `property`.
fn converted(property: u32) -> Vec<Step> {
    let mut script = interned();
    script.push(Step::Answer(Vec::new()));
    script.push(Step::Answer(notify(6, WINDOW, property)));
    script
}

fn words(bytes: &[u8]) -> u32 {
    u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]])
}

#[test]
fn a_picture_is_read_whole_through_a_window_of_its_own() {
    let mut script = converted(PROPERTY);
    script.push(property(7, PNG, b"\x89PNG", 0));
    script.push(Step::Answer(Vec::new()));

    let (read, requests) = against(0, SELECTION_LIMIT, script);

    assert_eq!(read, Ok(Some(b"\x89PNG".to_vec())));
    let names: Vec<&[u8]> = requests[..4]
        .iter()
        .map(|request| {
            assert_eq!(request[0], INTERN_ATOM);
            let length = usize::from(u16::from_le_bytes([request[4], request[5]]));
            &request[8..8 + length]
        })
        .collect();
    let wanted: [&[u8]; 4] = [b"CLIPBOARD", b"image/png", b"CORTEX_PASTE", b"INCR"];
    assert_eq!(names, wanted);
    let create = &requests[4];
    let input_only = 2_u16;
    let event_mask_bit = 0x0800;
    let property_change = 0x0040_0000;
    assert_eq!(create[0], CREATE_WINDOW);
    assert_eq!((words(&create[4..]), words(&create[8..])), (WINDOW, ROOT));
    assert_eq!(&create[22..24], &input_only.to_le_bytes());
    assert_eq!(
        (words(&create[28..]), words(&create[32..])),
        (event_mask_bit, property_change)
    );
    let convert = &requests[5];
    assert_eq!(convert[0], CONVERT_SELECTION);
    let fields: Vec<u32> = (1..6).map(|word| words(&convert[word * 4..])).collect();
    assert_eq!(fields, [WINDOW, CLIPBOARD, PNG, PROPERTY, 0]);
    let get = &requests[6];
    let (delete, any_type, offset) = (1, 0, 0);
    assert_eq!(&get[..2], &[GET_PROPERTY, delete]);
    let fields: Vec<u32> = (1..6).map(|word| words(&get[word * 4..])).collect();
    let room = u32::try_from(LIMIT / 4 + 1).unwrap_or(0);
    assert_eq!(fields, [WINDOW, PROPERTY, any_type, offset, room]);
    assert_eq!(requests[7][0], DESTROY_WINDOW);
    assert_eq!(words(&requests[7][4..]), WINDOW);
}

#[test]
fn an_owner_that_does_not_offer_the_type_answers_none() {
    let mut script = converted(0);
    script.push(Step::Answer(Vec::new()));

    let (read, requests) = against(0, SELECTION_LIMIT, script);

    assert_eq!(read, Ok(None));
    assert_eq!(requests[6][0], DESTROY_WINDOW);
}

#[test]
fn a_picture_in_chunks_is_read_to_its_empty_end() {
    let mut script = converted(PROPERTY);
    script.extend([
        property(7, INCR, &1000_u32.to_le_bytes(), 0),
        changed(7, WINDOW, Property::DELETE),
        changed(7, OTHER, Property::NEW_VALUE),
        changed(7, WINDOW, Property::NEW_VALUE),
        property(8, PNG, b"abc", 0),
        changed(8, WINDOW, Property::NEW_VALUE),
        property(9, PNG, b"def", 0),
        changed(9, WINDOW, Property::NEW_VALUE),
        property(10, PNG, b"", 0),
    ]);

    let (read, requests) = against(0, SELECTION_LIMIT, script);

    assert_eq!(read, Ok(Some(b"abcdef".to_vec())));
    let room = |request: &Vec<u8>| words(&request[20..]);
    let rooms: Vec<u32> = requests[6..].iter().map(room).collect();
    assert_eq!(rooms, [17, 17, 16, 15]);
}

#[test]
fn chunks_past_the_limit_stop_the_read() {
    let mut script = converted(PROPERTY);
    script.extend([
        property(7, INCR, &1000_u32.to_le_bytes(), 0),
        changed(7, WINDOW, Property::NEW_VALUE),
        property(8, PNG, &[1; LIMIT - 2], 0),
        changed(8, WINDOW, Property::NEW_VALUE),
        property(9, PNG, b"abc", 0),
    ]);

    let (read, _) = against(0, SELECTION_LIMIT, script);

    assert_eq!(read, Err(SelectionError::Over));
}

#[test]
fn a_whole_picture_past_the_limit_stops_the_read() {
    let mut script = converted(PROPERTY);
    script.push(property(7, PNG, &[1; LIMIT], 4));

    let (read, _) = against(0, SELECTION_LIMIT, script);

    assert_eq!(read, Err(SelectionError::Over));
}

#[test]
fn an_answer_to_another_window_is_passed_over() {
    let mut script = interned();
    script.push(Step::Answer(Vec::new()));
    script.push(Step::Answer(notify(6, OTHER, 0)));
    script.push(changed(6, WINDOW, Property::NEW_VALUE));
    script.push(Step::Push(notify(6, WINDOW, PROPERTY)));
    script.push(property(7, PNG, b"png", 0));

    let (read, _) = against(0, SELECTION_LIMIT, script);

    assert_eq!(read, Ok(Some(b"png".to_vec())));
}

#[test]
fn an_x_error_fails_the_read() {
    let mut script = interned();
    script.push(Step::Answer(Vec::new()));
    script.push(Step::Answer(error(6, BAD_WINDOW, CONVERT_SELECTION)));

    let (read, _) = against(0, SELECTION_LIMIT, script);

    let Err(SelectionError::Failed(reason)) = read else {
        panic!("expected a failed read, got {read:?}");
    };
    assert!(reason.contains("Window"), "{reason}");
}

#[test]
fn an_owner_that_never_answers_fails_the_read_after_the_wait() {
    let mut script = interned();
    script.push(Step::Answer(Vec::new()));
    script.push(Step::Answer(Vec::new()));

    let (read, _) = against(0, Duration::from_millis(40), script);

    assert_eq!(read, Err(SelectionError::Silent));
}

#[test]
fn a_server_that_closes_mid_read_fails_it() {
    let mut script = interned();
    script.push(Step::Answer(Vec::new()));
    script.push(Step::Hangup);

    let (read, _) = against(0, SELECTION_LIMIT, script);

    assert!(matches!(read, Err(SelectionError::Failed(_))), "{read:?}");
}

#[test]
fn a_server_that_closes_before_the_names_fails_the_read() {
    let (read, _) = against(0, SELECTION_LIMIT, vec![Step::Hangup]);

    assert!(matches!(read, Err(SelectionError::Failed(_))), "{read:?}");
}

#[test]
fn a_screen_the_server_does_not_have_fails_the_read() {
    let (read, requests) = against(3, SELECTION_LIMIT, Vec::new());

    let missing = String::from("the X server has no screen 3");
    assert_eq!(read, Err(SelectionError::Failed(missing)));
    assert!(requests.is_empty());
}

#[test]
fn a_session_with_no_display_set_fails_every_read() {
    let error = ConnectError::DisplayParsingError(DisplayParsingError::DisplayNotSet);

    let selection = X11Selection::absent(&error);

    let absent = SelectionError::Failed(error.to_string());
    assert_eq!(selection.convert("image/png", LIMIT), Err(absent.clone()));
    assert_eq!(selection.offered(), Err(absent));
}

fn atoms(sequence: u16, atoms: &[u32]) -> Step {
    let value: Vec<u8> = atoms.iter().flat_map(|atom| atom.to_ne_bytes()).collect();
    let reply = GetPropertyReply {
        format: 32,
        sequence,
        length: u32::try_from(atoms.len()).unwrap_or_else(|error| panic!("{error:?}")),
        type_: 4,
        bytes_after: 0,
        value_len: u32::try_from(atoms.len()).unwrap_or_else(|error| panic!("{error:?}")),
        value,
    };
    Step::Answer(reply.serialize())
}

fn named(sequence: u16, name: &str) -> Step {
    let mut name = name.as_bytes().to_vec();
    let length = name.len().div_ceil(4);
    let reply = GetAtomNameReply {
        sequence,
        length: u32::try_from(length).unwrap_or_else(|error| panic!("{error:?}")),
        name: name.clone(),
    };
    let mut bytes = reply.serialize();
    name.resize(length * 4, 0);
    bytes.resize(32 + name.len(), 0);
    Step::Answer(bytes)
}

#[test]
fn the_owner_lists_its_types_by_name() {
    let mut script = converted(PROPERTY);
    script.extend([
        atoms(7, &[PNG, 311]),
        Step::Answer(Vec::new()),
        named(9, "image/png"),
        named(10, "UTF8_STRING"),
    ]);

    let (listed, requests) = against_with(0, SELECTION_LIMIT, script, X11Selection::offered);

    assert_eq!(
        listed,
        Ok(vec![String::from("image/png"), String::from("UTF8_STRING")])
    );
    let name_length = usize::from(u16::from_le_bytes([requests[1][4], requests[1][5]]));
    assert_eq!(&requests[1][8..8 + name_length], b"TARGETS");
    let get_atom_name = 17;
    let asked: Vec<(u8, u32)> = requests[8..]
        .iter()
        .map(|request| (request[0], words(&request[4..])))
        .collect();
    assert_eq!(asked, [(get_atom_name, PNG), (get_atom_name, 311)]);
}

#[test]
fn a_clipboard_nobody_owns_lists_nothing() {
    let (listed, _) = against_with(0, SELECTION_LIMIT, converted(0), X11Selection::offered);

    assert_eq!(listed, Ok(Vec::new()));
}

#[test]
fn a_server_that_closes_before_the_names_fails_the_list() {
    let mut script = converted(PROPERTY);
    script.extend([atoms(7, &[PNG]), Step::Answer(Vec::new()), Step::Hangup]);

    let (listed, _) = against_with(0, SELECTION_LIMIT, script, X11Selection::offered);

    assert!(
        matches!(listed, Err(SelectionError::Failed(_))),
        "{listed:?}"
    );
}

#[test]
fn a_server_that_closes_before_the_list_fails_it() {
    let (listed, _) = against_with(
        0,
        SELECTION_LIMIT,
        vec![Step::Hangup],
        X11Selection::offered,
    );

    assert!(
        matches!(listed, Err(SelectionError::Failed(_))),
        "{listed:?}"
    );
}

#[test]
fn a_server_that_closes_before_the_property_fails_the_read() {
    let mut script = converted(PROPERTY);
    script.push(Step::Hangup);

    let (read, _) = against(0, SELECTION_LIMIT, script);

    assert!(matches!(read, Err(SelectionError::Failed(_))), "{read:?}");
}

#[test]
fn a_server_that_closes_between_chunks_fails_the_read() {
    let mut script = converted(PROPERTY);
    script.extend([property(7, INCR, &1000_u32.to_le_bytes(), 0), Step::Hangup]);

    let (read, _) = against(0, SELECTION_LIMIT, script);

    assert!(matches!(read, Err(SelectionError::Failed(_))), "{read:?}");
}

#[test]
fn a_deletion_or_another_window_is_not_taken_for_the_next_chunk() {
    let mut script = converted(PROPERTY);
    script.extend([
        property(7, INCR, &1000_u32.to_le_bytes(), 0),
        changed(7, WINDOW, Property::DELETE),
        changed(7, OTHER, Property::NEW_VALUE),
    ]);

    let (read, requests) = against(0, Duration::from_millis(40), script);

    assert_eq!(read, Err(SelectionError::Silent));
    assert_eq!(requests.len(), 7);
}
