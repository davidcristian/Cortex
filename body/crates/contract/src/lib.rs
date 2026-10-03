//! The body's shared port check lists, each run by a port's fake and by every adapter CI runs.

/// Pairs each check function with its own name, so a list cannot misname a check.
macro_rules! named {
    ($check_type:ty; $($check:ident),+ $(,)?) => {
        [$((stringify!($check), $check as $check_type)),+]
    };
}

pub mod audio;
mod fake_audio;

pub use fake_audio::{FakeAudio, Threads};
