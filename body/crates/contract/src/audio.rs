//! The `AudioControl` check list: what every volume backend owes, read through the port alone.

use std::mem::{Discriminant, discriminant};

use body_core::{AudioControl, AudioError, VolumeChange, VolumeState};

/// The steps a sound server divides the level into from silent to full, `PA_VOLUME_NORM`.
const LEVEL_STEPS: f32 = 65536.0;

/// Builds the implementation under test in each condition a check needs.
pub trait AudioSubject {
    /// An implementation whose output reads `state` until a change is applied.
    fn holding(&self, state: VolumeState) -> Box<dyn AudioControl>;

    /// An implementation with no output endpoint to read or change.
    fn without_endpoint(&self) -> Box<dyn AudioControl>;

    /// An implementation whose backend fails every call for any other reason.
    fn broken(&self) -> Box<dyn AudioControl>;
}

/// One check and its name, run against a subject.
pub type AudioCheck = (&'static str, fn(&dyn AudioSubject));

/// Every check a volume backend owes, in the order a driver runs them.
pub const AUDIO_CHECKS: [AudioCheck; 8] = named![fn(&dyn AudioSubject);
    a_read_reports_the_state_held,
    a_change_reports_the_state_it_made,
    the_next_read_reports_the_change,
    a_level_alone_keeps_the_mute_flag,
    a_mute_flag_alone_keeps_the_level,
    an_empty_change_changes_nothing,
    no_endpoint_fails_both_calls,
    a_broken_backend_fails_both_calls,
];

/// Runs every check against `subject`, naming each on stderr first so a failure shows which.
pub fn run(subject: &dyn AudioSubject) {
    for (name, check) in AUDIO_CHECKS {
        eprintln!("audio check: {name}");
        check(subject);
    }
}

const fn state(level: f32, muted: bool) -> VolumeState {
    VolumeState { level, muted }
}

/// The state at the resolution a sound server keeps, so a backend that rounds the level agrees.
fn heard(result: Result<VolumeState, AudioError>) -> Result<VolumeState, AudioError> {
    result.map(|found| {
        state(
            (found.level * LEVEL_STEPS).round() / LEVEL_STEPS,
            found.muted,
        )
    })
}

/// Which error a call failed with, without its text, which each backend writes its own way.
fn kind(result: Result<VolumeState, AudioError>) -> Result<VolumeState, Discriminant<AudioError>> {
    result.map_err(|error| discriminant(&error))
}

fn a_read_reports_the_state_held(subject: &dyn AudioSubject) {
    for held in [state(0.4, true), state(0.75, false)] {
        let audio = subject.holding(held);
        assert_eq!(heard(audio.get_volume()), heard(Ok(held)));
    }
}

fn a_change_reports_the_state_it_made(subject: &dyn AudioSubject) {
    let audio = subject.holding(state(0.25, false));
    let made = audio.set_volume(VolumeChange::new(Some(0.75), Some(true)));
    assert_eq!(heard(made), heard(Ok(state(0.75, true))));
}

fn the_next_read_reports_the_change(subject: &dyn AudioSubject) {
    let audio = subject.holding(state(0.25, true));
    let made = audio.set_volume(VolumeChange::new(Some(0.6), Some(false)));
    assert_eq!(heard(audio.get_volume()), heard(made));
    assert_eq!(heard(audio.get_volume()), heard(Ok(state(0.6, false))));
}

fn a_level_alone_keeps_the_mute_flag(subject: &dyn AudioSubject) {
    for muted in [true, false] {
        let audio = subject.holding(state(0.5, muted));
        let made = audio.set_volume(VolumeChange::new(Some(0.25), None));
        assert_eq!(heard(made), heard(Ok(state(0.25, muted))));
    }
}

fn a_mute_flag_alone_keeps_the_level(subject: &dyn AudioSubject) {
    let audio = subject.holding(state(0.5, false));
    let muted = audio.set_volume(VolumeChange::new(None, Some(true)));
    assert_eq!(heard(muted), heard(Ok(state(0.5, true))));
    let unmuted = audio.set_volume(VolumeChange::new(None, Some(false)));
    assert_eq!(heard(unmuted), heard(Ok(state(0.5, false))));
}

fn an_empty_change_changes_nothing(subject: &dyn AudioSubject) {
    let audio = subject.holding(state(0.4, true));
    let made = audio.set_volume(VolumeChange::new(None, None));
    assert_eq!(heard(made), heard(Ok(state(0.4, true))));
}

fn no_endpoint_fails_both_calls(subject: &dyn AudioSubject) {
    let audio = subject.without_endpoint();
    let refused = kind(Err(AudioError::NoEndpoint(String::new())));
    assert_eq!(kind(audio.get_volume()), refused);
    let change = VolumeChange::new(Some(0.5), Some(true));
    assert_eq!(kind(audio.set_volume(change)), refused);
}

fn a_broken_backend_fails_both_calls(subject: &dyn AudioSubject) {
    let audio = subject.broken();
    let failed = kind(Err(AudioError::Backend(String::new())));
    assert_eq!(kind(audio.get_volume()), failed);
    let change = VolumeChange::new(Some(0.5), Some(true));
    assert_eq!(kind(audio.set_volume(change)), failed);
}
