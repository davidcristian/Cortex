# The kglobalaccel press loop is covered only sometimes

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-06

`just check` failed once on 2026-10-06 with nothing changed under `body/`: `rustcoverage.py`
read 99.98% of lines, 99.99% of regions and 99.69% of branches, and the only file short of full
was `body/crates/os_linux/src/accel_dbus.rs`, one line and one branch. Three runs of `cargo +nightly
llvm-cov --branch -p os-linux --all-targets` with the suite's fixed shuffle seed then read the
file whole twice and missed line 131 once: the `continue` taken when a press signal's body does
not read as `(String, String, i64)`. The tests passed in all three.

Only `each_press_and_release_is_read_in_order_and_other_or_forged_signals_are_skipped` in
`body/crates/os_linux/tests/accel_dbus.rs` sends such a body, the `("wrong",)` signal it emits
first, right after the fake bus is built. In the run that missed the line, no press failed to
deserialize, so that signal never reached the check, and the assertions, which read only the two
signals sent last, did not notice. Which race drops it is not settled: the reader's subscription,
the fake server's first emit, and the first `GetNameOwner` answer are the candidates.

**Do.** Find what drops the first signal, and send the malformed press only once the reader is
known to receive: for instance after a good press the test has already read. Run the coverage
command above enough times to show the line is covered every time.

## History

- 2026-10-06: filed after it failed a pre-commit `just check` on a docs-only change; the retry
  passed.
