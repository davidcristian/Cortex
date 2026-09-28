#![cfg(target_os = "linux")]

use std::collections::HashMap;
use std::sync::{Mutex, PoisonError};

use body_core::{AudioControl, AudioError, VolumeChange, VolumeState};
use os_linux::{LinuxAudioControl, PactlFailure, PactlRunner};

const STEREO_40: &str = "Volume: front-left: 26214 /  40% / -23.88 dB,   front-right: 26214 /  40% / -23.88 dB\n        balance 0.00\n";

/// A fake `pactl`: answers each subcommand from a script and records every call's arguments.
struct FakePactl {
    replies: HashMap<&'static str, Result<String, PactlFailure>>,
    calls: Mutex<Vec<Vec<String>>>,
}

impl FakePactl {
    fn new(volume: &str, mute: &str) -> Self {
        let mut replies = HashMap::new();
        replies.insert("get-sink-volume", Ok(String::from(volume)));
        replies.insert("get-sink-mute", Ok(String::from(mute)));
        replies.insert("set-sink-volume", Ok(String::new()));
        replies.insert("set-sink-mute", Ok(String::new()));
        Self {
            replies,
            calls: Mutex::new(Vec::new()),
        }
    }

    fn failing(mut self, subcommand: &'static str, failure: PactlFailure) -> Self {
        self.replies.insert(subcommand, Err(failure));
        self
    }

