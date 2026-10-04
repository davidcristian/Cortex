//! Live checks against the desktop session, `#[ignore]`d so they never run in CI or count toward
//! coverage. Run them with `just os-linux-live`, which needs a session bus, a sound server and an
//! X server with the XTEST extension on `DISPLAY`.
#![cfg(target_os = "linux")]

use std::sync::mpsc;
use std::thread;
use std::time::Duration;

use body_core::{
    AudioControl, CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, Hotkey, HotkeyChord,
    Notification, Notify, ScreenCapture, TargetRect, VolumeChange,
};
use os_linux::x11rb::connection::Connection as _;
use os_linux::x11rb::protocol::xproto::{KEY_PRESS_EVENT, KEY_RELEASE_EVENT};
use os_linux::x11rb::protocol::xtest::ConnectionExt as _;
use os_linux::x11rb::wrapper::ConnectionExt as _;
use os_linux::zbus::blocking::Connection;
use os_linux::{
    DbusNotifications, KeyGrab, LinuxAudioControl, LinuxHotkey, LinuxNotify, LinuxScreenCapture,
    PACTL_PROGRAM, PactlCommand, X11Keys, X11Root,
};

#[test]
#[ignore = "needs a desktop session bus with a notification server"]
fn a_notification_shows_on_the_session_bus() {
    let connection = Connection::session().unwrap();
    let notify = LinuxNotify::new("Cortex", DbusNotifications::new(connection));

    let shown = notify.show(&Notification::new(
        "Cortex live check",
        "The Linux notification backend reached the session bus <b>escaped</b>.",
        "live",
        true,
    ));

    assert_eq!(shown, Ok(true));
}

#[test]
#[ignore = "needs a PulseAudio or pipewire-pulse server and pactl"]
fn the_default_sink_volume_round_trips() {
    let audio = LinuxAudioControl::new(PactlCommand::new(PACTL_PROGRAM));
    let before = audio.get_volume().unwrap();
    let target = if before.level > 0.5 { 0.25 } else { 0.75 };

    let changed = audio
        .set_volume(VolumeChange::new(Some(target), Some(!before.muted)))
        .unwrap();
    let restored = audio
        .set_volume(VolumeChange::new(Some(before.level), Some(before.muted)))
        .unwrap();

    assert!(
        (changed.level - target).abs() < 1.0 / 65536.0,
        "{changed:?}"
    );
    assert_eq!(changed.muted, !before.muted);
    assert!(
        (restored.level - before.level).abs() < 1.0 / 65536.0,
        "{restored:?}"
    );
    assert_eq!(restored.muted, before.muted);
}

/// Maps a white `size` square at `at` on the root, naming `pid` in `_NET_WM_PID` and `title` in
/// `WM_NAME` when given them.
fn white_square(
    at: i16,
    size: u16,
    pid: Option<u32>,
    title: Option<&[u8]>,
) -> os_linux::x11rb::rust_connection::RustConnection {
    use os_linux::x11rb::protocol::xproto::{
        AtomEnum, ConnectionExt as _, CreateWindowAux, PropMode, WindowClass,
    };

    let (connection, screen) =
        os_linux::x11rb::connect(None).unwrap_or_else(|error| panic!("{error:?}"));
    let root = &connection.setup().roots[screen];
    let window = connection
        .generate_id()
        .unwrap_or_else(|error| panic!("{error:?}"));
    let aux = CreateWindowAux::new().background_pixel(root.white_pixel);
    connection
        .create_window(
            0,
            window,
            root.root,
            at,
            at,
            size,
            size,
            0,
            WindowClass::INPUT_OUTPUT,
            0,
            &aux,
        )
        .unwrap_or_else(|error| panic!("{error:?}"));
    if let Some(pid) = pid {
        let name = connection
            .intern_atom(false, b"_NET_WM_PID")
            .unwrap_or_else(|error| panic!("{error:?}"))
            .reply()
            .unwrap_or_else(|error| panic!("{error:?}"));
        connection
            .change_property32(
                PropMode::REPLACE,
                window,
                name.atom,
                AtomEnum::CARDINAL,
                &[pid],
            )
            .unwrap_or_else(|error| panic!("{error:?}"));
    }
    if let Some(title) = title {
        connection
            .change_property8(
                PropMode::REPLACE,
                window,
                AtomEnum::WM_NAME,
                AtomEnum::STRING,
                title,
            )
            .unwrap_or_else(|error| panic!("{error:?}"));
    }
    connection
        .map_window(window)
        .unwrap_or_else(|error| panic!("{error:?}"));
    connection
        .sync()
        .unwrap_or_else(|error| panic!("{error:?}"));
    thread::sleep(Duration::from_millis(200));
    connection
}

