# body/crates/core (`body_core`)

**Purpose.** The body's pure core: host-side domain types and ports, including the
OS-capability ports in `os` (`Hotkey` from Slice 8; `AudioControl` and `Notify` from
Slices 9/9.5; `ScreenCapture` from Slice 10, with `InputControl` still to come). No OS calls, ever. Per-platform backends live in
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
- `TurnEvent` and `ConfirmDecision` are the turn vocabulary a `converse` call carries, and they
  live in the `transport::turn` submodule (split out for the line cap) re-exported from
  `transport`, so `body_core::TurnEvent` and `body_core::transport::TurnEvent` both still resolve.
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
  last_activity_unix_ms, pinned }` is one recent chat as the switcher shows it (title/preview
  already derived; `pinned` is whether the user pinned it, ADR-0021 pinning addendum, which the
  brain lists first and above the recency window); `SessionMessage { role, text, turn_id,
  at_unix_ms }` is one persisted message (`role` is `"user"`/`"assistant"`).
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
  - `rename_session(&self, session_id, title)` (ADR-0021 management addendum) is the overlay's
    user-driven relabel of a chat: a **write** (the catalog display title), `""` clears the
    override. Reachable only from the overlay's own list controls, never a model/tool/tainted
    turn. Not retried (`SeamMethod::RenameSession` is not repeatable), so a lost reply surfaces
    rather than re-labelling; a store failure surfaces as `TransportError::Rpc` (`Unavailable`).
  - `delete_session(&self, session_id)` (ADR-0021 delete addendum) is the overlay's user-driven
    DESTRUCTIVE removal of a chat (fired only after an overlay-local confirm): the brain hard-
    deletes the transcript and cascades to the chat's private memories. Reachable only from the
    overlay's own list controls, never a model/tool/tainted turn. Not retried
    (`SeamMethod::DeleteSession` is not repeatable), so a lost reply surfaces rather than silently
    re-issuing a destroy against a chat a still-streaming turn may have re-materialized; a store or
    memory failure surfaces as `TransportError::Rpc` (`Unavailable`).
  - `set_session_pinned(&self, session_id, pinned)` (ADR-0021 pinning addendum) is the overlay's
    user-driven pin toggle: the brain unions a pinned chat into `list_sessions` regardless of
    recency, lifting it above the recency window. Reachable only from the overlay's own list
    controls, never a model/tool/tainted turn. Idempotent by value, yet still not retried
    (`SeamMethod::SetSessionPinned` is not repeatable, the uniform catalog-write convention), so a
    lost reply surfaces rather than re-asserting a pinned value the user's next toggle reversed; a
    store failure surfaces as `TransportError::Rpc` (`Unavailable`).
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
- `RetryPolicy` (`retry::policy`; `Copy`, `Eq`, `Debug`) is a bounded exponential-backoff
  schedule: public fields `max_attempts` (total tries incl. the first; `0`/`1` disable retry),
  `base_delay`, `multiplier`, `max_delay` (cap). `delay(index)` =
  `min(base·multiplierⁱⁿᵈᵉˣ, max_delay)` (saturating, so no overflow escapes the cap);
  `backoff(attempt, error)` returns the wait to apply or `None` to give up (retry only while an
  attempt remains *and* the error is transient). `Default` = 3 attempts / 200 ms / ×2 / 2 s cap.
  Two helpers serve the probe budget: `worst_case_backoff()` sums every wait the schedule can
  spend before giving up (unjittered, since equal jitter only ever shortens a wait), and
  `within(budget)` returns the schedule with its attempts trimmed until that sum fits `budget`,
  leaving the delays themselves alone. One attempt always survives `within`, so a budget buys
  back patience, never the call. `RetryPolicy::ONCE` is the schedule that cannot retry (one
  attempt, no wait): what a refused method runs on, so a refusal is *executed* by the same loop
  as a permission instead of by a second code path no test can enter.
- `is_transient(&TransportError) -> bool` is the retryable classifier: `Connection` and
  `Rpc{code=="Unavailable"}` are transient; every other `Rpc` status and `Protocol` are not.
  It is a **necessary** condition for a retry, never a sufficient one: a status says the brain
  could not serve the call, never that the brain did not already run it.
- `SeamMethod` (`retry::plan`; `Copy`, `Eq`, `Debug`) names every `BrainTransport` method, and
  `repeatable()` is the safety property retry rests on: **repeating the call is observably the
  same as making it once**. True for the four reads (each a view of a store the call does not
  touch); false for `Converse` (a turn may append messages, run tools, and stream output before
  it fails, and its `decisions` stream is one-shot), for `AckReminder`, whose *effect* is
  idempotent brain-side but whose *answer* is not (an ack whose reply was lost has already
  cleared the reminder, so the repeat says `false` about a reminder this call dismissed), and
  for `RenameSession`, a plain write a repeat could use to re-apply a stale label over one the
  user has since changed, for `DeleteSession`, a **destructive** write: idempotent in
  isolation, but a silent retry could destroy a chat re-materialized by a still-streaming turn
  (a concurrent `append` between a lost reply and the retry), the last call to re-issue by machinery,
  and for `SetSessionPinned`, the case where "idempotent by value" is strongest yet still one
  attempt: setting the same pin twice is a no-op, but the uniform catalog-write convention refuses a
  retry so a lost reply never re-asserts a pinned value the user's next toggle reversed.
  `AckReminder` is the case that shows repeatability is two tests, not one: no duplicated
  effect **and** no changed answer. The match is exhaustive, so a new variant does not compile
  until it is classified.
- `RetryPlan` (`retry::plan`; `Copy`, `Eq`, `Debug`) is which schedule each method runs under:
  public fields `reads` (the `RetryPolicy` for the repeatable reads) and `probe_budget` (the
  ceiling a `Health` probe's backoff is trimmed to, `DEFAULT_PROBE_BUDGET` = 1 s).
  `policy_for(method)` is the **one door every retry decision goes through**, and it answers
  `None` for a method that may not be repeated at all: the caller must then make exactly one
  attempt and surface whatever comes back, however transient it looks. `From<RetryPolicy>`
  reads a bare schedule as a plan governing the reads with the default budget, so a caller
  with no opinion about the probe keeps passing one policy. The probe is split out because the
  connection indicator renders its answer, so patience there is time the dot spends claiming a
  state the seam has stopped proving; the default budget does not bind the default schedule
  (600 ms worst case), so it changes nothing until the read knobs are turned up.
- `retry_with(policy, sleeper, randomness, call)` is the bounded-retry loop over any fallible
  async factory (ADR-0024 addendum): re-issues `call()` each attempt, sleeping the jittered
  delay while `backoff` says so. It is the schedule **executor**, not the gate: it takes the
  caller's word that repeating `call` is safe. Public so patience composes around a
  non-transport factory, which the shell uses to wrap its eager `converse` dial (safe: the
  non-idempotent turn has not begun until the dial succeeds, and a dial is not a seam method,
  so it has no entry in the plan).
- `RetryingTransport<T: BrainTransport, S: Sleeper, R: Randomness = FullDelay>` *is* a
  `BrainTransport`: wraps an inner transport and routes every unary call through the plan's
  verdict for that `SeamMethod`, running `retry_with` on the resolved schedule when the method
  is repeatable and on `RetryPolicy::ONCE` when the plan refuses it, so a refused call makes
  **exactly one attempt** and takes no path a permitted one does not. So
  `ack_reminder` is unretried by the gate rather than by bypassing it (ADR-0025), and no error
  code, however transient, can promote a call with an effect into two of them. `converse` is
  forwarded as the stream it is, the one method that cannot reach the gate at runtime (a
  stream is not a future the loop could re-issue); it is classified all the same so the port's
  methods are covered exhaustively (ADR-0024 decision 2). `new(inner, sleeper, plan)` (no
  jitter, the v1 default) or `with_randomness(inner, sleeper, randomness, plan)` (jittered);
  both take `impl Into<RetryPlan>`, so a bare `RetryPolicy` still works.

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
  since `health` is retried, so `Down` means the whole backoff budget failed to reach the
  brain. That budget is bounded on purpose (`RetryPlan::probe_budget`): patience past the
  point where the answer still matters is the indicator showing a state the seam stopped
  proving, so the probe's schedule is trimmed to fit while the reads keep theirs.

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
The screen-capture port (`os::screen` + `os::screen_image`, ADR-0029) is the third OS
capability the brain drives, and the first whose return value is a payload. Unlike the other
two, the port carries **no policy**: it hands back raw pixels and the pure core decides what
crosses the seam.

- `ScreenCapture` is the backend port: `capture(&self, &CaptureRequest) -> Result<RawFrame,
  CaptureError>`, `Send + Sync` and synchronous for the same reasons as `AudioControl`.
- `RawFrame::new(width, height, pixels) -> Result<RawFrame, CaptureError>` is BGRA straight
  from the OS, four bytes per pixel, top-down. It rejects a zero dimension or a buffer that is
  not `width * height * 4` bytes. The fourth byte is deliberately unspecified (GDI leaves it
  undefined), and the encoder drops it.
- `CaptureRequest::bounded(max_edge, max_bytes)` resolves both proto3 hints: a zero edge
  becomes `DEFAULT_MAX_EDGE` (1600) and a zero ceiling becomes `MAX_CAPTURE_BYTES` (6 MiB,
  `6 * 1024 * 1024`); an edge above `MAX_EDGE_CEILING` (4096) and a ceiling above
  `MAX_CAPTURE_BYTES` are clamped down. A caller can therefore only tighten this seam's
  bounds, never loosen them. `CaptureRequest::new(max_edge)` is the same with the seam's own
  ceiling.
- `Capture::from_bgra(&RawFrame, &CaptureRequest) -> Result<Capture, CaptureError>` is the
  whole policy: downscale so the long edge is at most `max_edge`, PNG-encode, and while the
  result is over `max_bytes` halve the edge **that was actually reached** and retry, up to
  `MAX_SHRINK_ATTEMPTS` (2) times, then answer `CaptureError::TooLarge(bytes)`. Verifying
  after encoding is the only honest order: a flat desktop is kilobytes at 1600x900 and a
  photograph is megabytes. A `Capture` exposes `data`, `mime_type` (always `CAPTURE_MIME`,
  `image/png`), `width`/`height` after the downscale, and `source_width`/`source_height`
  before it.
- `encode_png(width, height, rgb) -> Result<Vec<u8>, CaptureError>` is the encoder, public so
  its two rejects (a zero dimension, a buffer that is not `width * height * 3` bytes) can be
  provoked by a caller. The downscaler is a box filter with a separate identity arm, so a
  screen already inside the bound crosses pixel for pixel; averaging rather than dropping
  pixels is what keeps thin strokes, which is to say text, legible after a shrink.
- `CaptureError` (thiserror, `Clone`) is `NoDisplay(String)`, `Disabled`, `Backend(String)`,
  `TooLarge(usize)`. `DeniedScreenCapture` is the unit backend that always answers `Disabled`;
  it is real gated code on every platform rather than a stub, because a host that switched
  capture off has to keep answering "no" under test.
- `CAPTURE_RECEIPT_TITLE` / `CAPTURE_RECEIPT_BODY` / `CAPTURE_RECEIPT_ID` are the fixed,
  body-owned strings of the notification a successful capture shows. They live here, beside
  `UNTRUSTED_ATTRIBUTION`, for the same reason: the notice that tells the user their screen
  was read may never be built from anything the brain sent.

**Invariant (the byte ceiling).** `MAX_CAPTURE_BYTES` and the brain's
`CORTEX_BODY_MAX_IMAGE_BYTES` are the same number, 6 MiB. Nothing mechanical couples the two
constants across the language boundary; each is pinned to the literal `6291456` by a test in
its own toolchain, and the wire's `max_bytes` hint is what lets the brain hold the body to its
own budget rather than to a duplicated constant.

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
