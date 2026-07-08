# body/crates/core (`body_core`)

**Purpose.** The body's pure core: host-side domain types and ports, including the
OS-capability ports in `os` (`Hotkey` from Slice 8; `AudioControl`/`ScreenCapture`/
`InputControl` join in Slices 9-10). No OS calls, ever. Per-platform backends live in
the `os_windows`/`os_linux`/`os_macos` crates (`docs/modules/body-os.md`). Currently: the
typed global-hotkey chord, the `BrainTransport` port to the brain seam (`health` +
streaming `converse`), and the `Hotkey` port with the `Accelerator` chord→code mapping.

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
  **non-terminal**, answered via the `decisions` stream) | `Complete { turn_id }` (terminal) |
  `Failed { code, message }` (brain-reported turn error; terminal, since the connection is fine).
- `ConfirmDecision { confirm_id, approved }` is the user's answer to a `ConfirmRequest`
  (`Clone`, `Eq`, `Debug`; ADR-0022): fed into `converse`'s `decisions` stream, delivered
  to the brain as a `ConfirmResponse` on the open `Converse` stream.
- `SessionSummary` / `SessionMessage` are typed core mirrors of the proto session-read messages
  (`Clone`, `Eq`, `Debug`; ADR-0021). `SessionSummary { session_id, title, preview,
  last_activity_unix_ms }` is one recent chat as the switcher shows it (title/preview already
  derived); `SessionMessage { role, text, turn_id, at_unix_ms }` is one persisted message
  (`role` is `"user"`/`"assistant"`).
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
  The gRPC adapter is `body/crates/rpc` (`docs/modules/body-rpc.md`); fakes implement
  the same trait for tests.

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

**Invariants.**
- Pure: no OS/network calls; `unsafe_code = "forbid"`; no `unwrap`/`expect` outside
  tests (workspace lints).
- An existing `HotkeyChord` is always canonical. Invalid states are unrepresentable.
- 100% line+region+branch covered by behavior tests in `tests/` (never inline test
  modules; the 300-line cap counts source files, per ADR-0002).

**Dependencies.** `thiserror` and `futures-core` (the `Stream` trait for the `converse`
return type). Both are trait/type-only, no runtime. Dev-only: `tokio` and `tokio-stream`
(to await the `health` and drain the `converse` contract streams).
