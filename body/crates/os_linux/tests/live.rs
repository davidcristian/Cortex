//! Live checks against the desktop session, `#[ignore]`d so they never run in CI or count toward
//! coverage. Run them with `just os-linux-live`, which needs a session bus and a sound server.
#![cfg(target_os = "linux")]

use body_core::{AudioControl, Notification, Notify, VolumeChange};
use os_linux::zbus::blocking::Connection;
use os_linux::{DbusNotifications, LinuxAudioControl, LinuxNotify, PACTL_PROGRAM, PactlCommand};

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
