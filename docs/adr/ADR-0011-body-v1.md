# ADR-0011: Body v1 with hotkey → overlay → chat over the first OS-backend seam

- **Status:** Accepted (Slice 8)
- **Date:** 2026-07-01

## Context

Slice 8 is the first host-native **body** slice: a Tauri app that summons an overlay on a
global hotkey, sends the typed prompt to the brain over `Converse`, and renders the streamed
reply. It is where two ROADMAP "gate proven" items land: the **first `cfg`-gated OS backend**
and the **stub coverage escape-hatch policy**, so the decisions below are mostly about *where
logic lives* and *what the CI gate can and cannot see*, not about the feature itself.

The ground is already laid. `body_core` has the pure `HotkeyChord` (parse/validate/format,
Slice 1) and the `BrainTransport` port with `health` only; `body_rpc`'s `BrainSeamClient`
implements `health`, and the generated `Converse` bidi stream is committed but unused. The
brain already serves `Converse` end to end (the `body-rpc` live test drives it: one
`ClientEvent{session_id, user_turn}`, collect `TextDelta`s until `TurnComplete`).

The tension is the gate. CI is **Linux and GPU-less**, and `check-body` demands **100%
line+region+branch across the whole body workspace**. A Tauri app is a GUI with a webview and
a real OS event loop, and none of it is instrumentable to 100% headless on Linux. ROADMAP
assumption 4 anticipated exactly this: *app wiring stays thin and logic lives in
`body/crates/core`; if Tauri glue resists instrumentation, that glue gets an ADR'd,
narrowly-scoped exclusion.* This ADR is that exclusion, drawn as narrowly as possible.

## Decision

1. **The overlay talks to the brain one turn per `Converse` call, never over a long-lived bidi
   stream.** The port grows `converse(session_id, text) -> Stream<Result<TurnEvent,
   TransportError>>`. Session continuity is **already external** (the one hard rule: the brain
   persists session state in Redis behind `SessionStore`), so each overlay prompt is a *fresh*
   `Converse` sharing the same `session_id`; the brain rehydrates from the store. This keeps the
   port a plain request→stream shape (no client-side event multiplexing to model or test),
   matches the brain's existing single-turn `Converse` handling (the live test already drives
   exactly this), and defers both multi-turn-within-one-stream and the explicit proto `Cancel`
   event. **Cancellation is dropping the returned stream**, which aborts the RPC and the brain
   sees the client half-close. Images (`UserTurn.images`) are deferred to Slice 10 (vision);
   v1 sends text only, so the port takes `&str`, not a `UserTurn` value, until then.

2. **`TurnEvent` is a typed core mirror of the proto `ServerEvent`; the stream unifies error
   handling.** In `body_core`: `TurnEvent = Delta(String) | ToolActivity{tool_name, summary} |
   Status{state, detail} | Complete{turn_id} | Failed{code, message}`. The stream item is
   `Result<TurnEvent, TransportError>`, split by origin exactly as `health` is:
   - a brain-reported `SeamError` mid-turn → `Ok(TurnEvent::Failed{..})` (the connection is
     fine; *this turn* failed);
   - unreachable brain / non-OK gRPC status / a malformed or truncated stream →
     `Err(TransportError)`. `TransportError` gains one variant, **`Protocol(String)`**, for wire
     data the adapter cannot interpret (an empty `ServerEvent` oneof, or a stream that ends
     before `TurnComplete`). `health` never emits it, `converse` can, and both cases are
     coverable against the in-process fake.
   The overlay renders `Failed` and `Err` differently (turn error vs. connectivity), but iterates
   one stream either way.

