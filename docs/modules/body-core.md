# body/crates/core (`body_core`)

**Purpose.** The body's pure core: the host-side domain types and the ports that reach the outside
world. It makes no OS calls and no network calls of its own. It holds the typed global-hotkey chord
and its key mapping, the `BrainTransport` port with the `RetryingTransport` decorator that adds
bounded retry and a bound to every call on it (ADR-0024), the `link` classification behind the
overlay's connection indicator (ADR-0011 decision 8), and the OS-capability ports. The per-platform
backends live in the `os_windows`, `os_linux` and `os_macos` crates ([body-os.md](body-os.md)); the
gRPC adapter is `body/crates/rpc` ([body-rpc.md](body-rpc.md)).

## Where the rest of this contract is written

Two areas of this crate have documents of their own:

- [body-core-retry.md](body-core-retry.md): the `retry` module. The timer and jitter ports, the
  backoff schedule, which methods may be repeated, the per-call deadlines and the turn's silence
  bounds, and the `RetryingTransport` decorator that applies them.
- [body-core-capture.md](body-core-capture.md): the `os::screen` ports and the pure size policy
  behind a screen capture.

## The hotkey chord

- `Modifier` is `Ctrl | Alt | Shift | Super` (`Copy`, `Eq`, `Ord`).
- `HotkeyChord` is a validated chord, built only through `parse` or `Default`.
  `HotkeyChord::parse(&str) -> Result<HotkeyChord, HotkeyParseError>` splits on `+`, trims and
  ignores case; the aliases are `control` for Ctrl and `win`, `cmd` and `meta` for Super. The last
  segment is the key and must not be a modifier, and a bare key such as `"escape"` is valid.
  Modifiers are put into Ctrl, Alt, Shift, Super order whatever order they arrived in. `modifiers()`
  and `key()` are the accessors, `Display` renders the canonical lowercase form
  (`"ctrl+alt+space"`), `parse` and `Display` round-trip, and `Default` is `ctrl+alt+space`.
- `HotkeyParseError` (thiserror) is `Empty`, `EmptySegment`, `UnknownModifier(String)`,
  `DuplicateModifier(String)` or `MissingKey(String)` (the chord ends in a modifier).
- `Accelerator` is a chord resolved to the OS-neutral form a backend needs:
  `modifiers: Vec<Modifier>` in canonical order plus `code: String`, the W3C `KeyboardEvent.code`
  name such as `"Space"` or `"KeyA"`. `Accelerator::from_chord(&HotkeyChord)` maps letters to `KeyA`
  and so on, digits to `Digit0` and so on, `f1` to `f24` to `F1` to `F24`, and a small named set
  (space, enter or return, escape or esc, tab, backspace, the arrows); anything else is
  `UnsupportedKey`. It is pure and fully tested, which covers mapping a backend would otherwise hold
  untested.

## The brain transport

- `SeamHealth` is the result of a `BrainService.Health` probe: `ready: bool` and `detail: String`.
- `TransportError` (thiserror) is `Connection(String)` (the brain is unreachable: a bad address, a
  refused connection, a transport failure), `Rpc { code: String, message: String }` (it was reached
  and the RPC returned a non-OK gRPC status, `code` being the status-code name), `Protocol(String)`
  (it was reached and streaming, but the wire data cannot be read: an empty `ServerEvent`, or a
  `Converse` stream that ended before `TurnComplete`), or `Timeout { after: Duration }` (nothing
  came back inside the deadline, so the call was dropped). The fourth reports what the other three
  cannot: `Connection` says nothing accepted the call and `Rpc` says the brain answered, while a
  deadline says **this side stopped waiting** (ADR-0024 decision 12). `Protocol` differs from a
  brain-*reported* turn error, which is `TurnEvent::Failed`.
