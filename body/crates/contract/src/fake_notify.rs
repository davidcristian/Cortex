//! `FakeNotify`, the one stand-in `Notify` backend every body test uses.

use std::sync::{Arc, Mutex, PoisonError};
use std::thread;

use body_core::{Notification, Notify, NotifyError};

use crate::Threads;

#[derive(Clone)]
enum Behaviour {
    Answer(bool),
    Fail(NotifyError),
    Panic,
}

/// A `Notify` that records each notification it answers, or fails or panics on every call.
///
/// A clone shares the record, so a test keeps one clone after the other moves into a server.
#[derive(Clone)]
pub struct FakeNotify {
    behaviour: Behaviour,
    seen: Arc<Mutex<Vec<Notification>>>,
    threads: Threads,
}

impl FakeNotify {
    fn scripted(behaviour: Behaviour) -> Self {
        Self {
            behaviour,
            seen: Arc::default(),
            threads: Threads::default(),
        }
    }

    /// A backend that answers `shown` to every call: `false` is a service that declined.
    #[must_use]
    pub fn answering(shown: bool) -> Self {
        Self::scripted(Behaviour::Answer(shown))
    }

    /// A backend that answers every call with `error`.
    #[must_use]
    pub fn failing(error: NotifyError) -> Self {
        Self::scripted(Behaviour::Fail(error))
    }

    /// A backend that panics inside every call, as a crashed OS call does.
    #[must_use]
    pub fn panicking() -> Self {
        Self::scripted(Behaviour::Panic)
    }

    /// Every notification a call answered, in order.
    #[must_use]
    pub fn seen(&self) -> Vec<Notification> {
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }

    /// A handle on the threads every call ran on, taken before the fake moves into a server.
    #[must_use]
    pub fn threads(&self) -> Threads {
        Arc::clone(&self.threads)
    }
}

impl Notify for FakeNotify {
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError> {
        self.threads
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(thread::current().id());
        match &self.behaviour {
            Behaviour::Answer(shown) => {
                self.seen
                    .lock()
                    .unwrap_or_else(PoisonError::into_inner)
                    .push(notification.clone());
                Ok(*shown)
            }
            Behaviour::Fail(error) => Err(error.clone()),
            Behaviour::Panic => panic!("the notification backend died mid-call"),
        }
    }
}
