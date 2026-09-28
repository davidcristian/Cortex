//! Live checks against the desktop session, `#[ignore]`d so they never run in CI or count toward
//! coverage. Run them with `just os-linux-live`, which needs a session bus, a sound server and an
//! X server on `DISPLAY`.
#![cfg(target_os = "linux")]

use body_core::{AudioControl, CaptureRequest, Notification, Notify, ScreenCapture, VolumeChange};
use os_linux::zbus::blocking::Connection;
use os_linux::{
    DbusNotifications, LinuxAudioControl, LinuxNotify, LinuxScreenCapture, PACTL_PROGRAM,
    PactlCommand, X11Root,
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

#[test]
#[ignore = "needs an X server on DISPLAY"]
fn the_root_window_is_captured() {
    let (connection, screen) = os_linux::x11rb::connect(None).unwrap();
    let capture = LinuxScreenCapture::new(X11Root::new(connection, screen));

    let frame = capture.capture(&CaptureRequest::new(0)).unwrap();
    let pixels = frame.frame().pixels();
    let lit = pixels
        .chunks_exact(4)
        .filter(|pixel| pixel[..3] != [0, 0, 0])
        .count();

    eprintln!(
        "captured {}x{}, {lit} of {} pixels not black",
        frame.frame().width(),
        frame.frame().height(),
        pixels.len() / 4
    );
}
