#![cfg(target_os = "linux")]

use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::thread;

use os_linux::x11rb::errors::{ConnectError, DisplayParsingError};
use os_linux::x11rb::protocol::xproto::{
    Depth, Format, GetImageReply, ImageOrder, Screen, Setup, Visualtype,
};
use os_linux::x11rb::rust_connection::{DefaultStream, RustConnection};
use os_linux::x11rb::x11_utils::Serialize;
use os_linux::{GrabError, RootGrab, RootImage, X11Root};

const ROOT: u32 = 0x0000_0100;
const VISUAL: u32 = 0x0000_0021;
const GET_IMAGE: u8 = 73;

/// What the fake server sends back for the one request it reads.
enum Answer {
    Image(Vec<u8>),
    Error(u8),
    Hang,
}

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

/// Serves one client: the handshake, then one request answered as `answer`, then waits for the
/// client to close, since the client drops a reply that arrives together with the end of stream.
fn serve(mut peer: UnixStream, setup: &Setup, answer: Answer) -> Vec<u8> {
    let mut handshake = [0_u8; 12];
    peer.read_exact(&mut handshake)
        .unwrap_or_else(|error| panic!("{error:?}"));
    peer.write_all(&setup.serialize())
        .unwrap_or_else(|error| panic!("{error:?}"));
    let mut request = vec![0_u8; 20];
    peer.read_exact(&mut request)
        .unwrap_or_else(|error| panic!("{error:?}"));
    match answer {
        Answer::Image(data) => {
            let reply = GetImageReply {
                depth: 24,
                sequence: 1,
                visual: VISUAL,
                data,
            };
            peer.write_all(&reply.serialize())
                .unwrap_or_else(|error| panic!("{error:?}"));
        }
        Answer::Error(code) => {
            let mut error = [0_u8; 32];
            error[1] = code;
            error[2] = 1;
            error[10] = GET_IMAGE;
            peer.write_all(&error)
                .unwrap_or_else(|error| panic!("{error:?}"));
        }
        Answer::Hang => return request,
    }
    let mut rest = Vec::new();
    peer.read_to_end(&mut rest)
        .unwrap_or_else(|error| panic!("{error:?}"));
    request
}

fn grab_against(
    setup: Setup,
    screen: usize,
    answer: Answer,
) -> (Result<RootImage, GrabError>, Vec<u8>) {
    let (ours, theirs) = UnixStream::pair().unwrap_or_else(|error| panic!("{error:?}"));
    let server = thread::spawn(move || serve(theirs, &setup, answer));
    let (stream, _) =
        DefaultStream::from_unix_stream(ours).unwrap_or_else(|error| panic!("{error:?}"));
    let connection =
        RustConnection::connect_to_stream(stream, 0).unwrap_or_else(|error| panic!("{error:?}"));
    let root = X11Root::new(connection, screen);
    let grabbed = root.grab();
    drop(root);
    (
        grabbed,
        server.join().unwrap_or_else(|error| panic!("{error:?}")),
    )
}

#[test]
fn a_grab_reads_the_whole_root_in_the_servers_format() {
    let pixels = vec![1, 2, 3, 0, 4, 5, 6, 0];

    let (grabbed, request) = grab_against(
        setup(ImageOrder::LSB_FIRST, VISUAL),
        0,
        Answer::Image(pixels.clone()),
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
    let format_zpixmap = 2;
    assert_eq!(&request[..2], &[GET_IMAGE, format_zpixmap]);
    assert_eq!(&request[4..8], &ROOT.to_le_bytes());
    assert_eq!(&request[8..16], &[0, 0, 0, 0, 2, 0, 1, 0]);
    assert_eq!(&request[16..20], &u32::MAX.to_le_bytes());
}

#[test]
fn a_most_significant_byte_first_server_is_reported_as_such() {
    let (grabbed, _) = grab_against(
        setup(ImageOrder::MSB_FIRST, VISUAL),
        0,
        Answer::Image(vec![0; 8]),
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
        0,
        Answer::Image(vec![0; 8]),
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

    let (grabbed, _) = grab_against(setup, 0, Answer::Image(vec![0; 8]));

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
        0,
        Answer::Error(bad_match),
    );

    let Err(GrabError::Failed(reason)) = grabbed else {
        panic!("expected a failed grab, got {grabbed:?}");
    };
    assert!(reason.contains("Match"), "{reason}");
}

#[test]
fn a_server_that_closes_before_replying_is_a_failed_grab() {
    let (grabbed, _) = grab_against(setup(ImageOrder::LSB_FIRST, VISUAL), 0, Answer::Hang);

    assert!(matches!(grabbed, Err(GrabError::Failed(_))), "{grabbed:?}");
}

#[test]
fn a_screen_the_server_does_not_have_is_a_failed_grab_before_any_request() {
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

    let grabbed = root.grab();
    drop(root);

    assert_eq!(
        grabbed,
        Err(GrabError::Failed(String::from(
            "the X server has no screen 3"
        )))
    );
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

    let grabbed = X11Root::absent(&error).grab();

    assert_eq!(grabbed, Err(GrabError::NoDisplay(error.to_string())));
}
