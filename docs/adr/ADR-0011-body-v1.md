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
fully gated; **superseded 2026-07-19 by the bubble mark**, [ADR-0031](ADR-0031-bubble-mark.md),
which kept this palette and replaced the silhouette and the motion), the always-green header dot was **removed** (it was decoration; a real indicator
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
  **Superseded by [ADR-0034](ADR-0034-panel-views.md)** (the sheet became a view of the panel) **and
  [ADR-0035](ADR-0035-console-and-motion.md)** (that view became the shortcuts tab of one console it
  shares with the appearance choices). Both openers and the `?` key survive unchanged; what does not
  is the covering layer, `sheetOpen` (now one `consoleTab` field, so appearance and the list cannot
  both be up), and the two-press Esc, which leaves the console in a single press from either tab.
- The preview's **hover now pauses the fade timer itself**, not just the bar's animation: the
  hook latches hover, leaving restarts the full countdown, and the drain bar remounts in step
  so what it shows always matches the timer. The countdown-restarts-on-leave choice is noted
  in overlay-ux.md §4.

Two implementation nuances: the sheet is not frosted glass, because the panel's own
backdrop-filter bounds the backdrop root and a child's blur cannot reach the history beneath
it, so the sheet layers the panel tint over the solid ground instead; and the demo bridge
gained a short thinking pause plus a status event before streaming, so the new working
affordances are visible (and hand-verifiable) in plain browser dev. The first nuance expired with
the sheet: a view is the panel's own content rather than a layer over it, so there is no second
surface left to decide the glass question for.

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

**Deferred, recorded in [docs/refinements/index.md#body-overlay](../refinements/index.md#body-overlay):**
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

**Deferred here, recorded in [docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates):**
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
  [docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates): it needs the shell to compile
  (Linux GTK/webkit/dbus dev packages and a cold Tauri build), too heavy for every `body/`
  change, so it remains the one lint a shell change can dirty unseen. The toolchain-linked full
  build of either tree stays host-side, as the Risks section says.

## Addendum (2026-07-16, later still): multi-turn-within-one-stream + proto `Cancel`, read against the code and sharpened

Decision 1 deferred both multi-turn-within-one-stream and the explicit proto `Cancel`, with
drop-to-cancel covering v1. Reading that deferral against the code today shows the proto and the
whole server half are already built and proven; what remains is body-side only, its two parts are
coupled, and its value trigger is Slice 11, so it stays deferred and moves to fix-when-it-bites
(recorded in [docs/refinements/index.md#body-overlay](../refinements/index.md#body-overlay)).

- **The proto `Cancel` exists** (`proto/body.proto` `Cancel cancel = 3`, in the seam since the
  first proto commit) and round-trips (`test_client_event_oneof_carries_a_cancel`).
- **The server carries multiple turns per stream and handles `Cancel` end to end.** A `UserTurn`
  arriving mid-turn is queued and starts when the running turn finishes; a `Cancel` stops the
  in-flight turn, drops the queue, keeps the stream open, and drops the partial reply. Pinned by
  `test_cancel_behind_a_queued_turn_stops_current_and_drops_queued` and
  `test_cancel_mid_confirm_drops_the_turn_and_the_stream_stays_open`.
- **The lease-cancellation crux is clean and now has a dedicated proof.** The GPU lease is a
  non-reentrant `asyncio.Lock` held across the streaming block; a `CancelledError` mid-inference
  propagates out through `async with manager.acquire(...)` and frees it before the next turn
  leases. `test_cancelling_mid_stream_frees_the_model_lease` suspends a turn with the lease held,
  cancels it, and asserts a fresh acquire returns at once; releasing the lock outside a `finally`
  reddens it. No partial reply is persisted on cancel (the engine's generator is closed).
- **What remains is body-side and coupled.** The `BrainTransport::converse` port is one turn per
  call, and the overlay opens a fresh `Converse` per submit. A client-sent `Cancel` cannot cleanly
  precede body multi-turn: on the one-turn-per-call body, `Cancel` then a half-close ends the body
  stream with no terminal event, which the adapter maps to `TransportError::Protocol`. So client
  `Cancel` needs either multi-turn-within-one-stream (the case it earns its keep, carrying the
  per-turn-confirm-keying knock-on decision 1's follow-up already names) or a new terminal
  cancelled-ack.
- **Today's Stop is UI-only in the Tauri embedding, and that sets the trigger.** The overlay's Stop
  denies a pending confirm and mutes the JS sink, but does not half-close or abort the RPC, so the
  brain streams the turn to completion and persists the full reply while the overlay may show a
  truncated one. Drop-to-cancel is "stop showing me", not "abort the compute". A real abort (release
  the lease, drop the partial, keep the store consistent) earns its keep only when Slice 11's model
  swap makes mid-turn compute expensive and evictable, the same trigger the reconnect and streamed-
  brain-status deferrals wait on. The clean v1 fix for one-turn-per-call is a real drop-to-cancel:
  make the Tauri command abort its RPC on Stop (a body-local signal, no proto change), which the
  brain already tears down cleanly. Both that and the multi-turn+`Cancel` build live entirely in the
  ungated, host-validated Tauri shell + overlay glue, so neither is a gated slice today.

## Addendum (2026-07-16, later still): the shell-clippy residual is deferred to fix-when-it-bites

The "recorded deferral partly lands" addendum above left one residual: `cargo clippy` for the
Tauri shell in CI. Reading it against what CI actually installs settled it against wiring, and it
moves to fix-when-it-bites (recorded in
[docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates)).

- **What the rust CI job installs today.** Nothing at the system level. `.github/workflows/ci.yml`
  gives the rust job rust nightly plus stable (rustfmt, clippy, the `x86_64-pc-windows-msvc`
  target), `cargo-llvm-cov`, `just`, `uv`, and `rust-cache`, and no more; the overlay job is node
  only ("npm + jsdom only"). Nothing in CI provisions the GTK/webkit/dbus stack.
- **So shell clippy is not a marginal add; it is a new class of CI provisioning.** The shell
  depends on `tauri` 2, whose Linux `-sys` build scripts need the webkit dev stack via pkg-config.
  `libwebkit2gtk-4.1-dev` has a 630-package recursive apt closure (measured with `apt-cache
  depends --recurse`), an uncacheable `apt-get install` re-run every job on top of a cold compile
  of the roughly 150-crate Tauri Rust graph (`wry`, `webkit2gtk-sys`, gtk-rs, `tauri`). That cost
  lands on `check-body`, which every `body/` change runs, to catch the occasional style lint on
  881 lines of thin, host-validated wiring. Disproportionate at personal, local-first scale.
- **The gate would be real, and the shell is currently clean.** With pkg-config and the webkit-dev
  stack absent on the dev host (and no sudo), a permissive pkg-config shim satisfies the `-sys`
  build scripts, since clippy never links and consumes only the discarded link flags. Under it
  `cargo clippy --all-targets -- -D warnings` on the shell exits 0, and a planted `useless_format`
  makes the exact command exit 101. So this is a cost decline, not a can't-fail gate.
- **Trigger.** CI gaining the Tauri desktop stack for another reason (a future CI-side Tauri build
  or smoke job) drops the marginal cost to near zero and lets shell clippy ride along; failing
  that, shell findings outpacing the user's local checks, or the shell outgrowing the thin wiring
  the coverage-creep guard watches. Until then the maintainer catches shell clippy on the validation
  host, where the two `collapsible_if` were fixed. The classifier is unchanged: `body/app/src-tauri/`
  stays carved to rust (ADR-0006), justified by the shell fmt gate it already feeds.

## Addendum (2026-07-19): this ADR's Host-Windows line, stated once and in one place

The body is the ADR with the most host-side surface, and until now that surface was scattered
across a slice status, a runbook's notes, a refinements entry, and a risk paragraph. It is now
collected in [docs/host/](../host/index.md), one doc per sitting, wording kept verbatim. Nothing
about the work changed; what changed is that it can be found.

**Host-Windows (host-only) for this ADR**, adopting the explicit-line convention ADR-0028 already
uses (which is worth keeping precisely because an ADR that names none makes a missing one visible):

- The `os_windows` `global-hotkey` registration, the tray, and window show/hide.
- The real `converse` command streaming a live brain turn to the webview.
- The `confirm_response` command carrying an approval back into an open turn (ADR-0022).
- The `list_sessions` / `session_messages` commands (ADR-0021).
- The `check_link` command behind the connection indicator. The classification itself is pure and
  gated in `body_core::link` and is checked against a real brain by the `body-rpc` live suite, so
  what Windows adds is the IPC hop and nothing else. That is why this one had lived only in a
  runbook paragraph: it is a thin thing to check, and a thin thing to lose.
- The **overlay polish pass**, which is the one item in that whole directory that is authoring
  rather than validation: a transparent window with click-through margins (done together, since a
  first attempt bled through the panel and left a border), the morph to a real screen corner,
  hide-on-blur, and a tighter CSP. Its design source stays at
  [docs/design/overlay-ux.md](../design/overlay-ux.md) section 4.
- The **toolchain-linked full build** of `os_windows` and the Tauri shell, which is a standing
  per-change obligation rather than a one-time check: CI format-checks both trees and cross-target
  clippy type-checks `os_windows` without linking, and only a Windows build links them. That is
  the "build" third of the risk this ADR named, and it stays host-side by construction.

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-07-19, later): the user list above, mapped to the check that closes each

The list is a records fix only if it can be read in both directions. It could not: an audit that
walked from these lines into [docs/host/](../host/index.md) found the first two named nothing
there. Both are now check 0 of [docs/host/index.md#windows-desktop](../host/index.md#windows-desktop), which
is the sitting's own bring-up written down as a check, numbered 0 so the existing items keep the
numbers other ADRs cite. The mapping, line for line:

- Hotkey registration, the tray, window show/hide → **check 0**.
- The real `converse` command streaming to the webview → **check 0**.
- `confirm_response` into an open turn → check 3.
- `list_sessions` / `session_messages` → check 4.
- `check_link` behind the connection indicator → check 6.
- The overlay polish pass → [docs/host/index.md#overlay-polish](../host/index.md#overlay-polish).
- The toolchain-linked full build → the standing item at the end of the same doc.

Why the two that went missing were the obvious ones is worth keeping: they are what you do before
the checks rather than a check, so nobody wrote them down. Nothing else in the repo proves a global
hotkey registers on a live desktop, so "obvious" was never "covered".

No code changed here; this is a records correction at the origin ADR.


## Addendum (2026-07-19): a summon that arrives early is no longer lost

The overlay is summoned by a `cortex:activate` DOM event: the Tauri shell re-dispatches the host's
global-hotkey event, and the browser build self-summons on load so `vite dev` shows the design
immediately. Both were plain dispatches, delivered only to listeners that already existed, and the
app attaches its listener in a **passive** effect, which React flushes after paint rather than
before it. The self-summon therefore lost the race every time: instrumented in a browser, the
event fired at t=102ms and the listener attached at t=104ms, so `npm run dev` came up to an empty
stage and the overlay could only be opened by dispatching the event by hand. The original code
deferred the dispatch by two animation frames on the belief that effects flush before paint; that
is true of layout effects only, so the deferral never helped.

The same race drops a real hotkey press that lands while the webview is still mounting, which is
exactly the cold-start case where the first press is the one the user cares about.

An activation is now a **fact rather than a moment** (`overlay/activation.ts`): `requestActivation`
records it and then announces it, and the app takes any outstanding request when its listener
attaches. Both paths consume it, so a remount cannot replay a summon that has already been
answered. Proven the way the bug was found, by loading the dev server with no scripted input and
reading the panel's class: `panel open` at HEAD, `panel` (opacity 0) at the commit before the fix.

## Addendum (2026-07-20): two pieces of the overlay's chrome moved, and both are recorded elsewhere

Maintainer review of the running overlay reached two things this ADR is the origin of, and both are
written up as decisions of [ADR-0035](ADR-0035-console-and-motion.md) rather than here, because
they landed alongside that day's motion work and share its measurements.

- **Scrollbars became reserved chrome** ([ADR-0035](ADR-0035-console-and-motion.md) decision 22).
  The complaint was that they "look absolutely terrible and disturb the look of the application and
  also push elements around". Both halves were true: only `.history` was styled at all and its
  thumb took real layout width. All seven scroll regions now wear one 6px rail and reserve it
  permanently, and the horizontal axis is closed off rather than reserved.
- **The connection indicator no longer leads the header row**
  ([ADR-0035](ADR-0035-console-and-motion.md) decision 23). The dot and the capture ring moved
  together to the head of the button cluster, and the title took the row with a 31px inset off the
  panel's edge. That supersedes this ADR's 2026-07-03 line about the title's 6px margin: neither
  indicator keeps an optical margin now, both riding the header's own 10px gap.

## Addendum (2026-08-03): the line cap covers the overlay's TypeScript (closes ADR-0001 open question 6)

This ADR's 2026-07-01 addendum brought the overlay under the coverage gate and said so;
[ADR-0001](ADR-0001-architecture.md) open question 6 had named **two** gates that applied to
`.py`/`.rs` only, coverage and the 300-line cap, and only the first was reversed. The second was
left as written, so `scripts/linecap.py` kept `SOURCE_SUFFIXES = {".py", ".rs"}` and AGENTS.md gate 1
kept saying the cap covers "`.py` and `.rs`" while decision 6 above it had been overturned. The
overlay grew from a prompt box to 65 non-test TypeScript modules under a rule nothing measured.

**What that let through, measured on 2026-08-03 rather than assumed.** Two entries in
[docs/refinements/index.md#body-overlay](../refinements/index.md#body-overlay) had tracked overlay files as cap
violations by eye, and eye-tracking failed exactly as an ungated rule does. The closed entry and the
open one both call `bridge/demoBridge.ts` at 326 "the last overlay source above 300"; at the moment
that was written `overlay/panelPlacement.ts` stood at **371**, and it fell to 295 on 2026-08-02 as a
side effect of the ResizeObserver work, not because anything complained. `demoBridge.ts` itself had
drifted to **351**. So the backlog held a false claim and a stale number at once, which is the
signature of a rule enforced by attention.

1. **The cap now scans `.ts` and `.tsx` beside `.py` and `.rs`.** One scanner, one cap, one
   `just check-linecap`, because the cap is about cognitive load and does not care which toolchain a
   file is in. `SKIPPED_DIRS` gains `dist` and `coverage`, the overlay's own build output as listed
   in `body/app/.gitignore`; that also makes true a sentence
   [docs/modules/repo-gates](../modules/repo-gates.md) had been asserting since dashcheck landed,
   that dashcheck skips the same directories as the line cap minus `tests` and `_generated`, and a
   test in `scripts/tests/test_linecap.py` now holds the two lists to it.
2. **A test file is whatever that toolchain's runner calls a test.** `SKIPPED_FILE_PATTERNS` gains
   `*.test.ts` and `*.test.tsx`, which is verbatim the `src/**/*.test.{ts,tsx}` that
   `body/app/vite.config.ts` collects, plus `test-setup.ts`, that config's `setupFiles` entry and the
   TypeScript analog of `conftest.py`. Nothing wider: a `.spec.ts` cannot exist under this runner's
   config, so no rule pretends to cover one. `.d.ts` is **not** exempt, because an ambient
   declaration is hand-written TypeScript like any other.
3. **The stylesheet, the markup, and the proto stay outside, and this is the argument.** The cap's
   remedy is "split by responsibility", which presumes a module with a public contract. `overlay.css`
   (2420 lines the day this was decided, 2686 on 2026-08-08, 2700 as of 2026-08-09) is one cascade
   whose order is load-bearing, so splitting it trades a long file for fragile `@import` ordering,
   and `index.html` is a single mount point. `proto/body.proto` (314 lines then, 345 as of
   2026-08-08) is over 300,
   and capping it would put the gate in direct conflict with this repo's
   own architecture invariant that the seam is "defined once in proto/body.proto". A gate that
   demands a violation of AGENTS.md is worse than no gate. The CSS is recorded as an open deferral in
   [docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates); the proto is a decision, not a
   deferral. `scripts/tests/test_linecap.py` pins all three so dropping one is a deliberate edit.
4. **`demoBridge.ts` was split rather than exempted.** Its open refinement entry had argued for
   waiting, on the grounds that lifting the canned script into a constants module "would cost a new
   entry in the coverage `exclude` list" and that "widening that list is the bigger concession". That
   reasoning was written while nothing enforced the cap, so the comparison was against no cost at
   all. Re-read against the code it does not survive: the concession is not a new **kind** of
   unmeasured file, since the demo bridge has been coverage-excluded since it was written, but the
   same exclusion spelled over the two files it now occupies. Measured rather than assumed: with
   `demoScript.ts` left out of the list, `vitest run --coverage` reports it 0% over lines 8 to 141
   and the tree drops from 100% to **97.45%**, exit 1; with it in, the tree is back at 100%. The cost
   is therefore exactly one explicit path, and it is written as a path rather than a
   `src/bridge/demo*.ts` glob because this repo has already been bitten once by gate config that
   enumerates loosely (the fail-open `scripts/` config closed 2026-07-12, ADR-0026 addendum). The
   bridge went 351 to 234 and the extracted script is 141; `sessions()` and `reminders()` are
   functions rather than constants so each `DemoBridge` still stamps its seed relative to its own
   construction, as the inline initializers did. Both exclusions came off on 2026-08-11, when the
   demo bridge joined the overlay's shared `BrainBridge` check list and its script became tested
   data, which is the trigger the refinement entry had set; the 0% measured here was a fact about a
   script nothing imported in CI rather than a property of the file
   ([ADR-0001](ADR-0001-architecture.md), the addendum of that date).
5. **CI needed no change, which was checked rather than presumed.** `cross-tree` in
   `.github/workflows/ci.yml` carries no `needs` and no `if`, so it runs on every push and pull
   request; `scripts/ci_paths.py` classifies `body/app/src/overlay/useOverlay.ts` as overlay-only,
   and the cap scan sees it anyway because it is not path-gated. Only the comments naming the scanned
   suffixes were wrong, in that workflow, in the `justfile`, and in
   [ADR-0006](ADR-0006-gate-performance.md) decision 1.

**Proven able to fail before being trusted**, per AGENTS.md's distrust-green rule, with
`just check-linecap`'s own command. A planted 301-line `body/app/src/overlay/planted.ts` and a
301-line `body/app/src/components/Planted.tsx` each exit 1 naming the file; a 300-line one exits 0.
A 400-line `*.test.ts` and `*.test.tsx`, a 400-line `.ts` under `dist/`, `coverage/` and
`node_modules/`, and `test-setup.ts` grown past 400 all exit 0, so each exclusion excludes what it
claims and nothing else. The new scanner branches are covered by tests that fail under mutation:
reverting `SOURCE_SUFFIXES` fails 6, dropping `*.test.ts` fails 1, dropping `dist` fails 2.

## Addendum (2026-08-10): the declined shell clippy was run here, and the decline holds

The fix-when-it-bites deferral above has two triggers, and only one of them is settled by reading a
file. The 2026-08-09 backlog sweep read `.github/workflows/ci.yml` and confirmed the first (CI has
gained no desktop stack), then left the second, shell findings outpacing the maintainer's local
checks, resting on a read as well. That one is only settled by running the check, so it was run on
2026-08-10.

- **The shell is clean.** `cargo clippy --all-targets -- -D warnings` in `body/app/src-tauri` exits
  0 over 978 lines in 12 files, where this ADR recorded 881 lines. So the wiring grew by a file and
  97 lines and accumulated no finding, and the trigger has not fired.
- **Proven able to fail first**, as the earlier reading did: a `useless_format` planted in
  `src/tray.rs` makes the same command exit 101 on the lib and lib-test units, and it exits 0 again
  with the file restored.
- **The route this ADR records for the dev host is out of date.** It says pkg-config is absent and
  a permissive shim stood in. `/usr/bin/pkg-config` is real there now, and no shim was needed: what
  is missing is the `.pc` metadata, obtained without sudo by `apt-get download` plus `dpkg-deb -x`
  into a scratch prefix outside the repo with `PKG_CONFIG_PATH` naming its two `pkgconfig`
  directories.
- **The decline is now measured rather than argued.** That prefix took **47 `-dev` packages** (6.0
  MB fetched, 48 MB unpacked), discovered in six rounds because each `pkg-config` failure names
  only the next missing `Requires`, from `dbus-1` and the gtk/webkit set down to `graphite2`,
  `libthai`, `datrie`, `libsharpyuv` and `sysprof-capture-4`. None of those libraries is ever
  loaded, since clippy does not link; they exist to get build scripts past a probe. The Rust half
  is the cheap half, the Tauri graph type-checking in 22.6 s wall on a partly populated target
  directory, so what a runner would pay for is provisioning, which `rust-cache` does not cache.
  Both triggers stand and the deferral stays open in
  [docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates).

## Addendum (2026-08-17): the shell's clippy lands in CI, as the one gate `just check` does not run

The deferral recorded above is closed by wiring it, and the thing that changed is not the price
of the check but who was being asked to pay it. Every reading of this since 2026-07-16 measured
the cost as though shell clippy had to ride inside `check-body`, and on that assumption the
decline was right: a webkit `apt-get install` on every `body/` change, every `proto/` change and
every shared gate file, to lint a subtree most of them never touch. The assumption was the
defect. Split into its own path-filtered job, the provisioning lands on a `body/app/src-tauri/`
edit and on nothing else, and the arithmetic that justified the decline no longer applies to it.

Measured here rather than restated, since this entry has twice carried numbers that later reads
had to correct. The `-dev` closure a runner actually needs is **103 packages, 39.6 MB fetched in
about 4 s**, resolved from five roots (`libwebkit2gtk-4.1-dev`, `libgtk-3-dev`,
`libayatana-appindicator3-dev`, `librsvg2-dev`, `libdbus-1-dev`), and the earlier 630-package
figure was a recursive `apt-cache depends` walk with no `--no-recommends`/`--no-suggests`
filtering, which counts alternatives and runtime closures a real install does not. From a
**completely empty target directory**, `cargo clippy --locked --all-targets -- -D warnings` over
the whole Tauri graph finished in **30.9 s wall** against exactly those five roots and their
metadata, so the cold compile this entry called the expensive half is well under a minute, and
`rust-cache` keyed on `body/app/src-tauri` makes every later run cheaper still. Both halves cost
about a minute, once, on the change that could have broken them.

**Decision: CI runs it, local `just check` does not, and the check itself lives in a `just`
recipe either can invoke.** `check-shell` is `cargo clippy --locked --all-targets -- -D warnings`
in `body/app/src-tauri`, and the CI job runs that recipe, so what runs is the same on both sides
and only the schedule differs. This is a real divergence from the rule that `just check` is the
single gate and pre-commit mirrors it, and it is worth naming plainly rather than burying: a
shell clippy finding can now reach a local commit and be caught in CI instead of at the hook,
which no other check in this repo allows. It is accepted because the alternative is worse in a
way that is not close. Every other `check-*` recipe runs on a clean checkout with nothing but
the language toolchains; this one needs the Linux GTK/webkit/dbus dev packages, which the host
this repo is developed on does not have and cannot `sudo apt-get install`. Putting it in
`just check` would make the single gate unrunnable on a plausible dev box, and the two ways out
of that are both worse than the divergence: a check that skips itself when the libraries are
missing is a gate that cannot fail, which this repo treats as a defect, and a check that fails
for a missing system library trains the committer to ignore reds. A named recipe that CI
schedules keeps the check real, keeps it in one place, and keeps `just check` runnable.

The sudo-less route stays useful and is what validated this: `apt-get download` the `-dev`
closure, `dpkg-deb -x` it into a prefix outside the repo, and point `PKG_CONFIG_PATH` at its
`pkgconfig` directories. None of those libraries is ever loaded, since clippy does not link; the
packages exist to get the `-sys` build scripts past a pkg-config probe. That is also why the
runner installs them with `--no-install-recommends` and why no MSVC-style linking toolchain
appears anywhere in the job.

Proven able to fail before being trusted, at both levels this touches. A `useless_format` planted
in the shell's `link.rs` makes `just check-shell` exit **101**, naming the lint on the lib and the
lib-test unit, and it exits 0 with the file restored. On the routing side, the job is gated on a
`shell=` output nothing else reads, so a classifier that forgot to set it would leave the job
unrun and indistinguishable from passing; routing `body/app/src-tauri/` back to plain rust fails
the classifier suite. The shell's current 978 lines in 12 files are clippy-clean as they stand, so
this lands green and the check earns its place by what it catches next, not by what it caught
today. It still LINTS the shell rather than running it, which wants a real Win32 desktop session
([host/](../host/index.md)).
