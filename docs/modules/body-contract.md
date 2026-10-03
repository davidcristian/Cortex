# body/crates/contract (`body_contract`)

**Purpose.** The shared check lists for the body's ports, and the fakes they hold to the same
description as the real adapters ([ADR-0068](../adr/ADR-0068-port-contract-lists.md) decisions 11
and 12). A check written once runs over the fake in this crate's tests and over every adapter CI
can run, so a fake cannot promise what an adapter does not do. Only dev-dependencies name the
crate; nothing that ships links it.

## Public contract

- **`audio`**, the `AudioControl` list. `AudioSubject` builds the implementation under test in each
  condition a check needs: `holding(VolumeState)`, `without_endpoint()` and `broken()`, each a
  `Box<dyn AudioControl>`. `AUDIO_CHECKS` is a `const` table of eight `(name, fn(&dyn
  AudioSubject))` pairs, and `run(&dyn AudioSubject)` calls them in order, writing
  `audio check: <name>` to stderr before each, so a failing driver's output names the check.
- The eight checks: a read reports the state held; a change reports the state it made; the next
  read reports the change; a level alone keeps the mute flag; a mute flag alone keeps the level;
  an empty change changes nothing; no endpoint fails both calls with `NoEndpoint`; a broken backend
  fails both with `Backend`.
- **`notify`**, the `Notify` list, the same shape. `NotifySubject` builds `showing()`,
  `declining()`, `without_service()` and `broken()`; `declining` returns an `Option`, since a
  backend whose service cannot decline returns `None` and the check that needs it returns early.
  The five checks, each over three reminders that differ in taint, markup and length: a shown
  notification answers `true`; one backend answers each of several calls; a declined one answers
  `false`; no service fails with `Unavailable`; a broken backend fails with `Backend`.
- **`screen`**, the `ScreenCapture` list. `ScreenSubject` builds `showing(RawFrame)`, a display
  with no window to point at; `pointing_at(RawFrame, TargetRect)`, an `Option` because
  `LinuxScreenCapture` cannot capture one window; `without_display()`; and `broken()`. The six
  checks, over two frames and three edges: a display capture answers the whole display at its own
  size with no window; a focus capture names the window on the whole display; a display capture
  leaves a focused window out; a focus capture with no window fails; no display fails with
  `NoDisplay`; a broken backend fails with `Backend`. A frame is compared by size and its blue,
  green and red bytes, since no backend promises the fourth. `DeniedScreenCapture` runs no driver:
  it is the switched-off condition alone, and `body/crates/core/tests/screen.rs` checks it refuses
  every request with `Disabled`.
- **`FakeAudio`**, the one stand-in `AudioControl` every body test uses: `new(level, muted)` holds
  a state in memory, `failing(AudioError)` answers every call with that error, and `panicking()`
  panics inside every call. `threads()` returns the `Threads` handle on the thread each call ran on,
  which the `BodyService` tests read after the fake has moved into a server.
- **`FakeNotify`**, the one stand-in `Notify`: `answering(shown)`, `failing(NotifyError)` and
  `panicking()`, with `seen()` returning every notification a call answered and `threads()` as
  above. A clone shares both records, so a test keeps one after the other moves into a server.
- **`FakeScreen`**, the one stand-in `ScreenCapture`: `answering(RawFrame)` is a display with no
  window, so a focus request fails with `NoTarget`; `showing(RawFrame, TargetRect)` resolves a focus
  request to that window and answers a display request with the display; `failing(CaptureError)`;
  and `miscounting(width, height, pixels)`, a buffer that does not match its size, which
  `RawFrame::new` refuses. `requests()` returns the `Requests` handle on every request it was
  handed, and `threads()` as above.
- The drivers: `tests/audio.rs`, `tests/notify.rs` and `tests/screen.rs` here, over the fakes;
  `body/crates/os_linux/tests/audio_contract.rs`, over `LinuxAudioControl` on `SoundServer`, a
  stand-in `pactl` holding one default sink that the set commands change and the get commands
  print; `the_linux_backend_meets_every_notify_check` in `body/crates/os_linux/tests/notify.rs`,
  over `LinuxNotify` on that file's `FakeBus`, `declining` returning `None` because the
  freedesktop specification gives a server no way to decline; and
  `the_linux_backend_meets_every_screen_check` in `body/crates/os_linux/tests/screen.rs`, over
  `LinuxScreenCapture` on that file's `FakeRoot`.

## Invariants

- Each check is a plain function over `&dyn`, never generic, so it is one coverage record that
  every driver adds to; a generic check keeps one record per implementation under
  `cargo llvm-cov`, and a branch taken one way by each would read as half covered.
- A check compares only what every implementation agrees on. A level is compared at a sound
  server's resolution of 1/65536, because `LinuxAudioControl` rounds to it, and an error by its
  variant through `std::mem::discriminant`, because each backend writes its own text.
- What an adapter sends to the OS (the `pactl` arguments, the raw volume, the bus message and
  its escaping) is not on the list. It is checked in that adapter's own tests
  ([body-os.md](body-os.md)), and what a fake was handed in the `BodyService` tests.
- The crate is measured at 100% line, region and branch coverage like every workspace member. The
  fakes' failure and panic paths are reached by the rpc server's tests and the lists.

**Dependencies.** `body-core` (the ports). Dev-dependency of `body-rpc` (for the fakes) and of
`os-linux` (for the lists). The ports still without a list are in
[R-018](../refinements/tasks/018-ports-without-contract-suite.md).
