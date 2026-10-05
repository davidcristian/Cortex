#![cfg(target_os = "linux")]

use std::collections::VecDeque;
use std::os::fd::OwnedFd;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Condvar, Mutex, MutexGuard, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use body_core::{CaptureError, CaptureRequest, CaptureTarget, ScreenCapture};
use os_linux::{
    CHOOSER_LIMIT, CastSession, FrameError, FrameReader, HideSignal, LinuxWindowCapture,
    PortalError, RESTORE_LIMIT, ScreenCastPortal, Started, WatchedWindowCapture, WindowStream,
};

const PATIENCE: Duration = Duration::from_secs(10);

fn lock<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex.lock().unwrap_or_else(PoisonError::into_inner)
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum Call {
    Start(Option<String>, Duration),
    Close(String),
}

#[derive(Clone, Copy)]
enum Answer {
    Token(Option<&'static str>),
    Held(Option<&'static str>),
    Fail(&'static str),
}

/// A portal that answers as scripted, holding a `Held` answer until the test releases it.
struct Portal {
    answers: Mutex<VecDeque<Answer>>,
    calls: Mutex<Vec<Call>>,
    release: Mutex<Receiver<()>>,
}

#[derive(Clone)]
struct Shared(Arc<Portal>);

impl ScreenCastPortal for Shared {
    fn source_types(&self) -> Result<u32, PortalError> {
        Ok(3)
    }

    fn start(&self, restore: Option<&str>, limit: Duration) -> Result<CastSession, PortalError> {
        lock(&self.0.calls).push(Call::Start(restore.map(String::from), limit));
        let answer = lock(&self.0.answers).pop_front();
        let token = match answer {
            Some(Answer::Token(token)) => token,
            Some(Answer::Held(token)) => {
                let _ = lock(&self.0.release).recv();
                token
            }
            Some(Answer::Fail(text)) => return Err(PortalError(String::from(text))),
            None => panic!("the portal was started more often than scripted"),
        };
        let (remote, _) = std::io::pipe().unwrap_or_else(|error| panic!("no pipe: {error}"));
        Ok(CastSession {
            handle: String::from("/session"),
            started: Started::Stream(WindowStream {
                node: 1,
                restore: token.map(String::from),
                remote: OwnedFd::from(remote),
            }),
        })
    }

    fn close(&self, handle: &str) {
        lock(&self.0.calls).push(Call::Close(String::from(handle)));
    }
}

impl FrameReader for Shared {
    fn read(&self, _remote: OwnedFd, _node: u32) -> Result<Vec<u8>, FrameError> {
        Err(FrameError(String::from("no frame in this test")))
    }
}

/// A hide signal the test drives, which records the count each wait was given.
#[derive(Default)]
struct Signal {
    state: Mutex<(VecDeque<u64>, Vec<u64>)>,
    changed: Condvar,
}

impl HideSignal for Signal {
    fn next_hide(&self, seen: u64, stop: &AtomicBool) -> Option<u64> {
        let mut state = lock(&self.state);
        state.1.push(seen);
        self.changed.notify_all();
        loop {
            if stop.load(Ordering::SeqCst) {
                return None;
            }
            if let Some(hide) = state.0.pop_front() {
                return Some(hide);
            }
            state = self
                .changed
                .wait(state)
                .unwrap_or_else(PoisonError::into_inner);
        }
    }

    fn wake(&self) {
        let _state = lock(&self.state);
        self.changed.notify_all();
    }
}

impl Signal {
    fn hide(&self, count: u64) {
        lock(&self.state).0.push_back(count);
        self.changed.notify_all();
    }

    /// The counts the thread waited with, once it has waited `times` times.
    fn waited(&self, times: usize) -> Vec<u64> {
        let deadline = Instant::now() + PATIENCE;
        let mut state = lock(&self.state);
        while state.1.len() < times {
            assert!(Instant::now() < deadline, "waited {:?}", state.1);
            state = self
                .changed
                .wait_timeout(state, Duration::from_millis(10))
                .unwrap_or_else(PoisonError::into_inner)
                .0;
        }
        state.1.clone()
    }
}

struct Rig {
    portal: Arc<Portal>,
    signal: Arc<Signal>,
    release: Sender<()>,
}

fn rig(answers: &[Answer]) -> (Rig, LinuxWindowCapture<Shared, Shared>) {
    let (release, held) = channel();
    let portal = Arc::new(Portal {
        answers: Mutex::new(answers.iter().copied().collect()),
        calls: Mutex::new(Vec::new()),
        release: Mutex::new(held),
    });
    let shared = Shared(Arc::clone(&portal));
    let rig = Rig {
        portal,
        signal: Arc::new(Signal::default()),
        release,
    };
    (rig, LinuxWindowCapture::new(shared.clone(), shared))
}

impl Rig {
    fn calls(&self) -> Vec<Call> {
        lock(&self.portal.calls).clone()
    }

    fn watch(&self, window: LinuxWindowCapture<Shared, Shared>) -> Watched {
        window.watch_hides(self.signal.clone(), CHOOSER_LIMIT)
    }

    fn until_started(&self, starts: usize) {
        let deadline = Instant::now() + PATIENCE;
        while self
            .calls()
            .iter()
            .filter(|call| matches!(call, Call::Start(..)))
            .count()
            < starts
        {
            assert!(Instant::now() < deadline, "{:?}", self.calls());
            thread::sleep(Duration::from_millis(1));
        }
    }
}

type Watched = WatchedWindowCapture<Shared, Shared>;

fn focus() -> CaptureRequest {
    CaptureRequest::targeted(0, 0, CaptureTarget::Focus)
}

fn refused(capture: &dyn ScreenCapture) {
    let result = capture.capture(&focus());
    assert!(
        matches!(result, Err(CaptureError::NoTarget(_))),
        "{result:?}"
    );
}

fn chooser() -> Call {
    Call::Start(None, Duration::from_mins(1))
}

fn closed() -> Call {
    Call::Close(String::from("/session"))
}

#[test]
fn a_hide_while_a_choice_is_wanted_opens_the_chooser_for_a_minute() {
    let (rig, window) = rig(&[Answer::Token(Some("t1")), Answer::Fail("stop")]);
    refused(&window);
    let watched = rig.watch(window);

    rig.signal.hide(4);

    assert_eq!(rig.signal.waited(2), [0, 4]);
    assert!(!watched.window().choice_wanted());
    let message = watched.capture(&focus()).map(|_| ());
    assert_eq!(message, Err(CaptureError::Backend(String::from("stop"))));
    assert_eq!(
        rig.calls(),
        [
            chooser(),
            closed(),
            Call::Start(Some(String::from("t1")), RESTORE_LIMIT)
        ]
    );
}

#[test]
fn a_hide_with_no_choice_wanted_opens_nothing() {
    let (rig, window) = rig(&[]);
    let _watched = rig.watch(window);

    rig.signal.hide(1);
    rig.signal.hide(2);

    assert_eq!(rig.signal.waited(3), [0, 1, 2]);
    assert!(rig.calls().is_empty());
}

#[test]
fn a_hide_while_a_chooser_is_open_waits_for_it_and_opens_no_second_one() {
    let (rig, window) = rig(&[Answer::Held(None), Answer::Token(None)]);
    refused(&window);
    let _watched = rig.watch(window);

    rig.signal.hide(1);
    rig.until_started(1);
    rig.signal.hide(2);
    let _ = rig.release.send(());

    assert_eq!(rig.signal.waited(3), [0, 1, 2]);
    assert_eq!(rig.calls(), [chooser(), closed()]);
}

#[test]
fn a_capture_refused_while_the_chooser_is_open_wants_nothing_once_a_window_is_kept() {
    let (rig, window) = rig(&[Answer::Held(Some("t1")), Answer::Token(None)]);
    refused(&window);
    let watched = rig.watch(window);

    rig.signal.hide(1);
    rig.until_started(1);
    refused(&watched);
    rig.signal.hide(2);
    let _ = rig.release.send(());

    assert_eq!(rig.signal.waited(3), [0, 1, 2]);
    assert!(!watched.window().choice_wanted());
    assert_eq!(rig.calls(), [chooser(), closed()]);
}

#[test]
fn a_chooser_whose_call_failed_is_opened_again_at_the_next_hide_a_capture_wants() {
    let (rig, window) = rig(&[Answer::Fail("access denied"), Answer::Token(Some("t2"))]);
    refused(&window);
    let watched = rig.watch(window);

    rig.signal.hide(1);
    assert_eq!(rig.signal.waited(2), [0, 1]);
    refused(&watched);
    rig.signal.hide(2);

    assert_eq!(rig.signal.waited(3), [0, 1, 2]);
    assert_eq!(rig.calls(), [chooser(), chooser(), closed()]);
}

#[test]
fn dropping_the_watched_capture_ends_its_thread_and_lets_the_portal_go() {
    let (rig, window) = rig(&[]);
    let watched = rig.watch(window);
    rig.signal.waited(1);

    drop(watched);

    let deadline = Instant::now() + PATIENCE;
    while Arc::strong_count(&rig.portal) > 1 {
        assert!(Instant::now() < deadline, "the chooser thread still runs");
        thread::sleep(Duration::from_millis(1));
    }
    assert!(rig.calls().is_empty());
}
