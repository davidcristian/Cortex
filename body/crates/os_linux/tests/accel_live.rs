//! A live check of the `kglobalaccel` hotkey, `#[ignore]`d so it never runs in CI or counts toward
//! coverage. It needs a KDE session bus and someone to press `ctrl+alt+space` while it waits.
#![cfg(target_os = "linux")]

use std::sync::mpsc;
use std::time::Duration;

use body_core::{Hotkey, HotkeyChord};
use os_linux::zbus::blocking::Connection;
use os_linux::{DbusGlobalAccel, LinuxKdeHotkey, kglobalaccel_running};

#[test]
#[ignore = "needs a KDE session bus and a person pressing the chord"]
fn a_tap_a_hold_and_a_tap_run_the_callback_three_times() {
    let connection = Connection::session().unwrap_or_else(|error| panic!("{error}"));
    assert!(kglobalaccel_running(&connection), "no kglobalaccel");
    let hotkey = LinuxKdeHotkey::new(DbusGlobalAccel::new(connection), "Cortex live test");
    let chord = HotkeyChord::default();
    let (fired, on_fire) = mpsc::channel();

    let registered = hotkey.register(
        &chord,
        Box::new(move || fired.send(()).unwrap_or_else(|error| panic!("{error}"))),
    );
    eprintln!("registered {chord}: {registered:?}; press it, hold it a second, press it again");

    assert_eq!(registered, Ok(()));
    for run in 1..=3 {
        assert_eq!(
            on_fire.recv_timeout(Duration::from_mins(1)),
            Ok(()),
            "run {run}"
        );
        eprintln!("run {run}");
    }
    assert!(on_fire.recv_timeout(Duration::from_secs(2)).is_err());
}
