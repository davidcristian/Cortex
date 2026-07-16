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

A third maintainer pass finished the motion discipline: the positional **drift is gone** (it read as
a breathe anchored at the corner, and the orb's anchor now holds rock still; motion is the unified
spin + independent depth pulses + hue walk, nothing else), the band gradients were rebuilt from
the eight-hue palette (and then corrected: the palette is **one** eight-stop gradient
shared by both bands, not two four-stop arcs), the preview card slimmed to **reply + drain bar
only** (the mini mark followed the captions out), the send button's gradient now **fades in**
via an opacity overlay (a gradient background can't interpolate, so the hard swap popped), and
the chat title gained a 6px optical left margin.

## Addendum (2026-07-12): the recorded interaction gaps are closed

All nine browser-side interaction gaps from the 2026-07-03 pass landed behind the unchanged
`BrainBridge` port and reducer, CI-gated at 100% and browser-validated (light and dark, Chrome
against the demo bridge):

- The history **auto-scrolls** with the stream through a pinned-at-bottom latch: scrolling up
  holds the reader's place; returning near the bottom re-pins. The approval card scrolls into
  view the same way.
- The composer **takes focus on summon** (the panel-open rising edge) and **auto-grows** with
  its content up to the CSS ceiling, past which it scrolls internally.
- A press on the bare stage is **click-away dismiss**, the same path as Esc: mid-stream it
  morphs to the orb, idle it hides. Presses inside the panel pass through.
- The reducer's tool/status fields finally **render as slim inline chips** above the streaming
  bubble (a neutral pill with a pulsing accent dot, gone on completion), so the ADR-0020
  thinking status and any future `ToolActivity` have a visible surface.
- The empty chat greets with the **mark, "Ask me anything", and two tappable example prompts**
  (real capabilities only) that submit on tap.
- A **thinking shimmer** (three accent dots) holds the assistant bubble until the first token.
- The **`?` shortcut sheet** covers the panel, opened from the hint strip's ? button or the ?
  key outside the composer (where ? is just typing); Esc closes the sheet before it dismisses
  the panel, and `sheetOpen` lives in the reducer beside `switcherOpen`.
- The preview's **hover now pauses the fade timer itself**, not just the bar's animation: the
  hook latches hover, leaving restarts the full countdown, and the drain bar remounts in step
  so what it shows always matches the timer. The countdown-restarts-on-leave choice is noted
  in overlay-ux.md §4.

Two implementation nuances: the sheet is not frosted glass, because the panel's own
backdrop-filter bounds the backdrop root and a child's blur cannot reach the history beneath
it, so the sheet layers the panel tint over the solid ground instead; and the demo bridge
gained a short thinking pause plus a status event before streaming, so the new working
affordances are visible (and hand-verifiable) in plain browser dev.

## Addendum (2026-07-16): the connection indicator ships, derived rather than polled

The 2026-07-03 pass removed the always-green header dot because it was decoration, and the
2026-07-03 correction recorded that no connection surface existed at all: the `BrainBridge` was
`converse` only. The bridge has since grown the session reads, the reminder pull, the confirm
answer, and a resilient transport under all of them. The indicator now lands on top of that, and
the design decision worth recording is **where the signal comes from**, since the obvious answer
is the wrong one.

**Rejected: a `Health` poll on a timer.** It spends a request every interval for the entire
uptime of a tray-resident app, almost always while the overlay is hidden and nobody can see the
answer, and it is still stale between ticks, which is precisely the window that matters (the
brain dies one second after a tick and the dot stays green for the rest of the interval).

**Chosen: the freshest fact the overlay already has, plus a probe at the two moments it can be
stale.** Three sources, in order of how much they cost:

1. **The turn itself.** Every `TurnEvent` is proof the brain is serving, and every
   `TransportError` on the stream is proof it is not; both already reach the reducer. While
   anything is happening the indicator is exact and costs nothing.
2. **One probe per summon**, latched on the rising edge of visibility (the same
   `useSummonEffect` latch the reminder pull established). The dot is only visible when the
   overlay is, so that edge is when its truth starts to matter.
3. **A recovery re-check every 5 s, only while the overlay is visible *and* the link is not
   ready.** Zero requests in the steady state. This is the one thing the other two cannot do:
   nothing streams while an open panel sits idle, and a red dot that can only go green by
   dismissing and re-summoning is a worse lie than no dot. It stops the instant the brain
   answers ready. The interval is a constant, not an env knob: it is the recovery cadence of a
   supervised local process, and no operator needs a dial for it. It is also not the whole
   wait, because the probe underneath is itself patient (see below).

**Four states, because two lie and three are not quite enough.** The seam can report three
(`body_core::link::LinkState`), and the overlay adds a fourth for what it has not asked yet:

- `ready` (green): the brain answered and reports itself ready.
- `degraded` (amber): the brain **answered**, and is not serving. That covers `Health` replying
  `ready = false` (the model-swap case the field exists for), any non-OK gRPC status (a rejected
  seam token is `Unauthenticated`, a store abort is `Unavailable`), and a reply this side cannot
  read (`Protocol`). Reporting these as "cannot reach the brain" would send the user to the
  wrong machine; the brain is right there, refusing.
- `down` (red): `TransportError::Connection`, which is the only failure that means nothing
  answered.
- `unknown` (neutral): nothing has been asked yet. The v1 dot's sin was claiming a state it had
  not earned, so this one is a real state with its own colour.

**"Connecting" is a modifier, not a state.** Whether a probe is in flight is the overlay's own
fact and never the seam's, so it rides alongside (`LinkView.probing`) instead of replacing what
was last proven: the dot keeps its colour and pulses. A reconnect therefore neither flashes
green nor forgets that it was red, and the routine summon probe on an already-ready link is not
allowed to look busy at all (the steady state of a working system must not blink). The probe
also *is* the reconnect attempt, because it runs through the `RetryingTransport` decorator
(ADR-0024) and `health` is one of the retried idempotent calls: a single probe already spans the
whole backoff budget before it answers `down`.

**Shape.** `body_core::link` is pure and gated: `LinkStatus::from_health` / `from_error`
classify, and `probe_link(&transport)` awaits `BrainTransport::health` and never fails (a
failure *is* the answer, which is what lets the overlay render a state instead of an error). The
shell's `check_link` command is a lookup over that, infallible for the same reason, mapping even
a bad `CORTEX_BRAIN_ADDR` to `down` with the reason attached. The overlay grows
`BrainBridge.checkLink()`, the reducer grows `state.link`, and `components/LinkDot.tsx` renders
tone + label (a colour alone is not an explanation, so the label is the tooltip *and* the
accessible name). Themes grow an `ok`/`warn`/`bad` trio drawn from the user's own eight-hue
ring palette, deepened for the light theme; this is the second sanctioned use of colour in the
overlay after activity, and it is meaning rather than decoration.

**One thing this proves and one it does not.** A gate caught the interesting failure: chaining
the recovery re-check off each answer (a `setTimeout` re-armed when `probing` goes false) dies
silently after a single retry whenever the probe answers inside one React batch, because the
flip is never rendered and the effect's dependencies never change. It is an interval keyed on
"visible and unhealthy" for that reason, with an in-flight guard so a slow probe cannot overlap
a tick. What is *not* proven is readiness beyond liveness: the brain's `Health` returns
`ready = True` unconditionally today (`server.py`), so "answered any call" and "ready" are the
same fact, which is why a streamed turn event is allowed to set green.

**Deferred, recorded in [docs/refinements/body-overlay.md](../refinements/body-overlay.md):**
**streamed brain status**, the push half this deferral originally assumed. It stays unbuilt
because nothing produces a status the overlay cannot ask for: `Health` has no not-ready path,
and a mid-turn `StatusUpdate` already reaches the overlay on the stream. When the model manager
lands (Slice 11) and a swap can make the brain not-ready *between* turns, both halves want
revisiting together: the push channel, and the rule that any successful call means ready.

## Addendum (2026-07-16): the "not CI-checked" risk came due, and is now a recorded deferral

The Risks section above accepted that the Windows backend is not fmt/clippy/build checked in
CI, and decision 5 put the Tauri shell outside the gated workspace for the same kind of
reason. Both remain right. What neither said is that no signal reports the consequence, so
findings accumulate in the two trees until somebody happens to look. On 2026-07-16 somebody
did: five clippy warnings and three files rustfmt would rewrite, none of them a regression
from the work in flight. Two `clippy::collapsible_if` in the shell's `confirm.rs`, three
pedantic findings in `os_windows/src/audio.rs` (one `unused_self`, two
`needless_pass_by_value`), and `cargo fmt` diffs in `confirm.rs`, `converse.rs`, and
`tray.rs`, the last only an import order the 2024 style edition reversed. They were
fixed on the spot, and both trees were then verified clean from Linux: the shell against a
userspace `libdbus-1-dev` prefix with a `pkg-config` shim, `os_windows` against the real
`windows` crate on the `x86_64-pc-windows-msvc` target, which clippy can type-check without
an MSVC toolchain because it never links.

**Deferred here, recorded in [docs/refinements/repo-gates.md](../refinements/repo-gates.md):**
**folding `cargo fmt --check` and `cargo clippy` for both trees into `just check`.** The
format half is nearly free (rustfmt only parses, and it alone would have caught three of the
eight); the lint half costs a `rustup target add` plus a `windows`-crate fetch for
`os_windows`, the Linux GTK/webkit/dbus dev packages for the shell, and a cold Rust build in
CI for trees whose dependencies are otherwise never fetched. Coverage is explicitly **not**
part of it: this
ADR excludes both trees from the coverage gate on purpose, and a cross-target clippy is a
compile check rather than a run.

## Addendum (2026-07-16, later): the recorded deferral partly lands

The deferral just above landed except for one clippy residual. Reading it against the code
sharpened "fmt plus clippy for both trees" into three real gaps and one non-gap:

- **`os_windows` fmt was never a gap.** It is a `body` workspace member, and `cargo fmt --all
  --check` (already in `check-body`) formats a member regardless of `cfg`, because rustfmt
  follows the module tree syntactically and never evaluates `#[cfg(windows)]`. Injecting a fmt
  violation into `os_windows/src/audio.rs` and watching the existing step flag it confirmed it,
  which is why the eight findings included no `os_windows` fmt diff (its three were the shell).
- **Shell fmt** folded into `check-body` (`cd body/app/src-tauri && cargo fmt --check`), and
  `scripts/ci_paths.py` now classifies `body/app/src-tauri/` as **rust** rather than overlay,
  so a shell change gates the job that fmt-checks it. A fmt gate the dirtying change cannot
  trigger is not a gate (ADR-0006 addendum).
- **`os_windows` clippy** folded into `check-body` as `cargo clippy --target
  x86_64-pc-windows-msvc -p os-windows`, the CI rust job adding the target. Clippy never links,
  so no MSVC toolchain; a `needless_return` proved invisible to native `--workspace` clippy and
  caught by the windows-target clippy.
- **Shell clippy stays deferred**, recorded in
  [docs/refinements/repo-gates.md](../refinements/repo-gates.md): it needs the shell to compile
  (Linux GTK/webkit/dbus dev packages and a cold Tauri build), too heavy for every `body/`
  change, so it remains the one lint a shell change can dirty unseen. The toolchain-linked full
  build of either tree stays host-side, as the Risks section says.
