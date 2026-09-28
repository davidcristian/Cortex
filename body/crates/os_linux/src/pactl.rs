//! The process adapter for [`PactlRunner`](crate::PactlRunner): runs the real `pactl`.

use std::ffi::OsString;
use std::process::Command;

use crate::audio::{PactlFailure, PactlRunner};

/// The program a host runs: `pactl` on `PATH`, from the `PulseAudio` utilities.
pub const PACTL_PROGRAM: &str = "pactl";

/// Runs a `pactl` program as a child process, in the C locale so its output reads the same.
pub struct PactlCommand {
    program: OsString,
}

impl PactlCommand {
    /// Creates the runner for `program`, normally [`PACTL_PROGRAM`].
    #[must_use]
    pub fn new(program: &str) -> Self {
        Self {
            program: OsString::from(program),
        }
    }
}

impl PactlRunner for PactlCommand {
    fn run(&self, args: &[&str]) -> Result<String, PactlFailure> {
        let output = Command::new(&self.program)
            .args(args)
            .env("LC_ALL", "C")
            .output()
            .map_err(|error| PactlFailure::Spawn(error.to_string()))?;
        if output.status.success() {
            Ok(String::from_utf8_lossy(&output.stdout).into_owned())
        } else {
            Err(PactlFailure::Exit(
                String::from_utf8_lossy(&output.stderr).into_owned(),
            ))
        }
    }
}
