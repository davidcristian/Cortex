#![cfg(target_os = "linux")]

use std::io::Write;
use std::os::fd::OwnedFd;
use std::time::{Duration, Instant};

use os_linux::{FRAME_LIMIT, FrameError, FrameReader, GST_LAUNCH_PROGRAM, GstLaunch};

const FAKE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/gst/fake-gst-launch.sh");

const PNG_SIGNATURE: &[u8] = b"\x89PNG\r\n\x1a\n";

/// The value of a setup step that cannot fail in a working test environment.
fn ok<T, E: std::fmt::Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("a setup step failed: {error:?}"))
}

/// A pipe whose reading end holds `bytes`, in place of the `PipeWire` descriptor.
fn remote(bytes: &[u8]) -> OwnedFd {
    let (reader, mut writer) = ok(std::io::pipe());
    ok(writer.write_all(bytes));
    OwnedFd::from(reader)
}

fn fake() -> GstLaunch {
    GstLaunch::new(FAKE, FRAME_LIMIT)
}

fn failure(result: Result<Vec<u8>, FrameError>) -> String {
    match result {
        Err(FrameError(message)) => message,
        Ok(bytes) => panic!("expected a failed read, got {} bytes", bytes.len()),
    }
}

#[test]
fn the_host_program_is_gst_launch_and_a_read_may_take_five_seconds() {
    assert_eq!(GST_LAUNCH_PROGRAM, "gst-launch-1.0");
    assert_eq!(FRAME_LIMIT, Duration::from_secs(5));
}

#[test]
fn a_read_returns_the_whole_standard_output_of_the_descriptor_given_as_standard_input() {
    let mut png = PNG_SIGNATURE.to_vec();
    png.extend((0..20_000u32).map(|index| index.to_le_bytes()[0]));

    let output = fake().read(remote(&png), 1);

    assert_eq!(output, Ok(png));
}

#[test]
fn a_read_runs_the_pipeline_for_the_node_in_the_c_locale() {
    let output = ok(fake().read(remote(b""), 41));

    let mut expected = PNG_SIGNATURE.to_vec();
    expected.extend_from_slice(
        b"C\n-q\npipewiresrc\nfd=0\npath=41\nnum-buffers=1\nalways-copy=true\n!\nvideoconvert\n!\n\
          video/x-raw,format=RGB\n!\npngenc\n!\nfdsink\n",
    );
    assert_eq!(output, expected);
}

#[test]
fn a_failure_status_returns_the_status_and_stderr() {
    let message = failure(fake().read(remote(b""), 2));

    assert_eq!(
        message,
        format!("{FAKE} failed (exit status: 3): pipewiresrc: no stream")
    );
}

#[test]
fn an_output_that_is_not_a_png_is_a_failure() {
    let message = failure(fake().read(remote(b""), 3));

    assert_eq!(message, format!("{FAKE} wrote no PNG"));
}

#[test]
fn a_program_still_running_at_its_limit_is_stopped() {
    let limit = Duration::from_millis(300);
    let began = Instant::now();

    let message = failure(GstLaunch::new(FAKE, limit).read(remote(b""), 4));

    assert_eq!(
        message,
        format!("{FAKE} read no frame within 300ms and was stopped")
    );
    assert!(began.elapsed() < Duration::from_secs(20));
}

#[test]
fn a_program_that_cannot_start_is_a_failure_naming_it() {
    let message =
        failure(GstLaunch::new("/nonexistent/gst-launch-1.0", FRAME_LIMIT).read(remote(b""), 1));

    assert!(
        message.starts_with("/nonexistent/gst-launch-1.0 could not start: "),
        "{message}"
    );
}