    fn calls(&self) -> Vec<Vec<String>> {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

impl PactlRunner for &FakePactl {
    fn run(&self, args: &[&str]) -> Result<String, PactlFailure> {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(args.iter().map(|arg| String::from(*arg)).collect());
        self.replies[args[0]].clone()
    }
}

fn args(list: &[&str]) -> Vec<String> {
    list.iter().map(|arg| String::from(*arg)).collect()
}

#[test]
fn the_level_is_the_mean_raw_channel_volume_over_the_norm() {
    let pactl = FakePactl::new(
        "Volume: front-left: 16384 /  25% / -36.12 dB,   front-right: 49152 /  75% / -7.50 dB\n",
        "Mute: no\n",
    );

    let state = LinuxAudioControl::new(&pactl).get_volume();

    assert_eq!(
        state,
        Ok(VolumeState {
            level: 0.5,
            muted: false
        })
    );
    assert_eq!(
        pactl.calls(),
        vec![
            args(&["get-sink-volume", "@DEFAULT_SINK@"]),
            args(&["get-sink-mute", "@DEFAULT_SINK@"]),
        ]
    );
}

#[test]
fn a_mono_sink_and_a_muted_one_read_correctly() {
    let pactl = FakePactl::new("Volume: mono: 65536 / 100% / 0.00 dB\n", "Mute: yes\n");

    let state = LinuxAudioControl::new(&pactl).get_volume();

    assert_eq!(
        state,
        Ok(VolumeState {
            level: 1.0,
            muted: true
        })
    );
}

#[test]
fn a_boost_past_the_norm_reads_as_full_volume() {
    let pactl = FakePactl::new("Volume: mono: 98304 / 150% / 10.57 dB\n", "Mute: no\n");

    let state = LinuxAudioControl::new(&pactl).get_volume().unwrap();

    assert!((state.level - 1.0).abs() < f32::EPSILON);
}

#[test]
fn setting_a_level_writes_the_raw_volume_then_reads_back() {
    let pactl = FakePactl::new(STEREO_40, "Mute: no\n");

    let state = LinuxAudioControl::new(&pactl).set_volume(VolumeChange::new(Some(0.4), None));

    assert!((state.unwrap().level - 0.4).abs() < 1.0 / 65536.0);
    assert_eq!(
        pactl.calls()[0],
        args(&["set-sink-volume", "@DEFAULT_SINK@", "26214"])
    );
    assert_eq!(pactl.calls().len(), 3);
}

#[test]
fn muting_and_unmuting_write_one_and_zero() {
    for (mute, flag) in [(true, "1"), (false, "0")] {
        let pactl = FakePactl::new(STEREO_40, "Mute: no\n");

        LinuxAudioControl::new(&pactl)
            .set_volume(VolumeChange::new(None, Some(mute)))
            .unwrap();

        assert_eq!(
            pactl.calls()[0],
            args(&["set-sink-mute", "@DEFAULT_SINK@", flag])
        );
    }
}

#[test]
fn an_empty_change_only_reads() {
    let pactl = FakePactl::new(STEREO_40, "Mute: no\n");

    LinuxAudioControl::new(&pactl)
        .set_volume(VolumeChange::new(None, None))
        .unwrap();

    assert_eq!(pactl.calls()[0][0], "get-sink-volume");
    assert_eq!(pactl.calls().len(), 2);
}

#[test]
fn a_failed_write_stops_before_the_read() {
    let pactl = FakePactl::new(STEREO_40, "Mute: no\n").failing(
        "set-sink-volume",
        PactlFailure::Exit(String::from("Invalid volume\n")),
    );

    let result =
        LinuxAudioControl::new(&pactl).set_volume(VolumeChange::new(Some(0.2), Some(true)));

    assert_eq!(
        result,
        Err(AudioError::Backend(String::from("Invalid volume")))
    );
    assert_eq!(pactl.calls().len(), 1);
}

#[test]
fn a_failed_mute_write_stops_before_the_read() {
    let pactl = FakePactl::new(STEREO_40, "Mute: no\n").failing(
        "set-sink-mute",
        PactlFailure::Exit(String::from("Invalid mute\n")),
    );

    let result = LinuxAudioControl::new(&pactl).set_volume(VolumeChange::new(None, Some(true)));

    assert_eq!(
        result,
        Err(AudioError::Backend(String::from("Invalid mute")))
    );
    assert_eq!(pactl.calls().len(), 1);
}

#[test]
fn no_sink_or_no_server_is_no_endpoint() {
    for stderr in [
        "Failed to get sink information: No such entity\n",
        "Connection failure: Connection refused\n",
    ] {
        let pactl = FakePactl::new(STEREO_40, "Mute: no\n")
            .failing("get-sink-volume", PactlFailure::Exit(String::from(stderr)));

        let result = LinuxAudioControl::new(&pactl).get_volume();

        assert_eq!(
            result,
            Err(AudioError::NoEndpoint(String::from(stderr.trim())))
        );
    }
}

#[test]
fn a_missing_program_is_a_backend_error() {
    let pactl = FakePactl::new(STEREO_40, "Mute: no\n").failing(
        "get-sink-volume",
        PactlFailure::Spawn(String::from("No such file or directory")),
    );

    let result = LinuxAudioControl::new(&pactl).get_volume();

    assert_eq!(
        result,
        Err(AudioError::Backend(String::from(
            "pactl did not start: No such file or directory"
        )))
    );
}

#[test]
fn a_failed_mute_read_is_reported() {
    let pactl = FakePactl::new(STEREO_40, "Mute: no\n").failing(
        "get-sink-mute",
        PactlFailure::Exit(String::from("Failure\n")),
    );

    let result = LinuxAudioControl::new(&pactl).get_volume();

    assert_eq!(result, Err(AudioError::Backend(String::from("Failure"))));
}

#[test]
fn output_with_no_channel_volume_is_a_backend_error() {
    for volume in [
        "",
        "Volume: front-left: 40% / -23.88 dB\n",
        "Volume: x1 / 40%\n",
    ] {
        let pactl = FakePactl::new(volume, "Mute: no\n");

        let result = LinuxAudioControl::new(&pactl).get_volume();

        let Err(AudioError::Backend(message)) = result else {
            panic!("expected Backend for {volume:?}, got {result:?}");
        };
        assert!(
            message.starts_with("pactl printed no channel volume"),
            "{message}"
        );
    }
}

#[test]
fn output_with_no_mute_state_is_a_backend_error() {
    for mute in ["", "Mute: maybe\n", "Muted: yes\n"] {
        let pactl = FakePactl::new(STEREO_40, mute);

        let result = LinuxAudioControl::new(&pactl).get_volume();

        let Err(AudioError::Backend(message)) = result else {
            panic!("expected Backend for {mute:?}, got {result:?}");
        };
        assert!(
            message.starts_with("pactl printed no mute state"),
            "{message}"
        );
    }
}
