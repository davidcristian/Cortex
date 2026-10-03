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
- **`FakeAudio`**, the one stand-in `AudioControl` every body test uses: `new(level, muted)` holds
  a state in memory, `failing(AudioError)` answers every call with that error, and `panicking()`
  panics inside every call. `threads()` returns the `Threads` handle on the thread each call ran on,
  which the `BodyService` tests read after the fake has moved into a server.
- The drivers: `tests/audio.rs` here, over `FakeAudio`, and
  `body/crates/os_linux/tests/audio_contract.rs`, over `LinuxAudioControl` on `SoundServer`, a
  stand-in `pactl` holding one default sink that the set commands change and the get commands
  print.

## Invariants

- Each check is a plain function over `&dyn`, never generic, so it is one coverage record that
  every driver adds to; a generic check keeps one record per implementation under
  `cargo llvm-cov`, and a branch taken one way by each would read as half covered.
- A check compares only what every implementation agrees on. A level is compared at a sound
  server's resolution of 1/65536, because `LinuxAudioControl` rounds to it, and an error by its
  variant through `std::mem::discriminant`, because each backend writes its own text.
- What an adapter sends to the OS (the `pactl` arguments, the raw volume) is not on the list. It
  is checked in that adapter's own tests ([body-os.md](body-os.md)).
- The crate is measured at 100% line, region and branch coverage like every workspace member. The
  `FakeAudio` failure and panic paths are reached by the rpc server's tests and the list.

**Dependencies.** `body-core` (the ports). Dev-dependency of `body-rpc` (for `FakeAudio`) and of
`os-linux` (for the list). The ports still without a list are in
[R-018](../refinements/tasks/018-ports-without-contract-suite.md).
