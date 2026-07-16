# body/crates/core (`body_core`)

**Purpose.** The body's pure core: host-side domain types and ports, including the
OS-capability ports in `os` (`Hotkey` from Slice 8; `AudioControl` and `Notify` from
Slices 9/9.5; `ScreenCapture`/`InputControl` join in Slice 10). No OS calls, ever. Per-platform backends live in
the `os_windows`/`os_linux`/`os_macos` crates (`docs/modules/body-os.md`). Currently: the
typed global-hotkey chord, the `BrainTransport` port to the brain seam (`health` +
streaming `converse` + the session and reminder reads) with the `RetryingTransport`
decorator + `Sleeper` port that add bounded-retry resilience over it (ADR-0024), the `link`
classification behind the overlay's connection indicator (ADR-0011 addendum), and the
`Hotkey` port with the `Accelerator` chord→code mapping.

**Public contract.**

- `Modifier` is `Ctrl | Alt | Shift | Super` (`Copy`, `Eq`, `Ord`).
- `HotkeyChord` is a validated chord; constructed only via `parse` or `Default`.
  - `HotkeyChord::parse(&str) -> Result<HotkeyChord, HotkeyParseError>` splits on
    `+`, trims, case-insensitive; aliases `control`→Ctrl, `win`/`cmd`/`meta`→Super.
    The last segment is the key and must not be a modifier. Bare keys (zero modifiers,
    e.g. `"escape"`) are valid. Modifiers are canonicalized to Ctrl, Alt, Shift, Super
    order regardless of input order.
  - `modifiers()` / `key()` accessors; `Display` renders the canonical lowercase form
    (`"ctrl+alt+space"`); `parse`/`Display` round-trip holds.
  - `Default` is `ctrl+alt+space` (the proposed default hotkey, ROADMAP assumption 7).
- `HotkeyParseError` (thiserror) has variants `Empty`, `EmptySegment`, `UnknownModifier(String)`,
  `DuplicateModifier(String)`, `MissingKey(String)` (chord ends in a modifier).
- `SeamHealth` is the result of a `BrainService.Health` probe: public fields `ready: bool`,
  `detail: String` (`Clone`, `Eq`, `Debug`).
- `TransportError` (thiserror) has `Connection(String)` (brain unreachable: bad address,
  refused connection, transport failure) | `Rpc { code: String, message: String }`
  (reached, but the RPC returned a non-OK gRPC status; `code` is the status-code name,
  e.g. `Internal`, `Unimplemented`) | `Protocol(String)` (reached and streaming, but the
  wire data is uninterpretable: an empty `ServerEvent`, or a `Converse` stream that ended
  before `TurnComplete`, a `converse`-only variant, distinct from a brain-*reported* turn
  error, which is `TurnEvent::Failed`).
