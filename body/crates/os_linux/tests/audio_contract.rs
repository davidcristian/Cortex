#![cfg(target_os = "linux")]

use std::sync::{Mutex, PoisonError};

use body_contract::audio::{AudioSubject, run};
use body_core::{AudioControl, VolumeState};
use os_linux::{LinuxAudioControl, PactlFailure, PactlRunner};

const VOLUME_NORM: f32 = 65536.0;

const QUIET: VolumeState = VolumeState {
    level: 0.25,
    muted: false,
};

/// The default sink: its raw volume, where [`VOLUME_NORM`] is 100%, and its mute flag.
struct Sink {
    raw: f32,
    muted: bool,
}

/// A stand-in sound server behind `pactl`: one default sink that the set commands change and the
/// get commands print, or one failure for every command.
struct SoundServer {
    sink: Mutex<Sink>,
    failure: Option<PactlFailure>,
}

impl SoundServer {
    fn backend(state: VolumeState, failure: Option<PactlFailure>) -> Box<dyn AudioControl> {
        Box::new(LinuxAudioControl::new(Self {
            sink: Mutex::new(Sink {
                raw: state.level * VOLUME_NORM,
                muted: state.muted,
            }),
            failure,
        }))
    }
}

impl PactlRunner for SoundServer {
    fn run(&self, args: &[&str]) -> Result<String, PactlFailure> {
        if let Some(failure) = &self.failure {
            return Err(failure.clone());
        }
        let mut sink = self.sink.lock().unwrap_or_else(PoisonError::into_inner);
        let percent = sink.raw * 100.0 / VOLUME_NORM;
        match args {
            ["get-sink-volume", _] => Ok(format!(
                "Volume: front-left: {raw:.0} / {percent:.0}% / 0.00 dB,   front-right: {raw:.0} / {percent:.0}% / 0.00 dB\n        balance 0.00\n",
                raw = sink.raw,
            )),
            ["get-sink-mute", _] => {
                Ok(format!("Mute: {}\n", if sink.muted { "yes" } else { "no" }))
            }
            ["set-sink-volume", _, raw] => {
                sink.raw = raw.parse().unwrap_or(f32::NAN);
                Ok(String::new())
            }
            _ => {
                sink.muted = args.last() == Some(&"1");
                Ok(String::new())
            }
        }
    }
}

struct Linux;

impl AudioSubject for Linux {
    fn holding(&self, state: VolumeState) -> Box<dyn AudioControl> {
        SoundServer::backend(state, None)
    }

    fn without_endpoint(&self) -> Box<dyn AudioControl> {
        let refused = PactlFailure::Exit(String::from("Connection failure: Connection refused\n"));
        SoundServer::backend(QUIET, Some(refused))
    }

    fn broken(&self) -> Box<dyn AudioControl> {
        let missing = PactlFailure::Spawn(String::from("No such file or directory"));
        SoundServer::backend(QUIET, Some(missing))
    }
}

#[test]
fn the_linux_backend_meets_every_audio_check() {
    run(&Linux);
}
