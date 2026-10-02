#![cfg(target_os = "linux")]

use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::thread;
use std::time::Duration;

use os_linux::x11rb::errors::{ConnectError, DisplayParsingError};
use os_linux::x11rb::protocol::randr::{GetMonitorsReply, MonitorInfo};
use os_linux::x11rb::protocol::xproto::{
    BackingStore, Depth, EventMask, Format, GetGeometryReply, GetImageReply, GetPropertyReply,
    GetSelectionOwnerReply, GetWindowAttributesReply, Gravity, ImageOrder, InternAtomReply,
    MapState, QueryExtensionReply, QueryTreeReply, Screen, Setup, Visualtype, WindowClass,
};
use os_linux::x11rb::rust_connection::{DefaultStream, RustConnection};
use os_linux::x11rb::x11_utils::Serialize;
use os_linux::{
    Area, GrabError, Layer, Layout, Monitor, Pixels, RootGrab, RootImage, Snapshot, TreeWindow,
    X11Root,
};

const ROOT: u32 = 0x0000_0100;
const VISUAL: u32 = 0x0000_0021;
const GET_IMAGE: u8 = 73;
const GRAB_SERVER: u8 = 36;
const UNGRAB_SERVER: u8 = 37;
const INTERN_ATOM: u8 = 16;
const QUERY_TREE: u8 = 15;
const GET_PROPERTY: u8 = 20;
const PID_ATOM: u32 = 0x0000_01a7;
const CM_ATOM: u32 = 0x0000_01b0;
const BACKGROUND_ATOM: u32 = 0x0000_01c4;
const GET_SELECTION_OWNER: u8 = 23;
const GET_GEOMETRY: u8 = 14;
const CARDINAL: u32 = 6;
const PIXMAP: u32 = 20;
const SHEET: u32 = 0x0080_0001;
const RANDR: u8 = 140;
const GET_MONITORS: u8 = 42;
const COMPOSITOR: u32 = 0x0060_0001;
const WHOLE: Area = Area {
    x: 0,
    y: 0,
    width: 2,
    height: 1,
};

/// What the fake server sends back for one request: reply bytes, or `None` to close instead.
/// `serve` writes the request's sequence number into each reply, so a script lists none.
type Answer = Option<Vec<u8>>;

fn setup(order: ImageOrder, visual: u32) -> Setup {
    let mut setup = Setup {
        status: 1,
        protocol_major_version: 11,
        resource_id_mask: 0x001f_ffff,
        maximum_request_length: u16::MAX,
        image_byte_order: order,
        min_keycode: 8,
        max_keycode: 255,
        pixmap_formats: vec![
            Format {
                depth: 1,
                bits_per_pixel: 1,
                scanline_pad: 32,
            },
            Format {
                depth: 24,
                bits_per_pixel: 32,
                scanline_pad: 32,
            },
        ],
        roots: vec![Screen {
            root: ROOT,
            width_in_pixels: 2,
            height_in_pixels: 1,
            root_visual: VISUAL,
            root_depth: 24,
            allowed_depths: vec![Depth {
                depth: 24,
                visuals: vec![Visualtype {
                    visual_id: visual,
                    bits_per_rgb_value: 8,
                    red_mask: 0x00ff_0000,
                    green_mask: 0x0000_ff00,
                    blue_mask: 0x0000_00ff,
                    ..Visualtype::default()
                }],
            }],
            ..Screen::default()
        }],
        ..Setup::default()
    };
    setup.length = u16::try_from((setup.serialize().len() - 8) / 4)
        .unwrap_or_else(|error| panic!("{error:?}"));
    setup
}

fn image(data: Vec<u8>) -> Vec<u8> {
    image_as(24, VISUAL, data)
}

fn image_as(depth: u8, visual: u32, data: Vec<u8>) -> Vec<u8> {
    let reply = GetImageReply {
        depth,
        sequence: 0,
        visual,
        data,
    };
    reply.serialize()
}

fn padded(mut bytes: Vec<u8>) -> Vec<u8> {
    bytes.resize(bytes.len().max(32), 0);
    bytes
}

fn atom(atom: u32) -> Vec<u8> {
    padded(
        InternAtomReply {
            sequence: 0,
            length: 0,
            atom,
        }
        .serialize()
        .to_vec(),
    )
}

