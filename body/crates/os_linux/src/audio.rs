//! The Linux [`AudioControl`] backend's logic, over `pactl` and the default sink.

use body_core::{AudioControl, AudioError, VolumeChange, VolumeState};

/// The sink every call reads or changes: the one the sound server plays to by default.
const SINK: &str = "@DEFAULT_SINK@";

/// `PA_VOLUME_NORM`, the raw volume a sound server reads as 100%.
const VOLUME_NORM: f32 = 65536.0;

/// Stderr text, in the C locale, that means no sink or no sound server is reachable.
const NO_ENDPOINT: [&str; 2] = ["No such entity", "Connection failure"];

/// Why one `pactl` run failed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PactlFailure {
    /// The program could not be started, for example because it is not installed.
    Spawn(String),
    /// The program ran and exited with a failure status; the text is its stderr.
    Exit(String),
}

/// Runs `pactl` with arguments and returns its stdout.
pub trait PactlRunner: Send + Sync {
    /// Runs one `pactl` command.
    ///
    /// # Errors
    ///
    /// [`PactlFailure`] when the program cannot start or exits with a failure status.
    fn run(&self, args: &[&str]) -> Result<String, PactlFailure>;
}

/// The Linux volume backend: the default sink of a `PulseAudio` or `pipewire-pulse` server.
pub struct LinuxAudioControl<R> {
    pactl: R,
}

impl<R: PactlRunner> LinuxAudioControl<R> {
    /// Creates the backend over `pactl`.
    #[must_use]
    pub const fn new(pactl: R) -> Self {
        Self { pactl }
    }

    fn run(&self, args: &[&str]) -> Result<String, AudioError> {
        self.pactl.run(args).map_err(classify)
    }
}

impl<R: PactlRunner> AudioControl for LinuxAudioControl<R> {
    fn get_volume(&self) -> Result<VolumeState, AudioError> {
        let level = parse_level(&self.run(&["get-sink-volume", SINK])?)?;
        let muted = parse_mute(&self.run(&["get-sink-mute", SINK])?)?;
        Ok(VolumeState { level, muted })
    }

    fn set_volume(&self, change: VolumeChange) -> Result<VolumeState, AudioError> {
        if let Some(level) = change.level {
            let raw = (level * VOLUME_NORM).round().to_string();
            self.run(&["set-sink-volume", SINK, raw.as_str()])?;
        }
        if let Some(mute) = change.mute {
            self.run(&["set-sink-mute", SINK, if mute { "1" } else { "0" }])?;
        }
        self.get_volume()
    }
}

/// Reads the level from `get-sink-volume`: the mean raw channel volume over [`VOLUME_NORM`],
/// clamped to `[0, 1]` because a server allows a boost past 100%. Each channel reads
/// `<name>: <raw> / <percent>% / <dB> dB`, so a raw value is the number before a lone `/`.
fn parse_level(output: &str) -> Result<f32, AudioError> {
    let tokens: Vec<&str> = output.split_whitespace().collect();
    let raws: Vec<f32> = tokens
        .windows(2)
        .filter(|pair| pair[1] == "/" && pair[0].bytes().all(|byte| byte.is_ascii_digit()))
        .filter_map(|pair| pair[0].parse::<f32>().ok())
        .collect();
    if raws.is_empty() {
        return Err(AudioError::Backend(format!(
            "pactl printed no channel volume: {}",
            output.trim()
        )));
    }
    let (sum, count) = raws.iter().fold((0.0_f32, 0.0_f32), |(sum, count), raw| {
        (sum + raw, count + 1.0)
    });
    Ok((sum / count / VOLUME_NORM).clamp(0.0, 1.0))
}

/// Reads the mute flag from `get-sink-mute`, which prints `Mute: yes` or `Mute: no`.
fn parse_mute(output: &str) -> Result<bool, AudioError> {
    match output.trim().strip_prefix("Mute:").map(str::trim) {
        Some("yes") => Ok(true),
        Some("no") => Ok(false),
        _ => Err(AudioError::Backend(format!(
            "pactl printed no mute state: {}",
            output.trim()
        ))),
    }
}

/// Maps a failed run: no sink or no server is `NoEndpoint`, anything else `Backend`.
fn classify(failure: PactlFailure) -> AudioError {
    match failure {
        PactlFailure::Exit(stderr) if NO_ENDPOINT.iter().any(|text| stderr.contains(text)) => {
            AudioError::NoEndpoint(stderr.trim().to_owned())
        }
        PactlFailure::Exit(stderr) => AudioError::Backend(stderr.trim().to_owned()),
        PactlFailure::Spawn(reason) => {
            AudioError::Backend(format!("pactl did not start: {reason}"))
        }
    }
}
