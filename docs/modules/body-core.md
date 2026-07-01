# body/crates/core (`body_core`)

**Purpose.** The body's pure core: host-side domain types and ports (and, from Slice 8,
the OS traits `ScreenCapture`/`AudioControl`/`InputControl`/`Hotkey`). No OS calls,
ever. Currently: the typed global-hotkey chord and the `BrainTransport` port to the
brain seam.

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
  summary }` | `Status { state, detail }` | `Complete { turn_id }` (terminal) |
  `Failed { code, message }` (brain-reported turn error; terminal, since the connection is fine).
- `BrainTransport` is the body's typed async client port to the brain seam
  (`Send + Sync` supertraits):
  - `health(&self)` returns `impl Future<Output = Result<SeamHealth, TransportError>> +
    Send`, so implementors just write `async fn health`.
  - `converse(&self, session_id, text)` returns `impl Stream<Item = Result<TurnEvent,
    TransportError>> + Send`, giving one turn per call (ADR-0011: session continuity is external,
    so each prompt is a fresh call sharing the `session_id`; dropping the stream cancels).
    `Ok(TurnEvent)` per brain event; `Err(TransportError)` for a transport/protocol failure.
    v1 sends text only. Images (vision) arrive in Slice 10.
  The gRPC adapter is `body/crates/rpc` (`docs/modules/body-rpc.md`); fakes implement
  the same trait for tests.

**Invariants.**
- Pure: no OS/network calls; `unsafe_code = "forbid"`; no `unwrap`/`expect` outside
  tests (workspace lints).
- An existing `HotkeyChord` is always canonical. Invalid states are unrepresentable.
- 100% line+region+branch covered by behavior tests in `tests/` (never inline test
  modules; the 300-line cap counts source files, per ADR-0002).

**Dependencies.** `thiserror` and `futures-core` (the `Stream` trait for the `converse`
return type). Both are trait/type-only, no runtime. Dev-only: `tokio` and `tokio-stream`
(to await the `health` and drain the `converse` contract streams).
