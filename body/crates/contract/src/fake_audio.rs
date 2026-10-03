//! `FakeAudio`, the one stand-in `AudioControl` backend every body test uses.

use std::sync::{Arc, Mutex, PoisonError};
use std::thread::{self, ThreadId};

use body_core::{AudioControl, AudioError, VolumeChange, VolumeState};

/// The threads a fake was called on, still readable after the fake has moved into a server.
pub type Threads = Arc<Mutex<Vec<ThreadId>>>;

enum Behaviour {
    Answer,
    Fail(AudioError),
    Panic,
}

/// An `AudioControl` that holds its state in memory, or fails or panics on every call.
pub struct FakeAudio {
    state: Mutex<VolumeState>,
    behaviour: Behaviour,
    threads: Threads,
}

impl FakeAudio {
    fn scripted(behaviour: Behaviour, level: f32, muted: bool) -> Self {
        Self {
            state: Mutex::new(VolumeState { level, muted }),
            behaviour,
            threads: Threads::default(),
        }
    }

    /// A backend whose output starts at `level` and `muted`.
    #[must_use]
    pub fn new(level: f32, muted: bool) -> Self {
        Self::scripted(Behaviour::Answer, level, muted)
    }

    /// A backend that answers every call with `error`.
    #[must_use]
    pub fn failing(error: AudioError) -> Self {
        Self::scripted(Behaviour::Fail(error), 0.5, false)
    }

    /// A backend that panics inside every call, as a crashed OS call does.
    #[must_use]
    pub fn panicking() -> Self {
        Self::scripted(Behaviour::Panic, 0.5, false)
    }

    /// A handle on the threads every call ran on, taken before the fake moves into a server.
    #[must_use]
    pub fn threads(&self) -> Threads {
        Arc::clone(&self.threads)
    }

    fn enter(&self) -> Result<(), AudioError> {
        self.threads
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(thread::current().id());
        match &self.behaviour {
            Behaviour::Answer => Ok(()),
            Behaviour::Fail(error) => Err(error.clone()),
            Behaviour::Panic => panic!("the audio backend died mid-call"),
        }
    }
}

impl AudioControl for FakeAudio {
    fn get_volume(&self) -> Result<VolumeState, AudioError> {
        self.enter()?;
        Ok(*self.state.lock().unwrap_or_else(PoisonError::into_inner))
    }

    fn set_volume(&self, change: VolumeChange) -> Result<VolumeState, AudioError> {
        self.enter()?;
        let mut state = self.state.lock().unwrap_or_else(PoisonError::into_inner);
        if let Some(level) = change.level {
            state.level = level;
        }
        if let Some(mute) = change.mute {
            state.muted = mute;
        }
        Ok(*state)
    }
}
