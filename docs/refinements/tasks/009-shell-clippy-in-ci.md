# cargo clippy for the Tauri shell in CI

**Status:** landed 2026-08-17
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

The shell's clippy still runs nowhere in CI. Unlike the shell's fmt (parse only) and
`os_windows`'s clippy (a target add, no link), shell clippy needs the shell to actually compile:
the Linux GTK/webkit/dbus dev packages (`apt-get install` on a runner; on this sudo-less WSL host
an unpacked `libdbus-1-dev` in a userspace prefix plus a `pkg-config` shim) and a cold Tauri build
with webkit. That build cost is why it is not folded into `check-body`, which every `body/` change
runs. It is the one half of this entry that still lets a shell clippy finding accumulate
unseen (two `collapsible_if` did, in `confirm.rs`, before 2026-07-16). The toolchain-linked
full build of either tree stays host-side, as ADR-0011 already notes.

**Reclassified 2026-07-16 to fix-when-it-bites, read against what CI installs and measured.**
The residual was listed as actionable, but reading what the CI rust job actually provisions
settled it against wiring. That job (`.github/workflows/ci.yml`) installs no system library
at all: rust nightly plus stable (rustfmt, clippy, the `x86_64-pc-windows-msvc` target),
`cargo-llvm-cov`, `just`, `uv`, and `rust-cache`, nothing more; the overlay job is node only
(its own comment says "npm + jsdom only"). So shell clippy is not a marginal add onto a
desktop toolchain CI already carries; it introduces a whole new class of CI provisioning. The
Tauri Linux dev stack (`libwebkit2gtk-4.1-dev` and its transitive deps) has a 630-package
recursive apt closure (measured with `apt-cache depends --recurse`), an uncacheable
`apt-get install` that re-runs every job (`rust-cache` caches compiled crates, not apt
packages), on top of a cold compile of the roughly 150-crate Tauri Rust graph (`wry`,
`webkit2gtk-sys`, the gtk-rs `-sys` crates, `tauri`). That whole cost lands on `check-body`,
which every `body/` change runs, to catch the occasional style lint on 881 lines (11 files) of
host-validated thin wiring. Disproportionate at personal, local-first scale, and the user
already catches shell clippy on the validation host (that is where the two `collapsible_if`
were fixed). It moves to fix-when-it-bites with its trigger: **CI gaining the Tauri desktop
stack for another reason** (a future CI-side Tauri build or smoke job), which drops the
marginal cost of shell clippy to near zero and lets it ride along; failing that, shell findings
accumulating faster than the user's local checks catch them, or the shell outgrowing the thin
wiring the coverage-creep guard already watches. This is a sharpened deferral, still open, so
the count is unchanged (the same bookkeeping the seam-transport and session-history sharpens
used), not a decline; the check itself is real, it is only too costly here.
**Confirmed clippy-clean now.** This host has neither `pkg-config` nor the webkit-dev stack
(only the `libgtk-3` runtime, no `-dev`, and no sudo), so a permissive `pkg-config` shim stood
in for it: the `-sys` build scripts consume only link flags, which clippy discards because it
never links, so a shim that answers every query and version check lets the whole Tauri graph
type-check. Under it `cargo clippy --all-targets -- -D warnings` on the shell exits 0, and a
planted `useless_format` makes that exact command exit 101, so the declined check is real
rather than vacuously green. The heavier note is that assembling even a shim for a one-off
local check mirrors the CI cost: the stack this host lacks is exactly the stack a CI runner
would have to install on every shell change.

**Run rather than read on 2026-08-10: the second trigger was measured and did not fire.** The
2026-08-09 sweep settled the first trigger by reading `.github/workflows/ci.yml`, which is the
right instrument for a trigger about what CI installs, and it left the second one, shell
findings accumulating faster than the maintainer's local checks catch them, resting on a read as
well. Only running the check settles that one, so it was run.
`cargo clippy --all-targets -- -D warnings` in `body/app/src-tauri` exits 0 over the shell as it
stands, which is **978 lines in 12 files** rather than the 881 in 11 this entry records, so the
wiring grew by a file and 97 lines since the last reading and accumulated no finding, which is
the accumulation half of the trigger answered. Proven able to fail before being
trusted, the same way the reading above did it: a `useless_format` planted in `src/tray.rs`
makes that exact command exit 101, naming the lint on the lib and the lib-test unit, and it
exits 0 again with the file restored. This lints the shell; it does not run it, which still
wants a real Win32 desktop session ([host/](../../host/index.md)).

