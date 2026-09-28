#![cfg(target_os = "linux")]

use os_linux::{PACTL_PROGRAM, PactlCommand, PactlFailure, PactlRunner};

#[test]
fn the_host_program_is_pactl() {
    assert_eq!(PACTL_PROGRAM, "pactl");
}

#[test]
fn a_run_passes_each_argument_and_returns_stdout() {
    let output = PactlCommand::new("echo").run(&["get-sink-volume", "@DEFAULT_SINK@"]);

    assert_eq!(output, Ok(String::from("get-sink-volume @DEFAULT_SINK@\n")));
}

#[test]
fn a_run_is_in_the_c_locale() {
    let output = PactlCommand::new("sh").run(&["-c", "printf %s \"$LC_ALL\""]);

    assert_eq!(output, Ok(String::from("C")));
}

#[test]
fn a_failure_status_returns_stderr() {
    let output = PactlCommand::new("sh").run(&["-c", "echo out; echo refused >&2; exit 3"]);

    assert_eq!(output, Err(PactlFailure::Exit(String::from("refused\n"))));
}

#[test]
fn a_program_that_cannot_start_is_a_spawn_failure() {
    let output = PactlCommand::new("/nonexistent/pactl").run(&["info"]);

    let Err(PactlFailure::Spawn(reason)) = output else {
        panic!("expected a spawn failure, got {output:?}");
    };
    assert!(!reason.is_empty());
}