3. **The `Hotkey` port is the first `cfg`-gated OS backend; Windows is real, macOS/Linux are
   `unimplemented!()` stubs.** The **port** (a Rust trait) and a pure `HotkeyChord`→accelerator
   conversion live in `body_core` (fully tested, no I/O). The backends live in new per-platform
   crates `os_windows` / `os_linux` / `os_macos` (the repo-map layout, where each will accrete this
   platform's impls of the other OS traits in Slices 9-10), each `#[cfg(target_os = …)]`. Only
   the target-matching crate compiles: on **Linux CI** that is `os_linux`, a pure stub whose
   `unimplemented!()` bodies are the **coverage escape hatch** (`#[cfg_attr(coverage,
   coverage(off))]` with an inline reason). This is the policy the slice exists to prove.
   `os_windows` (real, `cfg(windows)`) and `os_macos` (stub, `cfg(macos)`) compile to nothing on
   Linux, so the gate never measures them. The Windows backend makes real OS calls → it is a thin
   adapter, **host/integration-validated, never in CI** (gate 3): the coverage gate is a
   Linux-CI gate, and Windows-specific code is checked by building and running on the host, the
   same contract the brain's real adapters (llama.cpp, pgvector) already live under.

4. **The Windows `Hotkey` backend wraps the maintained `global-hotkey` crate, keeping
   `unsafe_code = forbid`.** Raw Win32 `RegisterHotKey` + a message pump would need `unsafe`
   (an ADR cost, and it fights the workspace `forbid`); `global-hotkey` encapsulates that and
   delivers activations on a receiver channel, cfg-gated to Windows. The app forwards an
   activation to "show the overlay." The port is what matters: **if wiring `global-hotkey`'s
   event delivery into Tauri's `tao` event loop proves awkward on the host, the fallback is
   Tauri's official `global-shortcut` plugin behind the same unchanged `Hotkey` port**. The
   seam absorbs the swap. This is the flagged risk (below).

5. **The Tauri app is a host-native shell *outside* the gated workspace.** `body/app` is its
   own Cargo project (its `src-tauri` crate is its own workspace root, path-depending on
   `../../crates/{core,rpc}` and `os_windows`); `body/Cargo.toml` `exclude`s it. So `just check`
   (which runs `cd body && cargo … --workspace`) **never builds Tauri, never needs
   webkit/node in CI**, and the coverage gate never sees the app. The app is built and run on
   the host and validated there, exactly like the integration suites. Its Rust is deliberately
   thin wiring (tray, hidden window, `#[command]` handlers, forwarding the `TurnEvent` stream to
   the webview as Tauri events); every branchy decision it would otherwise hold, namely
   accelerator conversion, event mapping, the transport, is pushed into `body_core`/`body_rpc`,
   which stay 100% gated. This is assumption 4's exclusion, scoped to the app crate alone.

6. **The overlay frontend is React + Vite** (the user's pick), a Vite project under `body/app/`
   built to static assets Tauri serves: a prompt input plus a streaming-reply pane that
   subscribes to the Tauri events the Rust side emits per `TurnEvent`. The frontend is **not
   gated** (the gates scan `.py`/`.rs`); its node toolchain is a host-only build concern and
   never enters CI. React was chosen over vanilla/Svelte for room to grow (settings, history,
   tool-activity panes) despite the heavier footprint.

## Consequences

Increments (each small, green, documented), split CI-gated / host-validated per our rhythm.
I author all of it; "host" marks what only the host Windows machine can *exercise*:

1. **(CI) `Converse` on the port** covers `BrainTransport::converse` returning the `TurnEvent`
   stream, the `body_rpc` adapter translating to/from the generated bidi `Converse` (send one
   `ClientEvent`, half-close, map each `ServerEvent`), and contract tests where the in-process
   `FakeBrain` *scripts* `Converse` over loopback: a normal streamed turn, a `SeamError`
   (→`Failed`), an empty-oneof and an early-close (→`Protocol`), and a brain-death mid-stream
   (→`Connection`). `TransportError::Protocol` added. 100% under `just check`.
2. **(CI) The `Hotkey` seam** covers the `Hotkey` port trait + `HotkeyChord`→accelerator conversion
   in `body_core` (tested), and the `os_linux`/`os_macos` stub crates with `unimplemented!()` +
   `coverage(off)` + reasons. Proves the `cfg`-gated OS backend and the stub escape hatch. 100%
   under `just check`.
3. **(host) The `os_windows` `Hotkey` backend** is `global-hotkey`-backed registration behind the
   port; a thin adapter, compiled and validated on Windows.
4. **(host) The Tauri app** is `body/app`: tray + hidden window, the React overlay, wiring hotkey
   activation → show → `converse` → render the streamed reply, hide on escape/blur. Configurable
   hotkey (`HotkeyChord`, default `ctrl+alt+space`). Excluded from the CI gate (decision 5).
   End-to-end host validation: press the chord, type, watch the real brain stream back.
5. **(docs) DoD** covers module docs (`body-os`, `body-app`), the runbook
   `docs/runbooks/body-overlay.md` (host bring-up + validation), and ROADMAP/AGENTS updates.

Config gains, at the app only: `CORTEX_BRAIN_ADDR` (already the `body_rpc` default,
`http://127.0.0.1:50051`) and `CORTEX_HOTKEY` (the chord, default `ctrl+alt+space`).

## Risks

- **`global-hotkey` ↔ Tauri event-loop integration (the flagged assumption).** Global-shortcut
  delivery must reach the async side that shows the overlay. Mitigated by decision 4's fallback
  (Tauri's `global-shortcut` plugin behind the same port) and by the port isolating the app from
  the choice; validated on the host, not CI.
- **Coverage creep into the ungated app.** The exclusion is only safe while the app stays thin.
  Guard: branchy logic goes to `body_core`/`body_rpc` (gated); the app holds wiring only, and
  code review watches the app crate's size.
- **Windows backend not CI-checked (fmt/clippy/build).** A cross-platform reality, since the Windows
  path is checked by building on the host. Same posture as the brain's host-only adapters.
- **One-turn `Converse` vs. future needs.** Follow-ups already work (fresh call, same
  `session_id`); a long-lived bidi stream + the explicit `Cancel` event become worthwhile only
  if a turn must be interrupted or client events must interleave, a later refinement behind the
  same port (drop-to-cancel covers v1).
- **Hotkey conflicts on the host.** `ctrl+alt+space` may collide with other software; it is
  configurable from day one (`CORTEX_HOTKEY`), and registration failure surfaces to the overlay.

## Addendum (2026-07-01): the overlay frontend is gated and browser-validated (revises decision 6)

Decision 6 said the React frontend is "not gated." **That is reversed at the user's
direction: every overlay component carries 100% test coverage, gated in `just check`, and the
overlay is validated in a real browser here. Windows is needed only for the Tauri shell.**

- **Gate.** A `frontend/` (Vite + React + TypeScript) project under `body/app/`, tested with
  **Vitest + @testing-library/react**, coverage via **v8** at **100% line+branch** thresholds,
  run by a new `just check-overlay` recipe folded into `just check` (with its own
  path-filtered CI job, ADR-0006). The frontend joins the Rust/Python trees under the same bar.
- **Testability seam.** Components never call Tauri directly. A thin typed **bridge**, the
  frontend's port (`converse(sessionId, text) → event stream`, `onActivate`, `hide`, connection
  status), is what components depend on. The real implementation wraps Tauri's
  `invoke`/`event.listen`; a fake drives tests and browser dev. Only that one real-bridge module
  is excluded from coverage (the Tauri glue, the frontend analog of the Rust host adapters);
  everything else is fully covered.
- **Browser validation (no Windows).** Because components depend on the bridge, not Tauri, the
  overlay runs in a plain browser against the fake bridge (or a real brain via a dev proxy):
  `vite dev` + the browser tooling validate the prompt → stream → render UX locally. Only the
  Tauri shell (tray, hidden window, global hotkey, real gRPC transport) still needs the host.

The overlay is thus fully CI-gated and locally verifiable; the host-only surface shrinks to the
Rust Tauri shell + `os_windows` (still authored by me, validated on the host Windows machine).

The overlay's **look, feel, and interaction model**, the bubbly/alive/colorful identity, design
tokens, the interaction state machine (including the user's *dismiss-while-processing* → corner
orb → response-preview behavior), message history, keyboard shortcuts, and chats-as-sessions are
specified in [docs/design/overlay-ux.md](../design/overlay-ux.md), the design source of truth that
overlay components are built against.

## Addendum (2026-07-03): Slice 8 close-out with a deferral record + two corrections

- **Deferred overlay polish (the Slice 8 conscious deferral), recorded at its origin ADR.**
  A proper transparent window + click-through margins (done together), the OS-window morph
  to a real screen corner, hide-on-blur, and a tighter CSP (null in v1) shipped deferred
  with the slice. Details live in [overlay-ux.md §4](../design/overlay-ux.md) and the
  [body-overlay runbook](../runbooks/body-overlay.md); collected in the ROADMAP "Deferred
  refinements & later work" ledger (Slice 8 block). Until this note the deferral was
  written down only outside the two canonical locations (flagged by the 2026-07-02 audit).
- **Correction (layout).** The 2026-07-01 addendum described "a `frontend/` project under
  `body/app/`"; the shipped Vite project lives directly at `body/app/` (`src/`,
  `package.json` at the root, with no `frontend/` subdirectory).
- **Correction (bridge sketch).** The same addendum sketched the bridge port as
  `converse(...)` + `onActivate` + `hide` + connection status. The shipped `BrainBridge`
  ([body-app.md](../modules/body-app.md)) is **`converse` only**: activation arrives as the
  `cortex:activate` DOM event, there is no `hide` method, and no connection-status surface
  exists in v1 (the design doc's connection dot is unshipped target design).

## Addendum (2026-07-03, later): user-directed design pass on the overlay chrome

Maintainer review of the running overlay reshaped the resting chrome. The design source of truth updated
with it ([overlay-ux.md](../design/overlay-ux.md) §2-§4): the corner orb became the **living
rings** (two wavy gradient bands; a pure `wavyRingPath` helper + a shared `RingMark` component,
fully gated), the always-green header dot was **removed** (it was decoration; a real indicator
waits on a health signal over the bridge, per the ROADMAP ledger), the theme toggle became a
**sun↔crescent SVG morph** (CSS-transitioned geometry, no glyph swap), and the hint strip
centered. A same-day motion refinement (maintainer review of the running rings): the mark **spins as
one** (the bands never rotate against each other, no breathing scale) while each band's **wave
depth pulses independently** (SMIL, reduced-motion aware); the palette gained the AI blues
(sky/cyan/indigo/lavender); the preview card dropped its redundant caption text (mark + reply +
drain bar only); and the panel's summon/idle-dismiss pop **from center**, with the corner travel
reserved for the orb morph (`.to-orb`, mode-driven). The same pass surfaced the browser-side
interaction gaps now recorded in the ROADMAP ledger (Slice 8 block): auto-scroll,
focus-on-summon, click-away dismiss, the stop control, tool/status chips, empty state, thinking
shimmer, shortcut sheet, composer auto-grow, and preview hover-pause.
