//! The process adapter for [`FrameReader`](crate::FrameReader): runs the real `gst-launch-1.0`.

use std::ffi::OsString;
use std::io::Read;
use std::os::fd::OwnedFd;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use crate::screencast::{FrameError, FrameReader};

/// The program a host runs: `gst-launch-1.0` on `PATH`, from the `GStreamer` tools.
pub const GST_LAUNCH_PROGRAM: &str = "gst-launch-1.0";

/// How long one frame read may take: with `RESTORE_LIMIT` it stays under the brain's 10 s wait.
pub const FRAME_LIMIT: Duration = Duration::from_secs(5);

const PNG_SIGNATURE: &[u8] = b"\x89PNG\r\n\x1a\n";

const POLL: Duration = Duration::from_millis(10);

/// Reads one frame with a `gst-launch-1.0` program, given the stream's descriptor as its input.
pub struct GstLaunch {
    program: OsString,
    limit: Duration,
}

impl GstLaunch {
    /// Creates the reader for `program`, normally [`GST_LAUNCH_PROGRAM`], stopped after `limit`.
    #[must_use]
    pub fn new(program: &str, limit: Duration) -> Self {
        Self {
            program: OsString::from(program),
            limit,
        }
    }
}

/// The arguments of the pipeline that reads one buffer of `node` as a PNG on standard output.
fn pipeline(node: u32) -> [String; 14] {
    [
        "-q",
        "pipewiresrc",
        "fd=0",
        &format!("path={node}"),
        "num-buffers=1",
        "always-copy=true",
        "!",
        "videoconvert",
        "!",
        "video/x-raw,format=RGB",
        "!",
        "pngenc",
        "!",
        "fdsink",
    ]
    .map(String::from)
}

impl FrameReader for GstLaunch {
    fn read(&self, remote: OwnedFd, node: u32) -> Result<Vec<u8>, FrameError> {
        let name = self.program.to_string_lossy();
        let mut child = Command::new(&self.program)
            .args(pipeline(node))
            .env("LC_ALL", "C")
            .stdin(remote)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| FrameError(format!("{name} could not start: {error}")))?;
        let picture = drain(child.stdout.take());
        let reason = drain(child.stderr.take());
        let Some(status) = finish(&mut child, self.limit) else {
            return Err(FrameError(format!(
                "{name} read no frame within {:?} and was stopped",
                self.limit
            )));
        };
        if !status.success() {
            let reason = String::from_utf8_lossy(&collect(reason))
                .trim_end()
                .to_owned();
            return Err(FrameError(format!("{name} failed ({status}): {reason}")));
        }
        let picture = collect(picture);
        if !picture.starts_with(PNG_SIGNATURE) {
            return Err(FrameError(format!("{name} wrote no PNG")));
        }
        Ok(picture)
    }
}

/// Reads a child's pipe to its end on a thread of its own, so neither pipe fills while it runs.
fn drain<P: Read + Send + 'static>(pipe: Option<P>) -> Option<JoinHandle<Vec<u8>>> {
    pipe.map(|mut pipe| {
        thread::spawn(move || {
            let mut bytes = Vec::new();
            let _ = pipe.read_to_end(&mut bytes);
            bytes
        })
    })
}

fn collect(pipe: Option<JoinHandle<Vec<u8>>>) -> Vec<u8> {
    pipe.and_then(|reader| reader.join().ok())
        .unwrap_or_default()
}

/// Waits for `child` to exit, or kills it once `limit` has passed and returns `None`.
fn finish(child: &mut Child, limit: Duration) -> Option<ExitStatus> {
    let deadline = Instant::now() + limit;
    loop {
        if let Some(status) = child.try_wait().ok().flatten() {
            return Some(status);
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            return None;
        }
        thread::sleep(POLL);
    }
}