- `TurnEvent` is the typed core mirror of the proto `ServerEvent`, streamed by `converse`. It lives
  in the `transport::turn` submodule, re-exported from `transport`.
  - `Delta(String)` is assistant text and `Status { state, detail }` is progress.
  - `ToolActivity { tool_name, summary }` announces one dispatch and `ToolOutcome { tool_name, ok }`
    says how it ended (ADR-0029 decision 18). Both are **non-terminal**. An outcome may only
    strengthen what a surface claims, so `ok: false` means the brain cannot say the tool reached
    anything rather than that nothing happened. **The pairing is not a property of the stream and
    this side must not read it as one**: a delegating turn reports its subagents' tool steps as
    `ToolActivity` through a best-effort side channel that sends no outcome and drops on a full
    buffer, so an activity nothing settles is ordinary.
  - `ConfirmRequest { confirm_id, tool_name, arguments_json, reason }` says a tool call awaits the
    user's approval (ADR-0022); it is non-terminal and is answered through the `decisions` stream.
    `ConfirmResolved { confirm_id, outcome }` says the brain stopped waiting on one, so a surface
    can close it; it is non-terminal and is sent only for endings the caller cannot know,
    `"timeout"` and `"unavailable"`, never the caller's own answer.
  - `Heartbeat` says the brain's turn is still running (ADR-0069). It is non-terminal, and
    `within_gaps` consumes it, so a surface behind `RetryingTransport` never receives one.
  - `Complete { turn_id }` and `Failed { code, message }` are the two terminal events.
- `ConfirmDecision { confirm_id, approved }` is the user's answer to a `ConfirmRequest`, fed into
  `converse`'s `decisions` stream and delivered as a `ConfirmResponse` on the open stream.
- `SessionSummary { session_id, title, preview, last_activity_unix_ms, hoisted }` is one recent
  chat as the switcher shows it, the title and preview already derived and `hoisted` saying whether
  the user hoisted it, which the brain lists first and above the recency window (ADR-0021 decision
  12).
  `SessionMessage { role, text, turn_id, at_unix_ms }` is one stored message.
- `DueReminder { reminder_id, text, fired_at_unix_ms, recurring, tainted, session_id }` is one fired
  reminder still awaiting delivery (ADR-0025). `text` is display-only and **inert**: a `tainted` one
  was scheduled out of content the brain does not trust, so a surface renders it as text, never as
  markup, a link or an instruction, and the bit travels with it so the surface can badge provenance
  instead of guessing. `session_id` is empty for the ticker's own fire.

`BrainTransport` is the typed async client port to the brain, `Send + Sync`. Fakes implement the
same trait for tests.

- `health(&self)` returns `impl Future<Output = Result<SeamHealth, TransportError>> + Send`.
- `converse(&self, session_id, text, decisions)` returns
  `impl Stream<Item = Result<TurnEvent, TransportError>> + Send`, one turn per call (ADR-0011:
  session continuity is external, so each prompt is a fresh call sharing the `session_id`, and
  dropping the returned stream cancels the turn). `decisions: impl Stream<Item = ConfirmDecision>
  + Send + 'static` answers mid-turn `ConfirmRequest`s (ADR-0022); the request stream half-closes
  when it ends, so a caller with no confirmation surface passes an empty stream. An unanswered
  confirmation is denied brain-side, so a decision sent after teardown does nothing.
- `list_sessions(&self, limit)` and `session_messages(&self, session_id)` (ADR-0021) are the
  read-only views the overlay's chat list and switcher load: `Vec<SessionSummary>` newest active
  first, at most `limit` with `0` meaning the brain's default, and `Vec<SessionMessage>` in append
  order. A store failure arrives as `TransportError::Rpc` with code `Unavailable`.
- `rename_session(&self, session_id, title)` (`""` clears the override),
  `delete_session(&self, session_id)` and `set_session_hoisted(&self, session_id, hoisted)` are the
  three user-driven catalog writes (ADR-0021 decisions 10 to 12). Each is reachable only from the
  overlay's own list controls, never from a model, a tool or a tainted turn, and none is retried, so
  a lost reply is reported rather than re-applied. `delete_session` is **destructive**: the brain
  hard-deletes the transcript and cascades to the chat's private memories, and a silent retry could
  destroy a chat a still-streaming turn re-created.
