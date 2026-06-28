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
  e.g. `Internal`, `Unimplemented`).
- `BrainTransport` is the body's typed async client port to the brain seam
  (`Send + Sync` supertraits): `health(&self)` returns
  `impl Future<Output = Result<SeamHealth, TransportError>> + Send`, so futures can be
  awaited from multi-threaded runtimes; implementors just write `async fn health`.
  The gRPC adapter is `body/crates/rpc` (`docs/modules/body-rpc.md`); fakes implement
  the same trait for tests.

**Invariants.**
- Pure: no OS/network calls; `unsafe_code = "forbid"`; no `unwrap`/`expect` outside
  tests (workspace lints).
- An existing `HotkeyChord` is always canonical. Invalid states are unrepresentable.
- 100% line+region+branch covered by behavior tests in `tests/` (never inline test
  modules; the 300-line cap counts source files, per ADR-0002).

**Dependencies.** `thiserror` only (`tokio` as a dev-dependency, to await the
`BrainTransport` contract tests).
