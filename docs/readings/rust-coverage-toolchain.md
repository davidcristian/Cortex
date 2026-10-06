# Readings: the Rust coverage toolchain

What the nightly coverage step does under the toolchains it has run on. Cited by
[ADR-0002](../adr/ADR-0002-toolchain-checks.md#rust-coverage-on-an-unpinned-nightly), decisions 10
and 12, and by [body-os-linux.md](../modules/body-os-linux.md).

## Build scripts enter the report on newer nightlies

**2026-08-11.** Holding cargo-llvm-cov at 0.8.7 and changing only the compiler, rustc
1.98.0-nightly (2026-07-01) leaves Cargo build scripts out of the report and rustc 1.99.0-nightly
(2026-08-10) instruments them. `crates/rpc/build.rs` entered at 41.18% of its lines covered, 17
instrumented lines of which 10 no test can reach, and took the workspace totals to 99.40% of
lines, 99.55% of regions and 99.06% of branches. With `/build[.]rs$` added to the ignore pattern,
1.99 reported the same file set and the same totals as 1.98, every metric fully covered.

Method: the coverage line of `just check-body`, run as `cargo +<toolchain> llvm-cov` under each
toolchain, reading the totals of the JSON export.

## The threshold flags are silent when the report goes to a file

**2026-08-17.** With cargo-llvm-cov 0.8.7, the coverage command with an unreachable
`--fail-under-lines 101` added exits 1 after 346 lines of output, none of which names a metric, a
percentage or a threshold; the last is `Finished report saved to coverage.json`. With the report
left on stdout the per-file table prints, and still no line names the threshold.

Method: the coverage line of `just check-body` with the flag appended, once with
`--output-path coverage.json` and once without it.

## A thread still in a loop at exit shifts the loop's counts

**2026-10-06.** llvm-cov derives most region counts by subtracting one counter from another, so a
thread that has entered a loop and not left it when the test binary exits is counted on a path it
never took. The `os_linux` hotkey tests left each listener thread waiting in `next_press` or
`next_activation` after their last assertion. When the binary exited before that thread read the
closed bus, the skip of a malformed signal (`accel_dbus.rs` line 131, `shortcuts_dbus.rs` line
184) read 0 although the tests send one, and the file fell short of full coverage. Of 32 runs
before the fix, 20 on an idle machine and 12 beside busy loops at twice its core count, 4 missed
the `accel_dbus.rs` line (1 idle, 3 loaded) and 1 missed the `shortcuts_dbus.rs` line (loaded),
and every miss came with one fewer read error than the tests cause. Keeping the bus open past the
exit missed the line in 4 runs of 4. With each test closing the bus and waiting for the listener
to drop its callback, 27 runs, 12 idle and 15 loaded, read both lines covered.

Method: `cargo +nightly llvm-cov --branch -p os-linux --all-targets --json` with the check's
shuffle seed, reading the two files' segments from each run's export.
