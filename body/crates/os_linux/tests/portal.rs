#![cfg(target_os = "linux")]

use std::ffi::OsString;
use std::os::unix::ffi::OsStringExt;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Mutex, PoisonError};
use std::thread;
use std::time::Duration;

use body_core::{CaptureError, CaptureRequest, CaptureTarget, ScreenCapture};
use os_linux::{
    LinuxPortalCapture, MAX_DECODED_BYTES, PortalError, PortalReply, ScreenshotPortal, decode_png,
    file_path, request_path,
};
use png::{BitDepth, ColorType};

/// The value of a setup step that cannot fail in a working test environment.
fn ok<T, E: std::fmt::Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("a setup step failed: {error:?}"))
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum Call {
    Sender,
    Screenshot(String, String),
    Read(PathBuf),
    Remove(PathBuf),
}

/// A portal that answers each call as scripted and records every call it was sent.
struct FakePortal {
    sender: Result<String, PortalError>,
    reply: Result<PortalReply, PortalError>,
    file: Result<Vec<u8>, PortalError>,
    removal: Result<(), PortalError>,
    calls: Mutex<Vec<Call>>,
    pause: Duration,
    in_flight: AtomicUsize,
    most_in_flight: AtomicUsize,
}

impl FakePortal {
    fn answering(reply: PortalReply) -> Self {
        Self {
            sender: Ok(String::from(":1.16")),
            reply: Ok(reply),
            file: Ok(rgb_picture()),
            removal: Ok(()),
            calls: Mutex::new(Vec::new()),
            pause: Duration::ZERO,
            in_flight: AtomicUsize::new(0),
            most_in_flight: AtomicUsize::new(0),
        }
    }

    fn record(&self, call: Call) {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(call);
    }
}

impl ScreenshotPortal for &FakePortal {
    fn sender(&self) -> Result<String, PortalError> {
        self.record(Call::Sender);
        self.sender.clone()
    }

    fn screenshot(&self, handle: &str, token: &str) -> Result<PortalReply, PortalError> {
        self.record(Call::Screenshot(String::from(handle), String::from(token)));
        let now = self.in_flight.fetch_add(1, Ordering::SeqCst) + 1;
        self.most_in_flight.fetch_max(now, Ordering::SeqCst);
        thread::sleep(self.pause);
        self.in_flight.fetch_sub(1, Ordering::SeqCst);
        self.reply.clone()
    }

    fn read(&self, path: &Path) -> Result<Vec<u8>, PortalError> {
        self.record(Call::Read(path.to_path_buf()));
        self.file.clone()
    }

    fn remove(&self, path: &Path) -> Result<(), PortalError> {
        self.record(Call::Remove(path.to_path_buf()));
        self.removal.clone()
    }
}

fn success() -> PortalReply {
    PortalReply {
        code: 0,
        uri: Some(String::from("file:///tmp/out.png")),
    }
}

fn encode(width: u32, height: u32, colour: ColorType, depth: BitDepth, data: &[u8]) -> Vec<u8> {
    encode_with(width, height, colour, depth, data, None)
}

fn encode_with(
    width: u32,
    height: u32,
    colour: ColorType,
    depth: BitDepth,
    data: &[u8],
    palette: Option<&[u8]>,
) -> Vec<u8> {
    let mut bytes = Vec::new();
    let mut encoder = png::Encoder::new(&mut bytes, width, height);
    encoder.set_color(colour);
    encoder.set_depth(depth);
    if let Some(palette) = palette {
        encoder.set_palette(palette.to_vec());
    }
    let mut writer = ok(encoder.write_header());
    ok(writer.write_image_data(data));
    ok(writer.finish());
    bytes
}

/// A 2 by 1 picture: a red pixel, then the blue 51, 102, 204 the live run's background was.
fn rgb_picture() -> Vec<u8> {
    encode(
        2,
        1,
        ColorType::Rgb,
        BitDepth::Eight,
        &[255, 0, 0, 51, 102, 204],
    )
}

const RGB_AS_BGRA: [u8; 8] = [0, 0, 255, 255, 204, 102, 51, 255];

fn display() -> CaptureRequest {
    CaptureRequest::targeted(0, 0, CaptureTarget::Display)
}

fn calls(portal: &FakePortal) -> Vec<Call> {
    portal
        .calls
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone()
}

fn backend(result: Result<impl std::fmt::Debug, CaptureError>) -> String {
    match result {
        Err(CaptureError::Backend(message)) => message,
        other => panic!("expected a backend error, got {other:?}"),
    }
}

