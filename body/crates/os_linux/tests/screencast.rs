#![cfg(target_os = "linux")]

use std::collections::VecDeque;
use std::fs::File;
use std::io::{Read, Write};
use std::os::fd::OwnedFd;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Mutex, PoisonError};
use std::thread;
use std::time::Duration;

use body_core::{CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, ScreenCapture};
use os_linux::{
    CastSession, FrameError, FrameReader, LinuxWindowCapture, NO_WINDOW, PortalError,
    RESTORE_LIMIT, ScreenCastPortal, Started, WindowStream, decode_png, offers_window,
};
use png::{BitDepth, ColorType};

const MINUTE: Duration = Duration::from_mins(1);

/// The value of a setup step that cannot fail in a working test environment.
fn ok<T, E: std::fmt::Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("a setup step failed: {error:?}"))
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum Call {
    Start(Option<String>, Duration),
    Read(u32, String),
    Close(String),
}

#[derive(Clone, Copy)]
enum Answer {
    Stream(u32, Option<&'static str>),
    Refused(u32),
    Expired,
    Fail(&'static str),
}

/// A portal and a frame reader that answer as scripted and record every call in one log.
struct Fake {
    types: Result<u32, PortalError>,
    answers: Mutex<VecDeque<Answer>>,
    picture: Result<Vec<u8>, FrameError>,
    calls: Mutex<Vec<Call>>,
    sessions: AtomicUsize,
    pause: Duration,
    in_flight: AtomicUsize,
    most_in_flight: AtomicUsize,
}

impl Fake {
    fn answering(answers: &[Answer]) -> Self {
        Self {
            types: Ok(3),
            answers: Mutex::new(answers.iter().copied().collect()),
            picture: Ok(picture()),
            calls: Mutex::new(Vec::new()),
            sessions: AtomicUsize::new(0),
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

    fn calls(&self) -> Vec<Call> {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

/// A pipe whose reading end holds `text`, in place of the `PipeWire` descriptor.
fn remote(text: &str) -> OwnedFd {
    let (reader, mut writer) = ok(std::io::pipe());
    ok(writer.write_all(text.as_bytes()));
    OwnedFd::from(reader)
}

impl ScreenCastPortal for &Fake {
    fn source_types(&self) -> Result<u32, PortalError> {
        self.types.clone()
    }

    fn start(&self, restore: Option<&str>, limit: Duration) -> Result<CastSession, PortalError> {
        self.record(Call::Start(restore.map(String::from), limit));
        let now = self.in_flight.fetch_add(1, Ordering::SeqCst) + 1;
        self.most_in_flight.fetch_max(now, Ordering::SeqCst);
        thread::sleep(self.pause);
        self.in_flight.fetch_sub(1, Ordering::SeqCst);
        let answer = self
            .answers
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .pop_front();
        let started = match answer {
            Some(Answer::Stream(node, restore)) => Started::Stream(WindowStream {
                node,
                restore: restore.map(String::from),
                remote: remote(&format!("node {node}")),
            }),
            Some(Answer::Refused(code)) => Started::Refused(code),
            Some(Answer::Expired) => Started::Expired,
            Some(Answer::Fail(text)) => return Err(PortalError(String::from(text))),
            None => panic!("the portal was started more often than scripted"),
        };
        let session = self.sessions.fetch_add(1, Ordering::SeqCst);
        Ok(CastSession {
            handle: format!("/session/{session}"),
            started,
        })
    }

    fn close(&self, handle: &str) {
        self.record(Call::Close(String::from(handle)));
    }
}

impl FrameReader for &Fake {
    fn read(&self, remote: OwnedFd, node: u32) -> Result<Vec<u8>, FrameError> {
        let mut text = String::new();
        ok(File::from(remote).read_to_string(&mut text));
        self.record(Call::Read(node, text));
        self.picture.clone()
    }
}

/// A 2 by 1 RGB picture: a red pixel, then a blue one.
fn picture() -> Vec<u8> {
    let mut bytes = Vec::new();
    let mut encoder = png::Encoder::new(&mut bytes, 2, 1);
    encoder.set_color(ColorType::Rgb);
    encoder.set_depth(BitDepth::Eight);
    let mut writer = ok(encoder.write_header());
    ok(writer.write_image_data(&[255, 0, 0, 51, 102, 204]));
    ok(writer.finish());
    bytes
}

fn window(fake: &Fake) -> LinuxWindowCapture<&Fake, &Fake> {
    LinuxWindowCapture::new(fake, fake)
}

/// A capture whose window was chosen, its chooser calls cleared from the log.
fn chosen(fake: &Fake) -> LinuxWindowCapture<&Fake, &Fake> {
    let capture = window(fake);
    assert_eq!(capture.choose(MINUTE), Ok(true));
    fake.calls
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clear();
    capture
}

fn focus() -> CaptureRequest {
    CaptureRequest::targeted(0, 0, CaptureTarget::Focus)
}

fn start(token: &str) -> Call {
    Call::Start(Some(String::from(token)), RESTORE_LIMIT)
}

fn close(session: usize) -> Call {
    Call::Close(format!("/session/{session}"))
}

fn no_window(result: Result<CapturedFrame, CaptureError>) {
    match result {
        Err(CaptureError::NoTarget(message)) => assert_eq!(message, NO_WINDOW),
        other => panic!("expected no window chosen, got {other:?}"),
    }
}

fn backend(result: Result<CapturedFrame, CaptureError>) -> String {
    match result {
        Err(CaptureError::Backend(message)) => message,
        other => panic!("expected a backend error, got {other:?}"),
    }
}

#[test]
fn a_focus_capture_with_no_window_chosen_asks_for_a_choice_and_calls_nothing() {
    let fake = Fake::answering(&[]);
    let capture = window(&fake);
    assert!(!capture.choice_wanted());

    no_window(capture.capture(&focus()));

    assert!(capture.choice_wanted());
    assert!(fake.calls().is_empty());
}

#[test]
fn a_display_request_is_refused_without_a_portal_call() {
    let fake = Fake::answering(&[Answer::Stream(1, Some("t1"))]);
    let capture = chosen(&fake);

    let message = backend(capture.capture(&CaptureRequest::targeted(0, 0, CaptureTarget::Display)));

    assert!(message.contains("not the display"), "{message}");
    assert!(fake.calls().is_empty());
    assert!(!capture.choice_wanted());
}

#[test]
fn a_chosen_window_is_read_alone_through_a_restored_session() {
    let answers = [
        Answer::Stream(7, Some("t1")),
        Answer::Stream(9, Some("t2")),
        Answer::Stream(11, Some("t3")),
    ];
    let fake = Fake::answering(&answers);
    let capture = chosen(&fake);

    let captured = capture.capture(&focus());
    capture.capture(&focus()).map(|_| ()).unwrap();

    assert_eq!(
        captured,
        Ok(CapturedFrame::window_only(decode_png(&picture()).unwrap()))
    );
    assert_eq!(
        fake.calls(),
        vec![
            start("t1"),
            Call::Read(9, String::from("node 9")),
            close(1),
            start("t2"),
            Call::Read(11, String::from("node 11")),
            close(2),
        ]
    );
}

#[test]
fn a_restored_session_that_does_not_start_is_closed_and_its_token_forgotten() {
    for refusal in [Answer::Expired, Answer::Refused(2)] {
        let fake = Fake::answering(&[Answer::Stream(1, Some("t1")), refusal]);
        let capture = chosen(&fake);

        let first = capture.capture(&focus());
        let wanted = capture.choice_wanted();
        let second = capture.capture(&focus());

        match refusal {
            Answer::Refused(_) => assert!(backend(first).contains("with response 2")),
            _ => no_window(first),
        }
        assert!(wanted);
        no_window(second);
        assert_eq!(fake.calls(), vec![start("t1"), close(1)]);
    }
}

#[test]
fn a_start_whose_call_failed_keeps_the_token_for_the_next_capture() {
    let answers = [
        Answer::Stream(1, Some("t1")),
        Answer::Fail("no bus"),
        Answer::Stream(2, Some("t2")),
    ];
    let fake = Fake::answering(&answers);
    let capture = chosen(&fake);

    assert_eq!(backend(capture.capture(&focus())), "no bus");
    assert!(capture.capture(&focus()).is_ok());

    assert!(!capture.choice_wanted());
    assert_eq!(fake.calls()[..2], [start("t1"), start("t1")]);
}

#[test]
fn a_frame_that_cannot_be_read_still_closes_its_session_and_keeps_the_new_token() {
    let cases = [
        (
            Err(FrameError(String::from("gst-launch-1.0 exited with 1"))),
            "exited with 1",
        ),
        (Ok(b"not a png".to_vec()), "not a readable PNG"),
    ];
    for (picture, expected) in cases {
        let answers = [Answer::Stream(1, Some("t1")), Answer::Stream(2, Some("t2"))];
        let mut fake = Fake::answering(&answers);
        fake.picture = picture;
        let capture = chosen(&fake);

        let message = backend(capture.capture(&focus()));
        fake.answers
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push_back(Answer::Expired);
        let _ = capture.capture(&focus());

        assert!(message.contains(expected), "{message}");
        assert_eq!(fake.calls()[2..4], [close(1), start("t2")]);
    }
}

#[test]
fn a_stream_with_no_new_token_leaves_no_window_chosen() {
    let fake = Fake::answering(&[Answer::Stream(1, Some("t1")), Answer::Stream(2, None)]);
    let capture = chosen(&fake);

    assert!(capture.capture(&focus()).is_ok());
    no_window(capture.capture(&focus()));

    assert_eq!(fake.calls().len(), 3);
}

#[test]
fn captures_from_two_threads_start_one_session_at_a_time() {
    let answers = [
        Answer::Stream(1, Some("t1")),
        Answer::Stream(2, Some("t2")),
        Answer::Stream(3, Some("t3")),
    ];
    let mut fake = Fake::answering(&answers);
    fake.pause = Duration::from_millis(50);
    let capture = chosen(&fake);

    thread::scope(|scope| {
        let other = scope.spawn(|| capture.capture(&focus()).map(|_| ()));
        assert_eq!(capture.capture(&focus()).map(|_| ()), Ok(()));
        assert_eq!(other.join().unwrap(), Ok(()));
    });

    assert_eq!(fake.most_in_flight.load(Ordering::SeqCst), 1);
    let starts: Vec<Call> = fake
        .calls()
        .into_iter()
        .filter(|call| matches!(call, Call::Start(..)))
        .collect();
    assert_eq!(starts, [start("t1"), start("t2")]);
}

#[test]
fn a_chooser_that_ends_without_a_token_keeps_nothing() {
    for answer in [Answer::Refused(1), Answer::Expired, Answer::Stream(4, None)] {
        let fake = Fake::answering(&[answer]);
        let capture = window(&fake);
        no_window(capture.capture(&focus()));

        assert_eq!(capture.choose(MINUTE), Ok(false));
        assert!(!capture.choice_wanted());
        no_window(capture.capture(&focus()));

        assert_eq!(fake.calls(), [Call::Start(None, MINUTE), close(0)]);
    }
}

#[test]
fn a_chooser_whose_call_failed_returns_the_error_and_closes_nothing() {
    let fake = Fake::answering(&[Answer::Fail("access denied")]);
    let capture = window(&fake);

    assert_eq!(
        capture.choose(MINUTE),
        Err(PortalError(String::from("access denied")))
    );

    assert_eq!(fake.calls(), [Call::Start(None, MINUTE)]);
}

#[test]
fn a_window_source_is_bit_two_of_the_source_types() {
    for (types, offered) in [(1, false), (2, true), (3, true), (5, false)] {
        let mut fake = Fake::answering(&[]);
        fake.types = Ok(types);

        assert_eq!(offers_window(&&fake), Ok(offered), "{types}");
    }
    let mut fake = Fake::answering(&[]);
    fake.types = Err(PortalError(String::from("no bus")));

    assert_eq!(
        offers_window(&&fake),
        Err(PortalError(String::from("no bus")))
    );
}
