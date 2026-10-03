//! `FakeScreen`, the one stand-in `ScreenCapture` backend every body test uses.

use std::sync::{Arc, Mutex, PoisonError};
use std::thread;

use body_core::{
    CaptureError, CaptureRequest, CaptureTarget, CapturedFrame, RawFrame, ScreenCapture, TargetRect,
};

use crate::Threads;

/// The requests a fake was handed, still readable after the fake has moved into a server.
pub type Requests = Arc<Mutex<Vec<CaptureRequest>>>;

enum Answer {
    Display(RawFrame),
    Window(RawFrame, TargetRect),
    Failure(CaptureError),
    Raw(u32, u32, Vec<u8>),
}

/// A `ScreenCapture` that answers a scripted desktop or failure and records each request.
pub struct FakeScreen {
    answer: Answer,
    requests: Requests,
    threads: Threads,
}

impl FakeScreen {
    fn with(answer: Answer) -> Self {
        Self {
            answer,
            requests: Requests::default(),
            threads: Threads::default(),
        }
    }

    /// A display showing `frame` with no window to point at, so a focus request finds none.
    #[must_use]
    pub fn answering(frame: RawFrame) -> Self {
        Self::with(Answer::Display(frame))
    }

    /// A display showing `frame`, where a focus request resolves to `window`.
    #[must_use]
    pub fn showing(frame: RawFrame, window: TargetRect) -> Self {
        Self::with(Answer::Window(frame, window))
    }

    /// A backend that answers every call with `error`.
    #[must_use]
    pub fn failing(error: CaptureError) -> Self {
        Self::with(Answer::Failure(error))
    }

    /// A backend that reports a size its buffer does not match, as one that miscounted a stride.
    #[must_use]
    pub fn miscounting(width: u32, height: u32, pixels: Vec<u8>) -> Self {
        Self::with(Answer::Raw(width, height, pixels))
    }

    /// A handle on every request the fake was handed, taken before it moves into a server.
    #[must_use]
    pub fn requests(&self) -> Requests {
        Arc::clone(&self.requests)
    }

    /// A handle on the threads every call ran on, taken before the fake moves into a server.
    #[must_use]
    pub fn threads(&self) -> Threads {
        Arc::clone(&self.threads)
    }
}

impl ScreenCapture for FakeScreen {
    fn capture(&self, request: &CaptureRequest) -> Result<CapturedFrame, CaptureError> {
        self.threads
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(thread::current().id());
        self.requests
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(*request);
        let focus = request.target() == CaptureTarget::Focus;
        match &self.answer {
            Answer::Display(_) if focus => Err(CaptureError::NoTarget(String::from(
                "no window on the desktop to point at",
            ))),
            Answer::Window(frame, window) if focus => {
                Ok(CapturedFrame::window(frame.clone(), *window))
            }
            Answer::Display(frame) | Answer::Window(frame, _) => {
                Ok(CapturedFrame::display(frame.clone()))
            }
            Answer::Failure(error) => Err(error.clone()),
            Answer::Raw(width, height, pixels) => {
                RawFrame::new(*width, *height, pixels.clone()).map(CapturedFrame::display)
            }
        }
    }
}
