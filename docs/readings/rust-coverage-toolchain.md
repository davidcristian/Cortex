# Readings: the Rust coverage toolchain

What the nightly coverage step does under the toolchains it has run on. Cited by
[ADR-0002](../adr/ADR-0002-toolchain-checks.md#rust-coverage-on-an-unpinned-nightly), decisions 10
and 12.

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