- `get_preferences(&self)` and `set_preference(&self, key, value)` (ADR-0032) are the user's
  settings record. The read answers `Vec<(String, String)>` of every stored pair, sorted by key,
  with values this layer does not interpret, and it retries with the other reads. The write stores
  one pair, an **empty** value clearing the key, and takes one attempt.
- `list_due_reminders(&self)` and `ack_reminder(&self, reminder_id, fired_at_unix_ms)` (ADR-0025)
  are the overlay's pull path: everything fired and still awaiting delivery across all sessions, and
  the one **write** on this port, marking a fire delivered when the user dismisses its card. The ack
  names the fire by the card's `fired_at_unix_ms`, so a card dismissed after a later fire replaced
  it clears nothing. `ack` answers `bool`, where `false` is a state report (the id is unknown,
  already acknowledged, or its fire was replaced) rather than a failure. A brain with no schedule
  backend answers an empty list and `false` rather than an error, which makes it indistinguishable
  from one with nothing due; an `Unavailable` would be classified transient and turn every overlay
  open into a retry storm.

## Connection classification (`link`, ADR-0011 decision 8)

This is what the overlay's indicator draws. It lives here rather than in a component or the shell
because what a failure proves is domain logic.

- `LinkState` is `Ready | Degraded | Down`, with `as_str()` giving the stable names the overlay's
  own `LinkState` union uses. **`Degraded` means the brain answered and is not serving**; only
  `Down` means nothing answered. The overlay adds its own `unknown` for "not asked yet".
- `LinkStatus { state, detail }` is one classified answer, `detail` being display-only text that is
  never parsed and is rendered inert. `from_health(&SeamHealth)` maps `ready` to `Ready` and
  anything else to `Degraded` with the brain's own detail. `from_error(&TransportError)` maps
  `Connection` to `Down` with the dial failure, `Rpc { code, message }` to `Degraded` as
  `"{code}: {message}"`, `Protocol` to `Degraded` as `"unreadable reply: …"`, and
  `Timeout { after }` to `Down` as `"no reply within …"`, because `Degraded` means the brain
  answered and an expired deadline is the absence of an answer (ADR-0024 decision 12). The detail
  names the deadline, so the tooltip still separates a wedged brain from an absent one.
- `probe_link(&impl BrainTransport) -> LinkStatus` awaits `health` and classifies the outcome. **It
  never fails**: a failure is the answer, which is what lets a caller render a state instead of an
  error. Composed over `RetryingTransport` it is also the reconnect attempt, so `Down` means the
  whole probe budget failed to reach the brain, and it arrives within
  `max(probe_budget, probe_deadline)`. How many attempts fit inside that bound is a fact about the
  host: a refused dial costs microseconds and leaves room for the retry the budget affords, while a
  dial the host drops spends the attempt's whole deadline, and an expired deadline is terminal, so
  the answer is one attempt old (ADR-0024 decision 24). The bound holds either way.

## OS-capability ports (`os`, ADR-0011)

- `Hotkey` is the global-hotkey port:
  `register(&self, chord: &HotkeyChord, on_activate: HotkeyCallback) -> Result<(), HotkeyError>`.
  The body registers one chord for its lifetime; the backend owns the OS registration and calls
  `on_activate` on each press. `HotkeyCallback` is `Box<dyn Fn() + Send + 'static>`, called on an OS
  or event-loop thread. `HotkeyError` (thiserror, `Clone`) is `UnsupportedKey(String)` (the key has
  no `code` mapping) or `Registration(String)` (the OS rejected the binding).
- `AudioControl` (ADR-0023) is documented with its adapters in [body-os.md](body-os.md).
- `Notify` (`os::notify`, ADR-0025) is the push half of reminder delivery:
  `show(&self, &Notification) -> Result<bool, NotifyError>`, `Send + Sync` because the `BodyService`
  server holds it across async tasks. `Ok(false)` is a **state report**, not a failure: the host was
  reached and declined, typically because notifications are switched off. The brain treats `false`
  and an error identically, so the split keeps the body's own logs accurate rather than changing the
  outcome. `NotifyError` (thiserror, `Clone`) is `Unavailable(String)` or `Backend(String)`, the
  same transient-or-fault split as `AudioError`.