**The route this entry records for this host is out of date, and the corrected one is the same
cost argument with a number on it.** It says the host has neither `pkg-config` nor the webkit
dev stack, so a permissive shim stood in. `/usr/bin/pkg-config` is real here now and no shim was
needed or written; what is missing is the `.pc` files, and the sudo-less way to get them is
`apt-get download` plus `dpkg-deb -x` into a scratch prefix outside the repo with
`PKG_CONFIG_PATH` naming its two `pkgconfig` directories. That took **47 `-dev` packages** (6.0
MB fetched, 48 MB unpacked), found in six rounds because each round's `pkg-config` failure names
only the next missing `Requires`: `dbus-1`, then gtk, pango, atk, gdk-pixbuf, harfbuzz,
webkit2gtk, javascriptcoregtk and libsoup, then the X, wayland, GL and image-codec packages
their `Requires.private` lines pull in, down to `graphite2`, `libthai`, `datrie`, `libsharpyuv`
and `sysprof-capture-4`. Not one of those libraries is ever loaded, clippy not linking; it is 47
packages of metadata to get build scripts past a probe. The Rust half is the cheap half, the
whole Tauri graph type-checking in 22.6 s wall here on a target directory that was already
partly populated, so what CI would be paying for is the provisioning rather than the compile,
and `rust-cache` caches none of it. That is this entry's decline measured rather than restated.
Both triggers stand and the entry stays open.

**Landed 2026-08-17, and neither trigger is what settled it.** Every reading above priced this
as a step inside `check-body`, which every `body/` change runs, and on that premise the decline
held four times. The premise was the defect. Shell clippy is now its own path-filtered CI job
(`check-shell`, gated on a fourth classifier output `shell=`), so the webkit provisioning lands
on a `body/app/src-tauri/` edit and on nothing else, and the arithmetic the decline rested on
stops applying. The numbers this entry carried were also too big: the real `-dev` closure is
**103 packages, 39.6 MB, about 4 s to fetch** from five roots, the 630 being an unfiltered
`apt-cache depends --recurse` walk, and the whole Tauri graph clippies from an **empty target
directory in 30.9 s wall**. About a minute, once, on the change that could have broken it.
`just check` deliberately does NOT run `check-shell`, since it is the only check needing system
libraries and requiring them would make the single gate unrunnable on a clean checkout; that
divergence, the first in this repo, is argued at the origin. A planted `useless_format` makes
`just check-shell` exit 101, and routing the shell subtree back to plain rust fails the
classifier suite, so neither half is trusted green untested. What did not land with it is the
verification asymmetry the split creates, filed as
[300](300-shell-job-never-ran-on-a-runner.md).

## Trail

- 2026-07-16: Recorded as the residual of the fmt-and-clippy landing and listed as actionable, the
  shell's clippy being the one half that still lets a finding accumulate unseen.
- 2026-07-16: Reclassified to fix-when-it-bites the same day, with the count unchanged, once
  reading what the rust CI job provisions (no system library at all) settled it against wiring: a
  630-package Tauri webkit-dev apt closure, uncacheable per job, plus a cold roughly 150-crate
  Tauri graph compile, for the occasional lint on 881 lines of host-validated thin wiring. It was
  confirmed clippy-clean live over a permissive `pkg-config` shim, with a planted `useless_format`
  proving the declined check real. The index records the move as emptying its actionable-now list,
  this having been the last item that list then held, which read `None` from that day until
  2026-07-19.
- 2026-08-09: The bucket sweep settled the CI half of the trigger by reading
  `.github/workflows/ci.yml`, which installs no system library and states the shell is never built
  there.
- 2026-08-10: The accumulation half was run rather than read. The shell's own
  `cargo clippy --all-targets` with warnings denied exits 0 over 978 lines in 12 files, where this
  entry records 881 in 11, and a planted `useless_format` makes the same command exit 101. The run
  also corrected the entry's route for this host: `pkg-config` is real here and no shim was needed,
  what is missing being 47 `-dev` packages of `.pc` metadata, unpacked without sudo, which is the
  CI provisioning cost the decline rests on measured rather than restated. Neither trigger fired.
- 2026-08-17: Landed, by splitting rather than by paying: a separate path-filtered CI job running
  a new `just check-shell`, gated on a fourth classifier output, so only a shell edit provisions
  webkit. The decline's premise, that this had to ride inside `check-body`, was the defect, and
  its numbers were high (103 packages and 39.6 MB, not a 630-package closure; 30.9 s for a cold
  clippy of the whole Tauri graph). `just check` deliberately does not run the new recipe, the
  first check in this repo CI schedules and the single gate does not, argued at the origin. Both
  levels were proven able to fail. Residue filed as
  [300](300-shell-job-never-ran-on-a-runner.md).