/// The two answers that name the compositing manager's selection and report `owner` holding it.
fn owner(owner: u32) -> [Vec<u8>; 2] {
    let held = GetSelectionOwnerReply {
        sequence: 0,
        length: 0,
        owner,
    };
    [atom(CM_ATOM), padded(held.serialize().to_vec())]
}

fn tree(children: Vec<u32>) -> Vec<u8> {
    QueryTreeReply {
        sequence: 0,
        length: u32::try_from(children.len()).unwrap_or_else(|error| panic!("{error:?}")),
        root: ROOT,
        parent: 0,
        children,
    }
    .serialize()
}

fn attributes(map_state: MapState) -> Vec<u8> {
    attributes_of(map_state, WindowClass::INPUT_OUTPUT)
}

fn attributes_of(map_state: MapState, class: WindowClass) -> Vec<u8> {
    GetWindowAttributesReply {
        backing_store: BackingStore::NOT_USEFUL,
        sequence: 0,
        length: 3,
        visual: VISUAL,
        class,
        bit_gravity: Gravity::BIT_FORGET,
        win_gravity: Gravity::NORTH_WEST,
        backing_planes: 0,
        backing_pixel: 0,
        save_under: false,
        map_is_installed: true,
        map_state,
        override_redirect: false,
        colormap: 0,
        all_event_masks: EventMask::NO_EVENT,
        your_event_mask: EventMask::NO_EVENT,
        do_not_propagate_mask: EventMask::NO_EVENT,
    }
    .serialize()
    .to_vec()
}

fn geometry(x: i16, y: i16, border_width: u16) -> Vec<u8> {
    geometry_of(
        24,
        Area {
            x,
            y,
            width: 5,
            height: 6,
        },
        border_width,
    )
}

fn geometry_of(depth: u8, area: Area, border_width: u16) -> Vec<u8> {
    padded(
        GetGeometryReply {
            depth,
            sequence: 0,
            length: 0,
            root: ROOT,
            x: area.x,
            y: area.y,
            width: area.width,
            height: area.height,
            border_width,
        }
        .serialize()
        .to_vec(),
    )
}

fn pid(value: Option<u32>) -> Vec<u8> {
    property(CARDINAL, value)
}

fn property(kind: u32, value: Option<u32>) -> Vec<u8> {
    let value = value.map_or_else(Vec::new, |word| word.to_le_bytes().to_vec());
    let words = u32::try_from(value.len() / 4).unwrap_or_else(|error| panic!("{error:?}"));
    GetPropertyReply {
        format: if value.is_empty() { 0 } else { 32 },
        sequence: 0,
        length: words,
        type_: if value.is_empty() { 0 } else { kind },
        bytes_after: 0,
        value_len: words,
        value,
    }
    .serialize()
}

/// The answers to a grab of a root with no windows up to the selection's owner, `holder`.
fn empty_tree(holder: u32) -> Vec<Answer> {
    let mut answers = vec![
        Some(Vec::new()),
        Some(atom(PID_ATOM)),
        Some(tree(Vec::new())),
    ];
    answers.extend(owner(holder).map(Some));
    answers
}

/// The answers to a grab of a root with no windows and no compositing manager, read as `data`.
fn bare(data: Vec<u8>) -> Vec<Answer> {
    let mut answers = empty_tree(0);
    answers.extend([Some(image(data)), Some(Vec::new())]);
    answers
}

/// The answers that report no background pixmap on the root.
fn unset() -> [Vec<u8>; 2] {
    [atom(BACKGROUND_ATOM), property(PIXMAP, None)]
}

/// The answers that name `SHEET` as the background and report its `depth` and size.
fn sheet(depth: u8, width: u16, height: u16) -> [Vec<u8>; 3] {
    let area = Area {
        x: 0,
        y: 0,
        width,
        height,
    };
    [
        atom(BACKGROUND_ATOM),
        property(PIXMAP, Some(SHEET)),
        geometry_of(depth, area, 0),
    ]
}

fn error(code: u8, major: u8, minor: u8) -> Vec<u8> {
    let mut error = vec![0_u8; 32];
    error[1] = code;
    error[8] = minor;
    error[10] = major;
    error
}

