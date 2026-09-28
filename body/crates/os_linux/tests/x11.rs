#![cfg(target_os = "linux")]

use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::thread;

use os_linux::x11rb::errors::{ConnectError, DisplayParsingError};
use os_linux::x11rb::protocol::randr::{GetMonitorsReply, MonitorInfo};
use os_linux::x11rb::protocol::xproto::{
    Depth, Format, GetImageReply, ImageOrder, QueryExtensionReply, Screen, Setup, Visualtype,
};
use os_linux::x11rb::rust_connection::{DefaultStream, RustConnection};
use os_linux::x11rb::x11_utils::Serialize;
use os_linux::{Area, GrabError, Layout, Monitor, RootGrab, RootImage, X11Root};

const ROOT: u32 = 0x0000_0100;
const VISUAL: u32 = 0x0000_0021;
const GET_IMAGE: u8 = 73;
const RANDR: u8 = 140;
const GET_MONITORS: u8 = 42;
const WHOLE: Area = Area {
    x: 0,
    y: 0,
    width: 2,
    height: 1,
};

/// What the fake server sends back for one request: reply bytes, or `None` to close instead.
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

fn image(sequence: u16, data: Vec<u8>) -> Vec<u8> {
    let reply = GetImageReply {
        depth: 24,
        sequence,
        visual: VISUAL,
        data,
    };
    reply.serialize()
}

fn error(sequence: u16, code: u8, major: u8, minor: u8) -> Vec<u8> {
    let mut error = vec![0_u8; 32];
    error[1] = code;
    error[2..4].copy_from_slice(&sequence.to_le_bytes());
    error[8] = minor;
    error[10] = major;
    error
}

fn randr(present: bool) -> Vec<u8> {
    let reply = QueryExtensionReply {
        sequence: 1,
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
        sequence: 2,
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
/// close, since the client drops a reply that arrives together with the end of stream.
fn serve(mut peer: UnixStream, setup: &Setup, answers: Vec<Answer>) -> Vec<Vec<u8>> {
    let mut handshake = [0_u8; 12];
    peer.read_exact(&mut handshake)
        .unwrap_or_else(|error| panic!("{error:?}"));
    peer.write_all(&setup.serialize())
        .unwrap_or_else(|error| panic!("{error:?}"));
    let mut requests = Vec::new();
    for answer in answers {
        requests.push(read_request(&mut peer));
        let Some(bytes) = answer else {
            return requests;
        };
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

fn grab_against(setup: Setup, answer: Answer) -> (Result<RootImage, GrabError>, Vec<Vec<u8>>) {
    against(setup, 0, vec![answer], |root| root.grab(WHOLE))
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
        vec![Some(image(1, pixels.clone()))],
        |root| root.grab(area),
    );

    assert_eq!(
        grabbed,
        Ok(RootImage {
            width: 2,
            height: 1,
            depth: 24,
            bits_per_pixel: 32,
            lsb_first: true,
            masks: (0x00ff_0000, 0x0000_ff00, 0x0000_00ff),
            data: pixels,
        })
    );
    let request = &requests[0];
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
        Some(error(2, bad_request, RANDR, GET_MONITORS)),
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
    let (grabbed, _) = grab_against(
        setup(ImageOrder::MSB_FIRST, VISUAL),
        Some(image(1, vec![0; 8])),
    );

    assert!(
        !grabbed
            .unwrap_or_else(|error| panic!("{error:?}"))
            .lsb_first
    );
}

#[test]
fn a_root_visual_the_setup_does_not_list_has_no_masks() {
    let (grabbed, _) = grab_against(
        setup(ImageOrder::LSB_FIRST, 0x99),
        Some(image(1, vec![0; 8])),
    );

    assert_eq!(
        grabbed.unwrap_or_else(|error| panic!("{error:?}")).masks,
        (0, 0, 0)
    );
}

#[test]
fn a_depth_with_no_pixmap_format_has_no_bits_per_pixel() {
    let mut setup = setup(ImageOrder::LSB_FIRST, VISUAL);
    setup.pixmap_formats.pop();
    setup.length = u16::try_from((setup.serialize().len() - 8) / 4)
        .unwrap_or_else(|error| panic!("{error:?}"));

    let (grabbed, _) = grab_against(setup, Some(image(1, vec![0; 8])));

    assert_eq!(
        grabbed
            .unwrap_or_else(|error| panic!("{error:?}"))
            .bits_per_pixel,
        0
    );
}

#[test]
fn an_x_error_reply_is_a_failed_grab() {
    let bad_match = 8;

    let (grabbed, _) = grab_against(
        setup(ImageOrder::LSB_FIRST, VISUAL),
        Some(error(1, bad_match, GET_IMAGE, 0)),
    );

    let Err(GrabError::Failed(reason)) = grabbed else {
        panic!("expected a failed grab, got {grabbed:?}");
    };
    assert!(reason.contains("Match"), "{reason}");
}

#[test]
fn a_server_that_closes_before_replying_is_a_failed_grab() {
    let (grabbed, _) = grab_against(setup(ImageOrder::LSB_FIRST, VISUAL), None);

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
