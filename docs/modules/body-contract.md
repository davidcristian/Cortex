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
- **`hotkey`**, the `Hotkey` list. A callback runs later, on a press, so `HotkeySubject` builds a
  `HotkeyRig` in each condition: `listening()`, `taken()` (another program holds
  `HotkeyChord::default()`) and `broken()`. A rig gives the `hotkey()` under test, `press(chord)`,
  and `finish()`, which returns once every press so far has reached the backend. The six checks: a
  press runs the callback once; registering runs nothing until a press; each press runs only its
  own chord's callback, over two keys under one modifier and the second key under another; a key
  with no code fails with `UnsupportedKey`; a taken chord fails with `Registration` and a press runs
  nothing; a broken backend fails with `Registration`. `CHORDS` names the chords a driver's
  keyboard must have.
- **`transport`**, the `BrainTransport` list for every call but `converse`. The port is not
  dyn-compatible, so `Calls` is its twin, each call returning a boxed `Reply`, implemented once
  for every `T: BrainTransport`. `TransportSubject` builds `serving(&Held)`, a brain that starts
  from a health, its `Chat`s (hoisted first, then newest first), its due reminders and its settings
  sorted by key, and applies each write to them; `refusing()`, a brain failing every call with
  `Unavailable`, `store down`; and `unreachable()`. Each check returns a boxed future, and
  `run(&dyn TransportSubject)` awaits them in order. The fourteen checks: the health is what the
  brain holds, ready or not; a listing names every chat; a listing stops at its limit; a history is
  the asked chat's, in order; a rename shows in the next listing; a delete drops the chat from it; a
  hoist moves the chat above the rest; the due reminders are what the brain holds; an ack clears
  only the fire it names, once; the settings are what the brain holds; a written setting reads
  back in key order; an empty value clears its setting; a refusing brain fails every call with
  `Rpc` and its code and message; an unreachable one fails every call with `Connection`.
- **`FakeAudio`**, the one stand-in `AudioControl` every body test uses: `new(level, muted)` holds
  a state in memory, `failing(AudioError)` answers every call with that error, and `panicking()`
  panics inside every call. `threads()` returns the `Threads` handle on the thread each call ran on,
  which the `BodyService` tests read after the fake has moved into a server.
- **`FakeHotkey`**, the one stand-in `Hotkey`: `default()` keeps each callback it registers and
  `press(chord)` runs those registered for that chord; `failing(HotkeyError)` refuses every chord.
  Both refuse a key with no code first, through `Accelerator::from_chord`, as the real backends do.
  It holds its callbacks in a `RefCell`, so it is not `Sync`, which the port does not require.
- **`FakeNotify`**, the one stand-in `Notify`: `answering(shown)`, `failing(NotifyError)` and
  `panicking()`, with `seen()` returning every notification a call answered and `threads()` as
  above. A clone shares both records, so a test keeps one after the other moves into a server.
- **`FakeScreen`**, the one stand-in `ScreenCapture`: `answering(RawFrame)` is a display with no
  window, so a focus request fails with `NoTarget`; `showing(RawFrame, TargetRect)` resolves a focus
  request to that window and answers a display request with the display; `failing(CaptureError)`;
  and `miscounting(width, height, pixels)`, a buffer that does not match its size, which
  `RawFrame::new` refuses. `requests()` returns the `Requests` handle on every request it was
  handed, and `threads()` as above.
- The drivers: `tests/audio.rs`, `tests/hotkey.rs`, `tests/notify.rs` and `tests/screen.rs` here,
  over the fakes;
  `body/crates/os_linux/tests/audio_contract.rs`, over `LinuxAudioControl` on `SoundServer`, a
  stand-in `pactl` holding one default sink that the set commands change and the get commands
  print; `the_linux_backend_meets_every_notify_check` in `body/crates/os_linux/tests/notify.rs`,
  over `LinuxNotify` on that file's `FakeBus`, `declining` returning `None` because the
  freedesktop specification gives a server no way to decline; and
  `the_linux_backend_meets_every_screen_check` in `body/crates/os_linux/tests/screen.rs`, over
  `LinuxScreenCapture` on that file's `FakeRoot`; and `the_linux_backend_meets_every_hotkey_check`
  in `body/crates/os_linux/tests/hotkey.rs`, over `LinuxHotkey` on that file's `FakeKeys`, whose
  `Rig` presses each chord as the key and state a `PRESSES` table names. The transport's drivers
  are `the_fake_meets_every_transport_check` in `body/crates/core/tests/transport.rs`, over that
  file's `FakeTransport`; `retrying_over_the_fake_meets_every_transport_check` beside it, over
  `RetryingTransport` wrapping that fake; and `body/crates/rpc/tests/transport_contract.rs`, over
  `BrainRpcClient`
  on the scripted `BrainService` in `body/crates/rpc/tests/brain/mod.rs` that every rpc test
  serves.

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

**Dependencies.** `body-core` (the ports). Dev-dependency of `body-rpc` (for the fakes and the
transport list), of `os-linux` (for the lists) and of `body-core` (for the transport list). The
transport's turn is [R-781](../refinements/tasks/781-a-shared-check-list-for-the-brain-transport.md).