fn randr(present: bool) -> Vec<u8> {
    let reply = QueryExtensionReply {
        sequence: 0,
        length: 0,
        present,
        major_opcode: RANDR,
        first_event: 89,
        first_error: 147,
    };
    let mut bytes = reply.serialize().to_vec();
    bytes.resize(32, 0);
    bytes
}

fn monitor_info(primary: bool, x: i16, width: u16) -> MonitorInfo {
    MonitorInfo {
        name: 0,
        primary,
        automatic: true,
        x,
        y: 3,
        width,
        height: 4,
        width_in_millimeters: 0,
        height_in_millimeters: 0,
        outputs: vec![0x42],
    }
}

fn monitors(monitors: Vec<MonitorInfo>) -> Vec<u8> {
    let mut reply = GetMonitorsReply {
        sequence: 0,
        length: 0,
        timestamp: 0,
        n_outputs: 1,
        monitors,
    };
    reply.length = u32::try_from((reply.serialize().len() - 32) / 4)
        .unwrap_or_else(|error| panic!("{error:?}"));
    reply.serialize()
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

/// Serves one client: the handshake, then one request per answer, then waits for the client to
/// close, since the client drops a reply that arrives together with the end of stream. A wait
/// over ten seconds panics, which closes the stream, so a client awaiting a reply fails.
fn serve(mut peer: UnixStream, setup: &Setup, answers: Vec<Answer>) -> Vec<Vec<u8>> {
    let mut handshake = [0_u8; 12];
    peer.read_exact(&mut handshake)
        .unwrap_or_else(|error| panic!("{error:?}"));
    peer.write_all(&setup.serialize())
        .unwrap_or_else(|error| panic!("{error:?}"));
    peer.set_read_timeout(Some(Duration::from_secs(10)))
        .unwrap_or_else(|error| panic!("{error:?}"));
    let mut requests = Vec::new();
    for (sequence, answer) in (1_u16..).zip(answers) {
        requests.push(read_request(&mut peer));
        let Some(mut bytes) = answer else {
            return requests;
        };
        if !bytes.is_empty() {
            bytes[2..4].copy_from_slice(&sequence.to_le_bytes());
        }
        peer.write_all(&bytes)
            .unwrap_or_else(|error| panic!("{error:?}"));
    }
    let mut rest = Vec::new();
    peer.read_to_end(&mut rest)
        .unwrap_or_else(|error| panic!("{error:?}"));
    requests
}

fn against<T>(
    setup: Setup,
    screen: usize,
    answers: Vec<Answer>,
    call: impl FnOnce(&X11Root) -> T,
) -> (T, Vec<Vec<u8>>) {
    let (ours, theirs) = UnixStream::pair().unwrap_or_else(|error| panic!("{error:?}"));
    let server = thread::spawn(move || serve(theirs, &setup, answers));
    let (stream, _) =
        DefaultStream::from_unix_stream(ours).unwrap_or_else(|error| panic!("{error:?}"));
    let connection =
        RustConnection::connect_to_stream(stream, 0).unwrap_or_else(|error| panic!("{error:?}"));
    let root = X11Root::new(connection, screen);
    let result = call(&root);
    drop(root);
    (
        result,
        server.join().unwrap_or_else(|error| panic!("{error:?}")),
    )
}

fn grab_against(setup: Setup, answers: Vec<Answer>) -> (Result<Snapshot, GrabError>, Vec<Vec<u8>>) {
    against(setup, 0, answers, |root| root.grab(WHOLE))
}

fn image_of(grabbed: Result<Snapshot, GrabError>) -> RootImage {
    match grabbed.map(|snapshot| snapshot.pixels) {
        Ok(Pixels::Root(image)) => image,
        other => panic!("expected the root's image, got {other:?}"),
    }
}

fn layers_of(grabbed: Result<Snapshot, GrabError>) -> Vec<Layer> {
    match grabbed.map(|snapshot| snapshot.pixels) {
        Ok(Pixels::Layers(layers)) => layers,
        other => panic!("expected layers, got {other:?}"),
    }
}

fn layout_against(answers: Vec<Answer>) -> (Result<Layout, GrabError>, Vec<Vec<u8>>) {
    against(
        setup(ImageOrder::LSB_FIRST, VISUAL),
        0,
        answers,
        X11Root::layout,
    )
}

#[test]
fn a_grab_reads_the_given_area_in_the_servers_format() {
    let pixels = vec![1, 2, 3, 0, 4, 5, 6, 0];
    let area = Area {
        x: 1,
        y: 2,
        width: 2,
        height: 1,
    };

    let (grabbed, requests) = against(
        setup(ImageOrder::LSB_FIRST, VISUAL),
        0,
        bare(pixels.clone()),
        |root| root.grab(area),
    );

    assert_eq!(
        image_of(grabbed),
        RootImage {
            width: 2,
            height: 1,
            depth: 24,
            bits_per_pixel: 32,
            lsb_first: true,
            masks: (0x00ff_0000, 0x0000_ff00, 0x0000_00ff),
            data: pixels,
        }
    );
    let request = &requests[5];
    let format_zpixmap = 2;
    assert_eq!(&request[..2], &[GET_IMAGE, format_zpixmap]);
    assert_eq!(&request[4..8], &ROOT.to_le_bytes());
    assert_eq!(&request[8..16], &[1, 0, 2, 0, 2, 0, 1, 0]);
    assert_eq!(&request[16..20], &u32::MAX.to_le_bytes());
}

#[test]
fn a_layout_lists_the_active_randr_monitors_over_the_root() {
    let (listed, requests) = layout_against(vec![
        Some(randr(true)),
        Some(monitors(vec![
            monitor_info(false, 0, 5),
            monitor_info(true, 5, 6),
        ])),
    ]);

    let at = |primary, x, width| Monitor {
        primary,
        area: Area {
            x,
            y: 3,
            width,
            height: 4,
        },
    };
    assert_eq!(
        listed,
        Ok(Layout {
            root: WHOLE,
            monitors: vec![at(false, 0, 5), at(true, 5, 6)],
        })
    );
    let get_active = 1;
    assert_eq!(&requests[1][..2], &[RANDR, GET_MONITORS]);
    assert_eq!(&requests[1][4..8], &ROOT.to_le_bytes());
    assert_eq!(requests[1][8], get_active);
}

#[test]
fn a_server_without_randr_lists_no_monitors() {
    let (listed, requests) = layout_against(vec![Some(randr(false))]);

    assert_eq!(
        listed,
        Ok(Layout {
            root: WHOLE,
            monitors: Vec::new(),
        })
    );
    assert_eq!(requests.len(), 1);
}

#[test]
fn an_x_error_to_the_monitor_list_is_a_failed_layout() {
    let bad_request = 1;

    let (listed, _) = layout_against(vec![
        Some(randr(true)),
        Some(error(bad_request, RANDR, GET_MONITORS)),
    ]);

    assert!(matches!(listed, Err(GrabError::Failed(_))), "{listed:?}");
}

#[test]
fn a_server_that_closes_before_the_monitor_list_is_a_failed_layout() {
    let (listed, _) = layout_against(vec![None]);

    assert!(matches!(listed, Err(GrabError::Failed(_))), "{listed:?}");
}

#[test]
fn a_most_significant_byte_first_server_is_reported_as_such() {
    let (grabbed, _) = grab_against(setup(ImageOrder::MSB_FIRST, VISUAL), bare(vec![0; 8]));

    assert!(!image_of(grabbed).lsb_first);
}

#[test]
fn a_root_visual_the_setup_does_not_list_has_no_masks() {
    let (grabbed, _) = grab_against(setup(ImageOrder::LSB_FIRST, 0x99), bare(vec![0; 8]));

    assert_eq!(image_of(grabbed).masks, (0, 0, 0));
}

#[test]
fn a_depth_with_no_pixmap_format_has_no_bits_per_pixel() {
    let mut setup = setup(ImageOrder::LSB_FIRST, VISUAL);
    setup.pixmap_formats.pop();
    setup.length = u16::try_from((setup.serialize().len() - 8) / 4)
        .unwrap_or_else(|error| panic!("{error:?}"));

    let (grabbed, _) = grab_against(setup, bare(vec![0; 8]));

    assert_eq!(image_of(grabbed).bits_per_pixel, 0);
}

#[test]
fn an_x_error_reply_is_a_failed_grab_that_still_releases_the_server() {
    let bad_match = 8;

    let (grabbed, requests) = grab_against(setup(ImageOrder::LSB_FIRST, VISUAL), {
        let mut answers = empty_tree(0);
        answers.extend([Some(error(bad_match, GET_IMAGE, 0)), Some(Vec::new())]);
        answers
    });

    let Err(GrabError::Failed(reason)) = grabbed else {
        panic!("expected a failed grab, got {grabbed:?}");
    };
    assert!(reason.contains("Match"), "{reason}");
    let opcodes: Vec<u8> = requests.iter().map(|request| request[0]).collect();
    assert_eq!(
        opcodes,
        vec![
            GRAB_SERVER,
            INTERN_ATOM,
            QUERY_TREE,
            INTERN_ATOM,
            GET_SELECTION_OWNER,
            GET_IMAGE,
            UNGRAB_SERVER
        ]
    );
}

#[test]
fn a_server_that_closes_before_replying_is_a_failed_grab() {
    let (grabbed, _) = grab_against(
        setup(ImageOrder::LSB_FIRST, VISUAL),
        vec![Some(Vec::new()), None],
    );

    assert!(matches!(grabbed, Err(GrabError::Failed(_))), "{grabbed:?}");
}

#[test]
fn a_screen_the_server_does_not_have_fails_both_reads_before_any_request() {
    let (ours, theirs) = UnixStream::pair().unwrap_or_else(|error| panic!("{error:?}"));
    let setup = setup(ImageOrder::LSB_FIRST, VISUAL);
    let server = thread::spawn(move || {
        let mut peer = theirs;
        let mut handshake = [0_u8; 12];
        peer.read_exact(&mut handshake)
            .unwrap_or_else(|error| panic!("{error:?}"));
        peer.write_all(&setup.serialize())
            .unwrap_or_else(|error| panic!("{error:?}"));
        let mut rest = Vec::new();
        peer.read_to_end(&mut rest)
            .unwrap_or_else(|error| panic!("{error:?}"));
        rest
    });
    let (stream, _) =
        DefaultStream::from_unix_stream(ours).unwrap_or_else(|error| panic!("{error:?}"));
    let root = X11Root::new(
        RustConnection::connect_to_stream(stream, 0).unwrap_or_else(|error| panic!("{error:?}")),
        3,
    );

    let listed = root.layout();
    let grabbed = root.grab(WHOLE);
    drop(root);

    let missing = GrabError::Failed(String::from("the X server has no screen 3"));
    assert_eq!(listed, Err(missing.clone()));
    assert_eq!(grabbed, Err(missing));
    assert!(
        server
            .join()
            .unwrap_or_else(|error| panic!("{error:?}"))
            .is_empty()
    );
}

#[test]
fn a_session_with_no_display_set_is_no_display() {
    let error = ConnectError::DisplayParsingError(DisplayParsingError::DisplayNotSet);

    let root = X11Root::absent(&error);

    assert_eq!(root.layout(), Err(GrabError::NoDisplay(error.to_string())));
    assert_eq!(
        root.grab(WHOLE),
        Err(GrabError::NoDisplay(error.to_string()))
    );
}

#[test]
fn a_grab_lists_every_window_under_the_root_inside_one_server_grab() {
    let (frame, popup, client) = (0x0040_0001, 0x0040_0002, 0x0040_0003);
    let mut answers = vec![
        Some(Vec::new()),
        Some(atom(PID_ATOM)),
        Some(tree(vec![frame, popup])),
    ];
    answers.extend(
        [
            attributes(MapState::VIEWABLE),
            geometry(7, 8, 1),
            pid(None),
            tree(vec![client]),
            attributes(MapState::UNMAPPED),
            geometry(-2, 3, 0),
            pid(Some(4242)),
            tree(Vec::new()),
            attributes_of(MapState::UNVIEWABLE, WindowClass::INPUT_ONLY),
            geometry(0, 0, 0),
            pid(Some(77)),
            tree(Vec::new()),
        ]
        .map(Some),
    );
    answers.extend(owner(0).map(Some));
    answers.extend([Some(image(vec![0; 8])), Some(Vec::new())]);

    let (grabbed, requests) = grab_against(setup(ImageOrder::LSB_FIRST, VISUAL), answers);

    let at = |x, y| Area {
        x,
        y,
        width: 5,
        height: 6,
    };
    let window = |parent, area, border, viewable, pid, input_only| TreeWindow {
        parent,
        area,
        border,
        viewable,
        pid,
        input_only,
    };
    assert_eq!(
        grabbed.unwrap_or_else(|error| panic!("{error:?}")).windows,
        vec![
            window(None, at(7, 8), 1, true, None, false),
            window(None, at(-2, 3), 0, false, Some(4242), false),
            window(Some(0), at(0, 0), 0, false, Some(77), true),
        ]
    );
    assert_eq!(
        requests.first().map(|request| request[0]),
        Some(GRAB_SERVER)
    );
    assert_eq!(
        requests.last().map(|request| request[0]),
        Some(UNGRAB_SERVER)
    );
    assert_eq!(&requests[1][..2], &[INTERN_ATOM, 0]);
    assert_eq!(&requests[1][8..19], b"_NET_WM_PID");
    assert_eq!(&requests[2][..1], &[QUERY_TREE]);
    assert_eq!(&requests[2][4..8], &ROOT.to_le_bytes());
    let property = &requests[13];
    assert_eq!(property[0], GET_PROPERTY);
    assert_eq!(&property[4..8], &client.to_le_bytes());
    assert_eq!(&property[8..12], &PID_ATOM.to_le_bytes());
    assert_eq!(&property[12..16], &CARDINAL.to_le_bytes());
}

#[test]
fn an_x_error_while_listing_windows_is_a_failed_grab_that_releases_the_server() {
    let bad_window = 3;
    let get_window_attributes = 3;
    let at_the_root = vec![
        Some(Vec::new()),
        Some(atom(PID_ATOM)),
        Some(error(bad_window, QUERY_TREE, 0)),
        Some(Vec::new()),
    ];
    // The grab stops reading at the error, so the window's other three requests get no reply: a
    // reply left unread resets the socket at close, or meets a closed one if written late.
    let at_a_window = vec![
        Some(Vec::new()),
        Some(atom(PID_ATOM)),
        Some(tree(vec![0x0040_0001])),
        Some(error(bad_window, get_window_attributes, 0)),
        Some(Vec::new()),
        Some(Vec::new()),
        Some(Vec::new()),
        Some(Vec::new()),
    ];

    for answers in [at_the_root, at_a_window] {
        let (grabbed, requests) = grab_against(setup(ImageOrder::LSB_FIRST, VISUAL), answers);

        let Err(GrabError::Failed(reason)) = grabbed else {
            panic!("expected a failed grab, got {grabbed:?}");
        };
        assert!(reason.contains("Window"), "{reason}");
        assert_eq!(
            requests.last().map(|request| request[0]),
            Some(UNGRAB_SERVER)
        );
    }
}

#[test]
fn a_grab_reads_the_root_only_when_no_compositing_manager_owns_the_screen() {
    let mut composited = empty_tree(COMPOSITOR);
    composited.extend(unset().map(Some));
    composited.push(Some(Vec::new()));

    for (answers, read) in [(bare(vec![0; 8]), GET_IMAGE), (composited, INTERN_ATOM)] {
        let (grabbed, requests) = grab_against(setup(ImageOrder::LSB_FIRST, VISUAL), answers);

        let expected = if read == GET_IMAGE {
            Pixels::Root(image_of(grabbed.clone()))
        } else {
            Pixels::Layers(Vec::new())
        };
        assert_eq!(grabbed.map(|snapshot| snapshot.pixels), Ok(expected));
        assert_eq!(&requests[3][..2], &[INTERN_ATOM, 0]);
        assert_eq!(&requests[3][8..21], b"_NET_WM_CM_S0");
        assert_eq!(requests[4][0], GET_SELECTION_OWNER);
        assert_eq!(&requests[4][4..8], &CM_ATOM.to_le_bytes());
        assert_eq!(requests[5][0], read);
        assert_eq!(
            requests.last().map(|request| request[0]),
            Some(UNGRAB_SERVER)
        );
    }
}

#[test]
fn the_compositing_manager_selection_is_named_for_the_screen_read() {
    let mut two = setup(ImageOrder::LSB_FIRST, VISUAL);
    two.roots.push(two.roots[0].clone());
    two.length =
        u16::try_from((two.serialize().len() - 8) / 4).unwrap_or_else(|error| panic!("{error:?}"));

    let (grabbed, requests) = against(two, 1, bare(vec![0; 8]), |root| root.grab(WHOLE));

    assert!(grabbed.is_ok(), "{grabbed:?}");
    assert_eq!(&requests[3][8..21], b"_NET_WM_CM_S1");
}

/// The answers to a grab of `WHOLE` listing two viewable top-level windows, the first at the
/// origin and the second one pixel right, with `holder` owning the selection, then `reads` and
/// the release.
fn two_windows(holder: u32, reads: Vec<Vec<u8>>) -> Vec<Answer> {
    let mut answers = vec![
        Some(Vec::new()),
        Some(atom(PID_ATOM)),
        Some(tree(vec![0x0040_0001, 0x0040_0002])),
    ];
    answers.extend(
        [
            attributes(MapState::VIEWABLE),
            geometry(0, 0, 0),
            pid(None),
            tree(Vec::new()),
            attributes(MapState::VIEWABLE),
            geometry(1, 0, 0),
            pid(None),
            tree(Vec::new()),
        ]
        .map(Some),
    );
    answers.extend(owner(holder).map(Some));
    answers.extend(reads.into_iter().map(Some));
    answers.push(Some(Vec::new()));
    answers
}

const RGB: (u8, u8, (u32, u32, u32)) = (24, 32, (0x00ff_0000, 0x0000_ff00, 0x0000_00ff));

/// A layer of `shade` at `x` on the first row, `width` wide, in the given format.
fn layer(
    x: i16,
    width: u16,
    shade: u8,
    (depth, bits_per_pixel, masks): (u8, u8, (u32, u32, u32)),
) -> Layer {
    Layer {
        place: Area {
            x,
            y: 0,
            width,
            height: 1,
        },
        image: RootImage {
            width: u32::from(width),
            height: 1,
            depth,
            bits_per_pixel,
            lsb_first: true,
            masks,
            data: vec![shade; usize::from(width) * 4],
        },
    }
}

#[test]
fn a_composited_grab_reads_each_top_level_window_inside_the_area_from_the_window() {
    let unlisted = 0x99;
    let [name, unset] = unset();
    let answers = two_windows(
        COMPOSITOR,
        vec![
            name,
            unset,
            image(vec![1; 8]),
            image_as(32, unlisted, vec![2; 4]),
        ],
    );

    let (grabbed, requests) = grab_against(setup(ImageOrder::LSB_FIRST, VISUAL), answers);

    let unknown = (32, 0, (0, 0, 0));
    assert_eq!(
        layers_of(grabbed),
        vec![layer(0, 2, 1, RGB), layer(1, 1, 2, unknown)]
    );
    let (first, second) = (&requests[15], &requests[16]);
    assert_eq!(&first[..2], &[GET_IMAGE, 2]);
    assert_eq!(&first[4..16], &[1, 0, 0x40, 0, 0, 0, 0, 0, 2, 0, 1, 0]);
    assert_eq!(&second[4..16], &[2, 0, 0x40, 0, 0, 0, 0, 0, 1, 0, 1, 0]);
    assert_eq!(
        requests.last().map(|request| request[0]),
        Some(UNGRAB_SERVER)
    );
}

#[test]
fn an_x_error_reading_a_window_is_a_failed_grab_that_releases_the_server() {
    let bad_match = 8;
    let [name, unset] = unset();
    let answers = two_windows(
        COMPOSITOR,
        vec![name, unset, error(bad_match, GET_IMAGE, 0)],
    );

    let (grabbed, requests) = grab_against(setup(ImageOrder::LSB_FIRST, VISUAL), answers);

    let Err(GrabError::Failed(reason)) = grabbed else {
        panic!("expected a failed grab, got {grabbed:?}");
    };
    assert!(reason.contains("Match"), "{reason}");
    assert_eq!(
        requests.last().map(|request| request[0]),
        Some(UNGRAB_SERVER)
    );
}

#[test]
fn a_grab_with_no_compositing_manager_reads_no_window() {
    let (grabbed, requests) = grab_against(
        setup(ImageOrder::LSB_FIRST, VISUAL),
        two_windows(0, vec![image(vec![0; 8])]),
    );

    assert_eq!(image_of(grabbed).data, vec![0; 8]);
    assert_eq!(requests.len(), 15);
    assert_eq!(requests[13][0], GET_IMAGE);
    assert_eq!(&requests[13][4..8], &ROOT.to_le_bytes());
    assert_eq!(requests[14][0], UNGRAB_SERVER);
}

#[test]
fn a_composited_grab_reads_the_background_pixmap_from_the_roots_corner_below_every_window() {
    let pixmap_visual = 0;
    let mut reads = sheet(24, 2, 1).to_vec();
    reads.extend([
        image_as(24, pixmap_visual, vec![4; 4]),
        image(vec![1; 8]),
        image(vec![2; 8]),
    ]);
    let answers = two_windows(COMPOSITOR, reads);
    let area = Area {
        x: 1,
        y: 0,
        width: 2,
        height: 1,
    };

    let (grabbed, requests) = against(setup(ImageOrder::LSB_FIRST, VISUAL), 0, answers, |root| {
        root.grab(area)
    });

    assert_eq!(
        layers_of(grabbed),
        vec![
            layer(1, 1, 4, RGB),
            layer(1, 2, 1, RGB),
            layer(1, 2, 2, RGB)
        ]
    );
    let (name, property, geometry, read) =
        (&requests[13], &requests[14], &requests[15], &requests[16]);
    assert_eq!(&name[..2], &[INTERN_ATOM, 0]);
    assert_eq!(&name[8..21], b"_XROOTPMAP_ID");
    assert_eq!(property[0], GET_PROPERTY);
    assert_eq!(&property[4..8], &ROOT.to_le_bytes());
    assert_eq!(&property[8..12], &BACKGROUND_ATOM.to_le_bytes());
    assert_eq!(&property[12..16], &PIXMAP.to_le_bytes());
    assert_eq!(geometry[0], GET_GEOMETRY);
    assert_eq!(&geometry[4..8], &SHEET.to_le_bytes());
    assert_eq!(read[0], GET_IMAGE);
    assert_eq!(&read[4..8], &SHEET.to_le_bytes());
    assert_eq!(&read[8..16], &[1, 0, 0, 0, 1, 0, 1, 0]);
}

/// Grabs `area` of a composited root with no windows whose background reads answer `reads`.
fn background_against(
    area: Area,
    reads: Vec<Answer>,
) -> (Result<Snapshot, GrabError>, Vec<Vec<u8>>) {
    let mut answers = empty_tree(COMPOSITOR);
    answers.extend(reads);
    answers.push(Some(Vec::new()));
    against(setup(ImageOrder::LSB_FIRST, VISUAL), 0, answers, |root| {
        root.grab(area)
    })
}

#[test]
fn a_background_the_server_cannot_paint_from_leaves_the_base_black() {
    let bad_drawable = 9;
    let [name, unset] = unset();
    let [named, set, _] = sheet(24, 2, 1);
    let [_, _, deep] = sheet(32, 2, 1);
    let [_, _, small] = sheet(24, 1, 1);
    let off = Area {
        x: 1,
        y: 0,
        width: 1,
        height: 1,
    };
    let cases = [
        (WHOLE, vec![name, unset]),
        (WHOLE, vec![named.clone(), set.clone(), deep]),
        (
            WHOLE,
            vec![
                named.clone(),
                set.clone(),
                error(bad_drawable, GET_GEOMETRY, 0),
            ],
        ),
        (off, vec![named, set, small]),
    ];

    for (area, reads) in cases {
        let count = reads.len();
        let (grabbed, requests) = background_against(area, reads.into_iter().map(Some).collect());

        assert_eq!(layers_of(grabbed), Vec::new());
        assert_eq!(requests.len(), 5 + count + 1);
    }
}

#[test]
fn a_server_that_closes_while_the_background_is_read_is_a_failed_grab() {
    let [named, set, _] = sheet(24, 2, 1);

    for reads in [vec![None], vec![Some(named), Some(set), None]] {
        let (grabbed, _) = background_against(WHOLE, reads);

        assert!(matches!(grabbed, Err(GrabError::Failed(_))), "{grabbed:?}");
    }
}
