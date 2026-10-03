use body_contract::FakeAudio;
use body_contract::audio::{AudioSubject, run};
use body_core::{AudioControl, AudioError, VolumeState};

struct Fake;

impl AudioSubject for Fake {
    fn holding(&self, state: VolumeState) -> Box<dyn AudioControl> {
        Box::new(FakeAudio::new(state.level, state.muted))
    }

    fn without_endpoint(&self) -> Box<dyn AudioControl> {
        Box::new(FakeAudio::failing(AudioError::NoEndpoint(String::from(
            "no device",
        ))))
    }

    fn broken(&self) -> Box<dyn AudioControl> {
        Box::new(FakeAudio::failing(AudioError::Backend(String::from(
            "COM 0x1",
        ))))
    }
}

#[test]
fn the_fake_meets_every_audio_check() {
    run(&Fake);
}