#[test]
#[ignore = "needs an X server on DISPLAY"]
fn the_root_window_is_captured_with_this_process_painted_black() {
    let (connection, screen) = os_linux::x11rb::connect(None).unwrap();
    let capture = LinuxScreenCapture::new(X11Root::new(connection, screen), std::process::id());
    assert!(capture.capture(&CaptureRequest::new(0)).is_err());
    let _below = white_square(0, 40, None, None);
    let _ours = white_square(10, 20, Some(std::process::id()), None);

    let frame = capture.capture(&CaptureRequest::new(0)).unwrap();
    let width = usize::try_from(frame.frame().width()).unwrap();
    let pixel = |x: usize, y: usize| &frame.frame().pixels()[(y * width + x) * 4..][..3];

    assert_eq!(pixel(5, 5), [255, 255, 255]);
    assert_eq!(pixel(15, 15), [0, 0, 0]);
    assert_eq!(pixel(29, 29), [0, 0, 0]);
    assert_eq!(pixel(30, 30), [255, 255, 255]);
}

#[test]
#[ignore = "needs an X server on DISPLAY"]
fn a_focus_capture_points_at_the_topmost_titled_window_that_is_not_ours() {
    let (connection, screen) = os_linux::x11rb::connect(None).unwrap();
    let capture = LinuxScreenCapture::new(X11Root::new(connection, screen), std::process::id());
    let focus = CaptureRequest::targeted(0, 0, CaptureTarget::Focus);
    let _ours = white_square(0, 5, Some(std::process::id()), Some(b"overlay"));
    assert!(matches!(
        capture.capture(&focus),
        Err(CaptureError::NoTarget(_))
    ));
    let _lower = white_square(40, 10, None, Some(b"lower"));
    let _target = white_square(10, 20, None, Some(b"target"));
    let _untitled = white_square(20, 30, None, None);
    let _overlay = white_square(25, 5, Some(std::process::id()), Some(b"overlay"));

    let captured = capture.capture(&focus).unwrap();

    let rect = TargetRect::new(10, 10, 30, 30);
    assert_eq!(
        captured,
        CapturedFrame::window(captured.frame().clone(), rect)
    );
}

#[test]
#[ignore = "needs an X server with the XTEST extension on DISPLAY"]
fn a_grabbed_chord_fires_once_per_press_with_and_without_num_lock() {
    let (connection, screen) = os_linux::x11rb::connect(None).unwrap();
    let hotkey = LinuxHotkey::new(X11Keys::new(connection, screen));
    let (fired, on_fire) = mpsc::channel();
    let chord = HotkeyChord::default();
    hotkey
        .register(&chord, Box::new(move || fired.send(()).unwrap()))
        .unwrap();

    let (presser, screen) = os_linux::x11rb::connect(None).unwrap();
    let root = presser.setup().roots[screen].root;
    let keyboard = X11Keys::new(os_linux::x11rb::connect(None).unwrap().0, screen)
        .keyboard()
        .unwrap();
    let per = usize::from(keyboard.keysyms_per_keycode);
    let keycode = |keysym: u32| {
        let index = keyboard
            .keysyms
            .chunks(per)
            .position(|keysyms| keysyms.contains(&keysym))
            .unwrap();
        u8::try_from(index).unwrap() + keyboard.min_keycode
    };
    let (control, alt, space, num_lock) = (
        keycode(0xffe3),
        keycode(0xffe9),
        keycode(0x20),
        keycode(0xff7f),
    );
    let press_for = |keys: &[u8], held: Duration| {
        for &key in keys {
            presser
                .xtest_fake_input(KEY_PRESS_EVENT, key, 0, root, 0, 0, 0)
                .unwrap();
        }
        presser.sync().unwrap();
        thread::sleep(held);
        for &key in keys.iter().rev() {
            presser
                .xtest_fake_input(KEY_RELEASE_EVENT, key, 0, root, 0, 0, 0)
                .unwrap();
        }
        presser.sync().unwrap();
        thread::sleep(Duration::from_millis(50));
    };
    // Each tap lasts 50 ms: two instant taps share one server time, which reads as an auto-repeat.
    let tap = |keys: &[u8]| press_for(keys, Duration::from_millis(50));

    tap(&[control, alt, space]);
    let plain = on_fire.recv_timeout(Duration::from_secs(5));
    tap(&[num_lock]);
    tap(&[control, alt, space]);
    let with_num_lock = on_fire.recv_timeout(Duration::from_secs(5));
    tap(&[num_lock]);
    tap(&[control, space]);
    let without_alt = on_fire.recv_timeout(Duration::from_millis(500));
    press_for(&[control, alt, space], Duration::from_millis(1500));
    thread::sleep(Duration::from_millis(200));
    let held = on_fire.try_iter().count();

    eprintln!(
        "{chord} on keycodes {control}+{alt}+{space}: plain {plain:?}, with Num Lock \
         {with_num_lock:?}, ctrl+space alone {without_alt:?}, held 1.5 s {held} run(s)"
    );
    assert_eq!((plain, with_num_lock), (Ok(()), Ok(())));
    assert!(without_alt.is_err());
    assert_eq!(held, 1);
}