#[test]
fn a_display_capture_reads_the_picture_and_removes_its_file() {
    let portal = FakePortal::answering(success());

    let captured = LinuxPortalCapture::new(&portal)
        .capture(&display())
        .unwrap();

    assert_eq!(captured.frame().width(), 2);
    assert_eq!(captured.frame().height(), 1);
    assert_eq!(captured.frame().pixels(), RGB_AS_BGRA);
    let handle = "/org/freedesktop/portal/desktop/request/1_16/cortex0";
    let file = PathBuf::from("/tmp/out.png");
    assert_eq!(
        calls(&portal),
        vec![
            Call::Sender,
            Call::Screenshot(String::from(handle), String::from("cortex0")),
            Call::Read(file.clone()),
            Call::Remove(file),
        ]
    );
}

#[test]
fn each_capture_sends_a_new_token() {
    let portal = FakePortal::answering(success());
    let backend = LinuxPortalCapture::new(&portal);

    backend.capture(&display()).unwrap();
    backend.capture(&display()).unwrap();

    let tokens: Vec<Call> = calls(&portal)
        .into_iter()
        .filter(|call| matches!(call, Call::Screenshot(..)))
        .collect();
    let root = "/org/freedesktop/portal/desktop/request/1_16";
    assert_eq!(
        tokens,
        vec![
            Call::Screenshot(format!("{root}/cortex0"), String::from("cortex0")),
            Call::Screenshot(format!("{root}/cortex1"), String::from("cortex1")),
        ]
    );
}

#[test]
fn captures_from_two_threads_run_one_at_a_time() {
    let mut portal = FakePortal::answering(success());
    portal.pause = Duration::from_millis(50);
    let backend = LinuxPortalCapture::new(&portal);

    thread::scope(|scope| {
        let other = scope.spawn(|| backend.capture(&display()).map(|_| ()));
        assert_eq!(backend.capture(&display()).map(|_| ()), Ok(()));
        assert_eq!(other.join().unwrap(), Ok(()));
    });

    assert_eq!(portal.most_in_flight.load(Ordering::SeqCst), 1);
}

#[test]
fn a_focus_capture_is_no_target_and_takes_no_picture() {
    let portal = FakePortal::answering(success());

    let result = LinuxPortalCapture::new(&portal).capture(&CaptureRequest::targeted(
        0,
        0,
        CaptureTarget::Focus,
    ));

    assert!(
        matches!(result, Err(CaptureError::NoTarget(_))),
        "{result:?}"
    );
    assert!(calls(&portal).is_empty());
}

#[test]
fn a_reply_without_a_picture_fails_before_any_file_is_touched() {
    let replies = [
        (0, None, "success with no picture uri"),
        (1, Some("file:///tmp/out.png"), "cancelled"),
        (2, None, "response 2"),
        (7, Some("file:///tmp/out.png"), "response 7"),
    ];
    for (code, uri, expected) in replies {
        let portal = FakePortal::answering(PortalReply {
            code,
            uri: uri.map(String::from),
        });

        let message = backend(LinuxPortalCapture::new(&portal).capture(&display()));

        assert!(message.contains(expected), "{code}: {message}");
        assert_eq!(calls(&portal).len(), 2, "{code}");
    }
}

#[test]
fn a_failed_portal_step_is_a_backend_error_with_its_text() {
    let mut no_sender = FakePortal::answering(success());
    no_sender.sender = Err(PortalError(String::from("no bus")));
    let mut not_unique = FakePortal::answering(success());
    not_unique.sender = Ok(String::from("org.example.Name"));
    let mut refused = FakePortal::answering(success());
    refused.reply = Err(PortalError(String::from("access denied")));
    let mut unreadable = FakePortal::answering(success());
    unreadable.file = Err(PortalError(String::from("no such file")));
    let mut kept = FakePortal::answering(success());
    kept.removal = Err(PortalError(String::from("permission denied")));
    let cases = [
        (&no_sender, "no bus", 1),
        (
            &not_unique,
            "\"org.example.Name\", which is not a unique name",
            1,
        ),
        (&refused, "access denied", 2),
        (&unreadable, "no such file", 3),
        (&kept, "permission denied", 4),
    ];
    for (portal, expected, steps) in cases {
        let message = backend(LinuxPortalCapture::new(portal).capture(&display()));

        assert!(message.contains(expected), "{message}");
        assert_eq!(calls(portal).len(), steps, "{expected}");
    }
}

