//! The body's shared port check lists, each run by a port's fake and by every adapter CI runs.

/// Pairs each check function with its own name, so a list cannot misname a check.
macro_rules! named {
    ($check_type:ty; $($check:ident),+ $(,)?) => {
        [$((stringify!($check), $check as $check_type)),+]
    };
}

pub mod audio;
pub mod clipboard;
mod fake_audio;
mod fake_clipboard;
mod fake_hotkey;
mod fake_notify;
mod fake_screen;
mod fake_transport;
pub mod hotkey;
pub mod notify;
pub mod screen;
pub mod transport;

pub use fake_audio::{FakeAudio, Threads};
pub use fake_clipboard::FakeClipboard;
pub use fake_hotkey::FakeHotkey;
pub use fake_notify::FakeNotify;
pub use fake_screen::{FakeScreen, Requests};
pub use fake_transport::FakeTransport;
