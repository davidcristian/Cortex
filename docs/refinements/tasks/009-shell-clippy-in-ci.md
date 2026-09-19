# cargo clippy for the Tauri shell in CI

**Status:** done 2026-08-17
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Left over from [R-008](008-fmt-clippy-ungated-rust-trees.md): the shell's clippy ran nowhere in
CI, so a finding there could accumulate unreported, as two `collapsible_if` in `confirm.rs` did
before 2026-07-16. Unlike the shell's fmt (parse only) and `os_windows`'s clippy (one target, no
link), shell clippy needs the shell to compile, which means the Linux GTK/webkit/dbus dev packages
and a cold Tauri build with webkit.

Deferred four times, each on the same arithmetic. The CI rust job installs no system library at
all: rust nightly and stable (rustfmt, clippy, the `x86_64-pc-windows-msvc` target),
`cargo-llvm-cov`, `just`, `uv` and `rust-cache`. The overlay job is node only. So shell clippy
would add a new class of CI provisioning, and on the assumption that it had to be a step inside
`check-body`, which every `body/` change runs, that cost fell on every `body/` change to catch the
occasional style lint on 881 lines of thin, host-checked wiring.

Two measurements were taken while it waited, rather than read out of the tree:

- 2026-08-10: `cargo clippy --all-targets -- -D warnings` in `body/app/src-tauri` exits 0 over the
  shell as it stood, 978 lines in 12 files, so it had grown by a file and 97 lines and accumulated
  no finding. A `useless_format` planted in `src/tray.rs` makes the same command exit 101. This
  also corrected the route for this host: `/usr/bin/pkg-config` is real here and no shim is
  needed. What is missing are the `.pc` files, fetched without sudo by `apt-get download` plus
  `dpkg-deb -x` into a scratch prefix outside the repo with `PKG_CONFIG_PATH` naming its two
  `pkgconfig` directories: 47 `-dev` packages, 6.0 MB fetched and 48 MB unpacked, found in six
  rounds because each round's failure names only the next missing `Requires`. None of those
  libraries is ever loaded, since clippy does not link. The Rust half is cheap: the whole Tauri
  graph type-checks in 22.6 s wall on a partly populated target directory.

Closed 2026-08-17 by splitting rather than by paying. The premise was the defect: shell clippy is
now its own path-filtered CI job (`check-shell`, on a fourth classifier output `shell=`), so the
webkit provisioning happens on a `body/app/src-tauri/` edit and on nothing else. The earlier
numbers were too high. The real `-dev` closure is 103 packages, 39.6 MB, about 4 s to fetch from
five roots, the 630 being an unfiltered `apt-cache depends --recurse` walk, and the whole Tauri
graph clippies from an empty target directory in 30.9 s wall. That is about a minute, once, on the
change that could have broken it.

`just check` deliberately does not run `check-shell`, because it is the only check needing system
libraries and requiring them would make the single command unrunnable on a clean checkout. That
divergence, the first in this repo, is argued at the origin. A planted `useless_format` makes
`just check-shell` exit 101, and routing the shell subtree back to plain rust fails the classifier
suite. What is left over is the verification asymmetry the split creates, filed as
[R-300](300-shell-job-never-ran-on-a-runner.md).

## History

- 2026-07-16: Recorded as the residue of the fmt and clippy work and listed as actionable.
- 2026-07-16: Deferred the same day, once reading what the rust CI job installs (no system library
  at all) settled it against wiring: a 630-package Tauri webkit-dev apt closure, uncacheable per
  job, plus a cold compile of roughly 150 Tauri crates, for the occasional lint on 881 lines. It
  was confirmed clippy-clean live over a permissive `pkg-config` shim, with a planted
  `useless_format` showing the check was real.
- 2026-08-09: A review settled the CI half of the trigger by reading `.github/workflows/ci.yml`,
  which installs no system library and states the shell is never built there.
- 2026-08-10: The accumulation half was run rather than read. The shell's own
  `cargo clippy --all-targets` with warnings denied exits 0 over 978 lines in 12 files, where this
  entry recorded 881 in 11, and a planted `useless_format` makes the same command exit 101. The
  run also corrected the route for this host to 47 `-dev` packages of `.pc` metadata unpacked
  without sudo.
- 2026-08-17: Closed by splitting: a separate path-filtered CI job running a new
  `just check-shell`, so only a shell edit installs webkit. The earlier numbers were high (103
  packages and 39.6 MB, not a 630-package closure; 30.9 s for a cold clippy of the whole Tauri
  graph). `just check` deliberately does not run the new recipe. Both levels were shown able to
  fail. Residue filed as [R-300](300-shell-job-never-ran-on-a-runner.md).