#[test]
fn a_file_that_is_not_a_picture_is_still_removed() {
    let mut portal = FakePortal::answering(success());
    portal.file = Ok(b"not a png".to_vec());

    let message = backend(LinuxPortalCapture::new(&portal).capture(&display()));

    assert!(message.contains("not a readable PNG"), "{message}");
    assert_eq!(
        calls(&portal).last(),
        Some(&Call::Remove(PathBuf::from("/tmp/out.png")))
    );
}

#[test]
fn a_request_path_replaces_the_unique_name_punctuation() {
    assert_eq!(
        request_path(":1.16", "cortex0"),
        Ok(String::from(
            "/org/freedesktop/portal/desktop/request/1_16/cortex0"
        ))
    );
    assert_eq!(
        request_path(":12.3.4", "t"),
        Ok(String::from(
            "/org/freedesktop/portal/desktop/request/12_3_4/t"
        ))
    );
}

#[test]
fn a_file_uri_decodes_to_its_path() {
    let cases: [(&str, &[u8]); 4] = [
        ("file:///tmp/out.png", b"/tmp/out.png"),
        (
            "file:///home/u/Shot%20at%2004%3A50.png",
            b"/home/u/Shot at 04:50.png",
        ),
        ("file:///tmp/%e2%82%AC", "/tmp/\u{20ac}".as_bytes()),
        ("file:///tmp/%ff%25", b"/tmp/\xff%"),
    ];
    for (uri, path) in cases {
        let expected = PathBuf::from(OsString::from_vec(path.to_vec()));

        assert_eq!(file_path(uri), Ok(expected), "{uri}");
    }
}

#[test]
fn a_uri_that_is_not_a_local_file_is_refused() {
    let uris = [
        "/tmp/out.png",
        "http://example.com/out.png",
        "file://host/tmp/out.png",
        "file:///tmp/%2",
        "file:///tmp/%zz.png",
        "file:///tmp/%\u{e9}1",
    ];
    for uri in uris {
        let message = backend(file_path(uri));

        assert!(message.contains("is not a local file"), "{uri}: {message}");
    }
}

#[test]
fn rgb_and_rgba_pictures_decode_to_bgra_with_an_opaque_fourth_byte() {
    let rgba = encode(
        2,
        1,
        ColorType::Rgba,
        BitDepth::Eight,
        &[255, 0, 0, 0, 51, 102, 204, 9],
    );

    for picture in [rgb_picture(), rgba] {
        let frame = decode_png(&picture).unwrap();

        assert_eq!((frame.width(), frame.height()), (2, 1));
        assert_eq!(frame.pixels(), RGB_AS_BGRA);
    }
}

#[test]
fn palette_and_sixteen_bit_pictures_are_expanded_first() {
    let palette = encode_with(
        2,
        1,
        ColorType::Indexed,
        BitDepth::Eight,
        &[1, 0],
        Some(&[255, 0, 0, 51, 102, 204]),
    );
    let wide = encode(
        2,
        1,
        ColorType::Rgb,
        BitDepth::Sixteen,
        &[51, 0, 102, 0, 204, 0, 255, 1, 0, 2, 0, 3],
    );

    assert_eq!(
        decode_png(&palette).unwrap().pixels(),
        [204, 102, 51, 255, 0, 0, 255, 255]
    );
    assert_eq!(
        decode_png(&wide).unwrap().pixels(),
        [204, 102, 51, 255, 0, 0, 255, 255]
    );
}

#[test]
fn a_grey_picture_is_refused() {
    let grey = encode(2, 1, ColorType::Grayscale, BitDepth::Eight, &[0, 255]);

    let message = backend(decode_png(&grey));

    assert!(message.contains("Grayscale, not RGB or RGBA"), "{message}");
}

#[test]
fn a_cut_short_picture_is_refused() {
    let picture = rgb_picture();

    let message = backend(decode_png(&picture[..picture.len() - 16]));

    assert!(message.contains("not a readable PNG"), "{message}");
}

#[test]
fn a_picture_over_the_decode_limit_is_refused_from_its_header() {
    let side = 8193;
    assert!(side * side * 4 > MAX_DECODED_BYTES);
    let mut bytes = Vec::new();
    let mut encoder = png::Encoder::new(&mut bytes, 8193, 8193);
    encoder.set_color(ColorType::Rgba);
    let mut writer = encoder.write_header().unwrap();
    writer.write_chunk(png::chunk::IDAT, &[]).unwrap();
    drop(writer);

    let message = backend(decode_png(&bytes));

    assert!(message.contains("8193x8193, over the"), "{message}");
}