- `Notification` is the value a backend renders, built only by
  `Notification::new(title, body, reminder_id, tainted)`, which is where the **inert-text rule**
  lives: every control character becomes a space (replaced rather than dropped, so words never fuse
  across a stripped newline and a raw control byte cannot make a backend's document unparseable) and
  each line is bounded at `MAX_TEXT_CHARS` (200) with a trailing ellipsis marking the cut, because
  the OS rejects an oversized payload as a whole. Its accessors are `title()`, `body()`,
  `reminder_id()`, `tainted()` and `attribution()`, which answers the fixed `UNTRUSTED_ATTRIBUTION`
  line (`"from an untrusted source"`) for a tainted reminder and `None` otherwise: the badge that
  describes untrusted text is written by the body so it can never be written by that text. The value
  sanitizes rather than each backend, because a fired reminder is the one string the body renders
  that **no output guardrail inspected** (ADR-0015 filters streamed replies, not stored rows).
- `os::escape_xml(&str) -> String` escapes the five predefined XML entities, for a backend whose
  renderer is a markup template (the Windows toast). It is *not* applied by `Notification`, since
  the right escape differs per renderer and a pre-escaped value would be double-escaped at one that
  does its own. It lives here, covered, because the only caller is `cfg(windows)`.

## Invariants

- Pure: no OS or network calls, `unsafe_code = "forbid"`, and no `unwrap` or `expect` outside tests
  (workspace lints). An existing `HotkeyChord` is always canonical.
- **The byte ceiling is one number in two toolchains.** `MAX_CAPTURE_BYTES` and the brain's
  `CORTEX_BODY_MAX_IMAGE_BYTES` are both 6 MiB, each held to the literal `6291456` by a test in its
  own toolchain, and the wire's `max_bytes` hint is what lets the brain hold the body to its own
  budget rather than to a duplicated constant. `scripts/crosscheck.py` compares the two, since no
  single-toolchain suite can see the other side (ADR-0042).
- 100% line, region and branch covered by behaviour tests in `tests/` (never inline test modules;
  the 300-line cap counts source files, ADR-0002), and **this crate declares no coverage escape**:
  everything in it is reachable from a test, which is why the capture's size policy is pure core
  rather than part of the `cfg(windows)` backend CI never compiles.
- **This workspace's tests run twice per check, in two different orders** (ADR-0002 decision 17), a
  property of `check-body` that covers `body-rpc` and the OS crates equally. `cargo test` stays on
  stable in libtest's alphabetical order; the nightly coverage step appends
  `-- -Z unstable-options --shuffle-seed=104729` and runs the same tests permuted, and both must
  pass. Three things follow for anyone adding a test here. The seed is fixed and lives in the
  `justfile`, libtest taking its arguments only on the command line, and it is unrelated to the
  other suites' seeds. Adding one test re-draws its whole binary, since libtest seeds on the seed
  plus a hash of the test-name list, so a failure can name a pair you did not touch and is still a
  real, reproducible order dependency. And the shuffle permutes *dispatch* order into 24 parallel
  threads, so it redraws pairs further apart than the thread count and changes nothing for adjacent
  ones, which were already racing. Each binary prints `(shuffle seed: 104729)` in its header, so a
  failing log names its order; `just shuffle [seed]` covers the other suites.

**Dependencies.** `thiserror` and `futures-core` (the `Stream` trait for the `converse` return type,
and the `Future` bound the retry loop is generic over), both trait and type only with no runtime;
time is the injected `Sleeper` port, never a timer dependency. Dev-only: `tokio` and `tokio-stream`,
to await `health`, drain the `converse` contract streams, and drive the `RetryingTransport` fakes.