- `TurnEvent` is the typed core mirror of the proto `ServerEvent`, streamed by `converse`
  (`Clone`, `Eq`, `Debug`): `Delta(String)` (assistant text) | `ToolActivity { tool_name,
  summary }` | `Status { state, detail }` | `ConfirmRequest { confirm_id, tool_name,
  arguments_json, reason }` (a gated tool call awaits the user's approval, ADR-0022;
  **non-terminal**, answered via the `decisions` stream) | `ConfirmResolved { confirm_id,
  outcome }` (the brain stopped waiting on one, so a surface showing it can close it;
  **non-terminal**, and emitted only for endings the caller cannot know: `"timeout"` and
  `"unavailable"`, never the caller's own answer) | `Complete { turn_id }` (terminal) |
  `Failed { code, message }` (brain-reported turn error; terminal, since the connection is fine).
- `ConfirmDecision { confirm_id, approved }` is the user's answer to a `ConfirmRequest`
  (`Clone`, `Eq`, `Debug`; ADR-0022): fed into `converse`'s `decisions` stream, delivered
  to the brain as a `ConfirmResponse` on the open `Converse` stream.
- `SessionSummary` / `SessionMessage` are typed core mirrors of the proto session-read messages
  (`Clone`, `Eq`, `Debug`; ADR-0021). `SessionSummary { session_id, title, preview,
  last_activity_unix_ms }` is one recent chat as the switcher shows it (title/preview already
  derived); `SessionMessage { role, text, turn_id, at_unix_ms }` is one persisted message
  (`role` is `"user"`/`"assistant"`).
- `DueReminder` is the typed core mirror of the proto `DueReminder` (`Clone`, `Eq`,
  `Debug`; ADR-0025): `{ reminder_id, text, fired_at_unix_ms, recurring, tainted,
  session_id }`, one fired-but-undelivered reminder. `text` is display-only and **inert**:
  a `tainted` one was scheduled out of content the brain does not trust, so a surface
  renders it as text, never as markup, a link, or an instruction, and the bit rides along
  so it can badge provenance instead of guessing. `session_id` is empty for a
  session-less caller (the ticker's own fire).
- `BrainTransport` is the body's typed async client port to the brain seam
  (`Send + Sync` supertraits):
  - `health(&self)` returns `impl Future<Output = Result<SeamHealth, TransportError>> +
    Send`, so implementors just write `async fn health`.
  - `converse(&self, session_id, text, decisions)` returns `impl Stream<Item =
    Result<TurnEvent, TransportError>> + Send`, giving one turn per call (ADR-0011: session
    continuity is external, so each prompt is a fresh call sharing the `session_id`;
    dropping the returned stream still cancels the turn). `decisions: impl Stream<Item =
    ConfirmDecision> + Send + 'static` answers mid-turn `ConfirmRequest`s (ADR-0022); the
    request stream half-closes when it ends (a caller with no confirm surface passes an
    empty stream, which is the pre-8.8 one-shot shape). An unanswered/undeliverable confirm is
    denied brain-side (fail-closed), so a decision sent after teardown is a harmless
    no-op. `Ok(TurnEvent)` per brain event; `Err(TransportError)` for a
    transport/protocol failure. v1 sends text only. Images (vision) arrive in Slice 10.
  - `list_sessions(&self, limit)` / `session_messages(&self, session_id)` (ADR-0021) are the
    read-only session views the overlay's chat list / switcher / cycling load: `Vec<SessionSummary>`
    newest-active first (at most `limit`; `0` = the brain default) and `Vec<SessionMessage>` in
    append order. Both `impl Future<... > + Send`; a store failure surfaces as
    `TransportError::Rpc` (`Unavailable`).
  - `list_due_reminders(&self)` / `ack_reminder(&self, reminder_id)` (ADR-0025) are the
    overlay's pull path: `Vec<DueReminder>` of everything fired and still awaiting
    delivery (all sessions, since one user has one set of reminders), and the one
    **write** on this port, marking one delivered when the user dismisses it. `ack`
    answers `bool`: `false` is a state report (nothing to clear, because the id is
    unknown or already acked), never a failure, so acking twice is a no-op. A brain
    running with no schedule backend answers an empty list and `false` rather than an
    error, so it is indistinguishable from one with nothing due (deliberate: an
    `Unavailable` would be classified transient and turn every overlay open into a
    retry storm).
  The gRPC adapter is `body/crates/rpc` (`docs/modules/body-rpc.md`); fakes implement
  the same trait for tests.

Retry resilience (`retry` module, ADR-0024) is a decorator over the port, so the adapter
stays thin and the retry is exercised against a fake with no network or wall-clock:

- `Sleeper` is a timer effect port: `sleep(&self, Duration) -> impl Future<Output = ()> +
  Send`. The one seam the retry loop waits on; a fake records the schedule and returns
  instantly, the real `tokio::time::sleep` lives in the ungated shell.
- `Randomness` is a jitter effect port (ADR-0024 addendum): `unit(&self) -> f64`, one draw
  in `[0, 1]` per backoff. `FullDelay` (the exported `Randomness` impl returning a constant
  `1.0`) turns jitter off structurally: the retry loop scales each delay by
  `0.5 + 0.5·unit()` (equal jitter, half kept as a floor so the wait still lets a restarting
  brain recover), which for a constant `1.0` degenerates to the exact deterministic schedule.
  The real `ShellRandomness` (a `RandomState`-seeded draw) lives in the ungated shell; tests
  inject a scripted fake. A draw is sanitized (out-of-range clamped into `[0, 1]`, a
  non-finite draw treated as the full delay so `clamp` cannot pass a `NaN` to a panicking
  `mul_f64`), so a misbehaving source cannot panic the `Duration` math.
- `RetryPolicy` (`Copy`, `Eq`, `Debug`) is a bounded exponential-backoff schedule: public
  fields `max_attempts` (total tries incl. the first; `0`/`1` disable retry), `base_delay`,
  `multiplier`, `max_delay` (cap). `delay(index)` = `min(base·multiplierⁱⁿᵈᵉˣ, max_delay)`
  (saturating, so no overflow escapes the cap); `backoff(attempt, error)` returns the wait to
  apply or `None` to give up (retry only while an attempt remains *and* the error is
  transient). `Default` = 3 attempts / 200 ms / ×2 / 2 s cap.
- `is_transient(&TransportError) -> bool` is the retryable classifier: `Connection` and
  `Rpc{code=="Unavailable"}` are transient; every other `Rpc` status and `Protocol` are not.
- `retry_with(policy, sleeper, randomness, call)` is the bounded-retry loop over any fallible
  async factory (ADR-0024 addendum): re-issues `call()` each attempt, sleeping the jittered
  delay while `backoff` says so. Public so patience composes around a non-transport factory,
  which the shell uses to wrap its eager `converse` dial (safe: the non-idempotent turn has
  not begun until the dial succeeds).
- `RetryingTransport<T: BrainTransport, S: Sleeper, R: Randomness = FullDelay>` *is* a
  `BrainTransport`: wraps an inner transport and retries its **idempotent** methods (`health`,
  `list_sessions`, `session_messages`, `list_due_reminders`) via `retry_with` on a transient
  failure per the policy, sleeping via the `Sleeper` between tries. `converse` is forwarded
  **unchanged**, since it is non-idempotent, its `decisions` stream is one-shot, and a failed
  turn is terminal by the overlay's contract (ADR-0024 decision 2). `ack_reminder` is forwarded
  unchanged too (ADR-0025): repeating the write is harmless brain-side, but a retry that lands
  after a lost reply answers `false` for a reminder this very call cleared, which reads at the
  caller as "there was nothing to ack"; surfacing the transient failure keeps that ambiguity
  out of the answer, and the next overlay open re-lists whatever is still due. `new(inner,
  sleeper, policy)` (no jitter, the v1 default) or `with_randomness(inner, sleeper, randomness,
  policy)` (jittered).

Connection classification (`link` module, ADR-0011 addendum) is what the overlay's indicator
draws. It is here, not in a component or the shell, because "what does this failure prove"
is domain logic:

- `LinkState` (`Copy`, `Eq`, `Debug`) is `Ready | Degraded | Down`, with `as_str()` giving the
  stable names the overlay's own `LinkState` union uses (`ready`/`degraded`/`down`).
  **`Degraded` means the brain answered and is not serving**; only `Down` means nothing
  answered. The overlay adds its own `unknown` for "not asked yet"; the seam never reports it.
- `LinkStatus { state, detail }` (`Clone`, `Eq`, `Debug`) is one classified answer, `detail`
  being display-only text (never parsed, rendered inert).
  - `from_health(&SeamHealth)`: `ready` → `Ready`, else `Degraded`, carrying the brain's own
    detail. The brain's readiness verdict wins over mere reachability.
  - `from_error(&TransportError)`: `Connection` → `Down` (nothing answered) with the dial
    failure; `Rpc { code, message }` → `Degraded` as `"{code}: {message}"` (the brain answered,
    e.g. `Unauthenticated` for a rejected seam token); `Protocol` → `Degraded` as
    `"unreadable reply: …"`.
- `probe_link(&impl BrainTransport) -> LinkStatus` awaits `health` and classifies the outcome.
  **It never fails**: a failure is the answer, which is what lets a caller render a state
  instead of an error. Composed over `RetryingTransport` it is also the reconnect attempt,
  since `health` is retried, so `Down` means the whole backoff budget failed to reach the brain.

OS-capability ports (`os` module) are the first portability seam (ADR-0011):

- `Hotkey` is the global-hotkey backend port: `register(&self, chord: &HotkeyChord,
  on_activate: HotkeyCallback) -> Result<(), HotkeyError>`. The body registers one chord
  for its lifetime; the backend owns the OS registration and fires `on_activate` on each
  press. Per-platform adapters (`os_windows` real; `os_linux`/`os_macos` stubs) are documented in
  `docs/modules/body-os.md`.
- `HotkeyCallback` is `Box<dyn Fn() + Send + 'static>`, invoked on an OS/event-loop thread.
- `HotkeyError` (thiserror, `Clone`) is `UnsupportedKey(String)` (the key has no `code`
  mapping) | `Registration(String)` (the OS refused the binding).
- `Accelerator` is a chord resolved to the OS-neutral form a backend needs: `modifiers:
  Vec<Modifier>` (canonical order) + `code: String` (the W3C `KeyboardEvent.code` name,
  e.g. `"Space"`, `"KeyA"`, `"F5"`). `Accelerator::from_chord(&HotkeyChord) ->
  Result<Accelerator, HotkeyError>` maps letters→`KeyA`…, digits→`Digit0`…, `f1`…`f24`→
  `F1`…`F24`, and a small named set (space, enter/return, escape/esc, tab, backspace,
  arrows); anything else is `UnsupportedKey`. Pure and fully tested, covering the key-mapping logic
  the backend would otherwise hold untested.

The `AudioControl` volume port (ADR-0023) is documented with its adapters in
`docs/modules/body-os.md`. The notification port (`os::notify`, ADR-0025) is the push half of
reminder delivery:

- `Notify` is the notification-backend port: `show(&self, &Notification) -> Result<bool,
  NotifyError>`, `Send + Sync` for the same reason as `AudioControl` (the `BodyService`
  server holds it across async tasks). `Ok(false)` is a **state report**, not a failure: the
  host was reached and declined, typically because notifications are switched off. The brain
  treats `false` and an error identically (the reminder stays deliverable and the overlay's
  pull path shows it on the next open), so the split exists to keep the body's own logs
  honest, not to change the outcome.
- `NotifyError` (thiserror, `Clone`) is `Unavailable(String)` (no notification service
  reachable) | `Backend(String)` (the backend refused or failed), the same transient/fault
  split as `AudioError`.
- `Notification` is the value a backend renders, built only by `Notification::new(title,
  body, reminder_id, tainted)`, which is where the **inert-text rule** lives: every control
  character becomes a space (replaced, not dropped, so words never fuse across a stripped
  newline, and a raw control byte can never make a backend's document unparseable) and each
  line is bounded at `MAX_TEXT_CHARS` (200) with a trailing ellipsis marking the cut, because
  an oversized payload is refused by the OS as a whole, which would turn a long reminder into
  no reminder. Accessors `title()`, `body()`, `reminder_id()`, `tainted()`, and
  `attribution()`, which answers the fixed `UNTRUSTED_ATTRIBUTION` line
  (`"from an untrusted source"`) for a tainted reminder and `None` otherwise: the badge that
  describes untrusted text is body-authored so it can never be written by that text. The
  value sanitizes rather than each backend because a fired reminder is the one string the
  body renders that **no output guardrail inspected** (ADR-0015 filters streamed replies, not
  store rows).
- `os::escape_xml(&str) -> String` escapes the five predefined XML entities, for a backend
  whose renderer is a markup template (the Windows toast). It is *not* applied by
  `Notification`, since the right escape differs per renderer and a value that pre-escaped
  would double-escape at one that does its own. It lives here, gated, because the only caller
  is `cfg(windows)` and never measured in CI: leaving the escape there would rest the seam's
  data-not-instructions posture on untested code.

**Invariants.**
- Pure: no OS/network calls; `unsafe_code = "forbid"`; no `unwrap`/`expect` outside
  tests (workspace lints).
- An existing `HotkeyChord` is always canonical. Invalid states are unrepresentable.
- 100% line+region+branch covered by behavior tests in `tests/` (never inline test
  modules; the 300-line cap counts source files, per ADR-0002).

**Dependencies.** `thiserror` and `futures-core` (the `Stream` trait for the `converse`
return type, and the `Future` bound the retry loop is generic over). Both are trait/type-only,
no runtime; time is the injected `Sleeper` port, never a timer dependency. Dev-only: `tokio`
and `tokio-stream` (to await `health`, drain the `converse` contract streams, and drive the
`RetryingTransport` fakes).
