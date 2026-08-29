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

## Addendum (2026-08-25): where a check goes when its evidence, not its toolchain, is out of reach

Two deferrals arrived a day apart wearing different subjects and asking one question, so the
answer is written here rather than twice, beside the single divergence this repo has already
accepted. The first: an image that declares a `VOLUME` gets an anonymous volume on every start
of any container mounting nothing at that path, `docker compose down` leaves it on the host under
a name nobody chose, and nothing here asks which paths the images it pins declare. The second:
both stacks commit their generated seam stubs and regenerate them by hand, so a proto edit that
skips `just proto` leaves the committed files disagreeing with [proto/body.proto](../../proto/body.proto),
which is the seam's single source of truth, with every gate green.

Both are checks this repo genuinely wants, and in both the evidence sits somewhere `just check`
cannot go. What an image declares is a fact about a registry that only a pull can answer, and CI
has neither a docker daemon nor the images. What a codegen run produces needs `grpcio-tools` on
one side, which is already a brain dev dependency and bundles its own `protoc`, and a system
`protoc` binary on the other, which is exactly the toolchain the committed-stub decision
(ADR-0003) exists so nobody needs.

The tempting move in both cases is a second CI-scheduled recipe sitting next to `check-shell`.
It is refused. `check-shell` is outside the single gate because its *toolchain* cannot be assumed
on a clean dev box, and that argument does not transfer: a gate whose evidence is missing is not
the same shape of problem as a gate whose compiler is missing, and it has cheaper answers.
Letting the exception generalize would turn "one recipe is deliberately outside `just check`"
into a category, and a category is how a single gate stops being single.

**Decision: three answers, tried in this order, and the exception list stays at one.**

1. **Bring the evidence into the tree.** Write the out-of-reach fact down as a file the gate can
   read, gate that record against the tree it describes, and give the re-derivation its own
   hand-run recipe that fails when the record has gone stale. The gate then runs everywhere,
   including on a machine with no docker at all, and the recipe is what keeps the record honest.
   The shape is already here and proven: [docs/refinements/index.md](../refinements/index.md) is
   a generated artifact, `backlogcheck.py` holds it to the task files, and `just backlog`
   rewrites it. `scripts/imagevolumes.py` plus `just image-volumes` is the same arrangement with
   a docker daemon where the task files were. The honest cost is named rather than hidden: a
   recorded fact can go stale between re-derivations, so the record is only as good as the
   discipline of running the recipe when a pin moves, and that instruction belongs on the recipe
   and in the runbook rather than in anybody's head.
2. **Ask a cheaper question the tree can already answer.** Sometimes the expensive check has a
   text-only shadow that catches the same class of defect, and measuring which defects each one
   actually catches is what tells them apart. The stub case turned on exactly that measurement:
   regenerating the Python stubs is free and reproduces byte for byte, and it does not notice a
   comment at all, while a comment is the only part of a skipped regeneration that no compiler
   would catch. So the check that earns its place is a text comparison running no codegen, and
   the regenerate-and-diff is declined on evidence rather than on cost (ADR-0003 stub-fidelity
   addendum).
3. **A hand-run recipe that gates nothing.** Last, and only when neither of the above can be
   built. Its record here is poor and should be quoted whenever it is proposed: the probe image's
   two declared volumes were each found by reading `docker image inspect` by hand, months of runs
   apart, each time after the leak had been happening on every start. A check nobody is made to
   run is a check that runs after the damage, if at all. `just image-volumes` is deliberately not
   this: it is tier one's second half, and what it guards is a record a gate reads on every
   commit.

The first application found a defect that had been live the whole time and that neither deferral
knew about. `pg-backup` in [docker/docker-compose.memory.yml](../../docker/docker-compose.memory.yml)
runs the same `pgvector/pgvector:pg16` image as the server, mounts only its dump directory and its
script, and therefore collected an anonymous volume at `/var/lib/postgresql/data` on every start
of the memory stack, seeded from the image's own empty data directory that the sidecar never
touches. Reproduced before the fix by creating a container with exactly that mount set:

```
$ id=$(docker create --network none -v "$PWD/docker/postgres/backup.sh:/backup.sh:ro" \
    -v "$PWD/pgdata:/backup" --entrypoint /bin/sh pgvector/pgvector:pg16 /backup.sh)
$ docker inspect "$id" --format '{{range .Mounts}}TYPE={{.Type}} NAME={{.Name}} DST={{.Destination}}
{{end}}'
TYPE=bind NAME= DST=/backup.sh
TYPE=bind NAME= DST=/backup
TYPE=volume NAME=aa9c20129d789ac62a5484c4be308368b5c5630c5ebb30291dc7f9a51a376179 DST=/var/lib/postgresql/data
```

It takes the same fix the probe's fixture already uses, a `tmpfs` at the declared path, which
leaves docker's declaration nothing to anonymise. That is the argument for tier one stated as a
measurement rather than as a preference: the question had been askable by hand for months and
nobody asked it, and the first run of a gate that asks it on every commit answered no.

## Addendum (2026-08-25): the re-derivation asks the registry, and the tag stays a tag

The arrangement above records what each image declares and gives the record a hand-run recipe, and
the deferral it left open was the obvious one: a pinned tag can be republished under the same name,
so the record can go stale with no file in this tree changing and no gate able to tell. Three
answers were framed for it. All three are declined, and the reason is a defect found while
measuring them rather than an argument about which is prettiest.

**`docker image inspect` never reaches a registry.** It answers out of the local cache, and
`rederive` was built on it, so the one thing keeping the record honest could only ever confirm
whatever this machine happened to be holding. On a box carrying a month-old copy of
`ghcr.io/ggml-org/llama.cpp:server`, running the recipe reported that the record agrees with
docker about an image the registry stopped serving under that name weeks earlier. That is worse
than the deferral said. It was not "the record is only as fresh as the last re-derivation"; it was
that a re-derivation could not see a moved tag at all, which makes it precisely the shape this
module's own docstring already refuses, a run that "would confirm the record it was run to doubt".

**Decision: `--rederive` pulls every image it did not build before asking what that image
declares, and a pull it cannot do is reported rather than answered from the cache.** The three
images this repo builds are asked without a pull, having no registry to be refreshed from: their
answer is the local build, which is the thing a container here really runs. Which references those
are is not guessed from the shape of the name; the walk already reads `build:` per service, so the
gate hands the re-derivation the set it read.

That is the smallest thing that makes the deferral's own subject visible, and it lands in the
tier-one arrangement rather than beside it. A moving tag republished with a new `VOLUME` now shows
up the next time anybody runs `just image-volumes`, which is the same day the record was going to
be wrong either way, and the recipe's instruction gains one more occasion: run it when a pin moves,
and on any day a moving tag may have been republished.

The three framed answers stay declined against that.

- **Recording the resolved digest beside each tag** would make a moved tag visible only to
  something that can resolve a digest, which is a docker call and therefore the same problem one
  level down. It also churns: an upstream rebuild moves the digest without moving a declared path,
  so the record would be edited for events the record does not care about, and a record edited
  often is a record nobody reads.
- **A scheduled workflow running the recipe on a timer** buys the same visibility at the cost of a
  second scheduled job and a runner pulling multi-gigabyte CUDA images weekly, reporting into a job
  nobody watches. The tier-three argument above already says why that is the last resort and not
  the first, and the recipe now answers honestly when it is run, which is the half that was broken.
- **Pinning every image by digest** would make the whole class impossible and would turn every
  compose file into unreadable hashes maintained by dependabot churn. The class it closes is a
  publisher adding a `VOLUME` to an existing tag, which is rare, and whose symptom is clutter on
  the host rather than lost data. The trade is not worth the compose files.

What remains open is stated plainly: between two runs of the recipe, a republished tag can still
add a declared path and nothing here will know. That is the residue of choosing a record over a
daemon, it is named on the recipe and in the runbook, and it is the price of a gate that runs on a
machine with no docker at all.

### Proven able to fail

**Suite: `scripts/tests/test_volumecheck.py` and `scripts/tests/test_imagevolumes.py`, 46 tests**
(40 before this change), run against a mutated gate and restored from a copy after each. Baseline
46 passed, 0 failed. Eight mutants planted, seven killed by the suite and the eighth by the live
run below.

| mutant planted in the gate | tests killed |
|---|---|
| nothing is ever pulled, the cache answers for the registry | 3 |
| everything is pulled, including the images built here | 2 |
| the built set never reaches the re-derivation | 2 |
| no service is recorded as built | 3 |
| every service is recorded as built | 2 |
| the walk forgets what one file built | 3 |
| the drift report is handed the names instead of the built | 1 |
| a failed pull is answered from the cache instead of raised | 0, see below |

The survivor is the one mutant no unit test can reach: it lives inside `docker_volumes`, the thin
adapter that shells out to a real daemon, which is this module's one `pragma: no cover` and is
covered by an `integration`-marked test instead. It was killed live, and by accident first. The
initial live run of the new recipe on this host could not pull at all, docker's credential helper
being unavailable in that shell, and it reported five rows as failed pulls and exited 1 rather
than answering any of them from the cache. Re-run with a working docker config it exits 0 over all
eight images, five pulled and three built. With the pull removed and nothing else changed, the same
broken-credential shell exits 0 and prints that the record agrees with docker, which is exactly the
green this addendum exists to stop being possible.

## Addendum (2026-08-26): the record is held to the Dockerfiles this tree builds from

The arrangement above brings an out-of-reach fact into the tree and gates the record. The residue
it left is the same record moving under the gate from the other side. Three of its eight rows are
images this repo builds, `cortex-brain`, `cortex-mcp-email` and `cortex-model-host`, and each is
built from a Dockerfile sitting right here. Add `VOLUME /var/cache/thing` to
[brain/Dockerfile](../../brain/Dockerfile) and the built image declares a path, every container of
it collects an anonymous volume, and the row goes on saying the image declares nothing. `just
check` stays green, and only a hand-run `just image-volumes` on a machine that has rebuilt the
image would notice. Neither Dockerfile carries a `VOLUME` today, which is why this was a hole
rather than a defect.

That is the second answer above applied a second time: a cheaper question the tree can already
answer, asked on every commit, with no daemon anywhere near it.

**Decision: every `VOLUME` path a Dockerfile in this tree declares must appear in the row for the
image built from it, and the check runs inside `volumecheck.py`'s existing walk.** The rule is
one-directional, and that is what makes it cheap. A recorded path the Dockerfile does not declare
is fine, being inherited from the base image, and the record deliberately holds no row for a base:
only docker can say what `python:3.12-slim-trixie` declares. The half the tree can answer is the
half this asks. `ONBUILD VOLUME` is deliberately not read, declaring a volume in an image built
from this one rather than in this one.

**Decision: which Dockerfile builds which row is read from each compose service's `build:` stanza,
never recorded beside the row.** The alternative was cheaper by every measure except the one that
matters: writing `brain/Dockerfile` next to `cortex-brain` in the record spells one fact in a
second place, and nothing would then derive it to compare, so a `build:` repointed at another
context would leave the record naming a file that builds nothing, silently, on the same day. That
is the defect this addendum exists to close, re-created one level down. The gate already derives
the image *name* from compose and holds the record to it in both directions, an unrecorded image
and a row nothing names each being a fault; the Dockerfile is the same kind of fact and gets the
same treatment. A relative context is resolved against **both** project directories compose can
pick, the repo root that the `just` recipes pass and the compose file's own directory that a bare
`docker compose -f docker/...` uses, exactly as `bindcheck.py` resolves a bind source, and a
Dockerfile landing under neither is a fault rather than a silent pass.

**What it cost, which the deferral had understated.** The mapping could not be read at all:
`composeservices.py` set its `builds` flag to a bare `True` on meeting the key and never looked
inside the stanza, so the long form's `context:` and `dockerfile:` in
[docker/docker-compose.gpu.yml](../../docker/docker-compose.gpu.yml) arrived as service keys the
walk did not recognize and were stepped over in silence, which is the one thing that reader is
written never to do. `Service.build` now carries where the image is built from, in both spellings,
and the walk refuses a build key it was not taught rather than skipping it. Teaching it that put
the file over the line cap, so the mount-entry half moved out to `composetargets.py`, which owns
the one question a mount entry answers, the container path it names, in all four spellings compose
accepts. That is the sibling of `composemounts.py` the module docstrings already contrast: one
reads a mount's source, the other its target.

What stays open is the base image, and it is not a new exposure: if a base ever declares a path,
the built image inherits it, the record carries it after the next re-derivation, and this check
says nothing about it either way. That is the one-directional rule working as written.

### Proven able to fail

**Suite: `scripts/tests/test_volumecheck.py`, `scripts/tests/test_dockerfilevolumes.py` and
`scripts/tests/test_composeservices.py`, 130 tests** (86 before this change), run against a mutated
gate and restored from a copy after each. Baseline 130 passed, 0 failed. Ten mutants planted, all
ten killed, none of them by a crash: each mutant leaves a gate that runs and answers wrongly.

| mutant planted in the gate | tests killed |
|---|---|
| a VOLUME instruction is never recognized | 23 |
| a relative VOLUME path is accepted instead of refused | 1 |
| continuation lines are not joined onto their instruction | 3 |
| a declared path no row carries is not reported | 4 |
| a build reaching no Dockerfile is a silent pass | 2 |
| only the repo root is tried as a project directory | 2 |
| one file reached from both project directories is read twice | 1 |
| the block form's dockerfile key is stepped over | 5 |
| the short form's context is not recorded | 1 |
| the gate never asks a build what its Dockerfile declares | 7 |

The live proof beside it, which is the one the deferral described in words. With
`VOLUME /var/cache/thing` appended to [brain/Dockerfile](../../brain/Dockerfile) and nothing else
changed, `volumecheck.py --root ..` exits 1 and reddens both rows that file builds, naming each
image separately, because each is a container of its own collecting a volume of its own:

```
$ cd scripts && uv run python volumecheck.py --root ..
docker/docker-compose.email.yml:37: brain/Dockerfile declares VOLUME '/var/cache/thing', and the row for 'cortex-mcp-email' in scripts/imagevolumes.py does not carry it; ...
docker/docker-compose.yml:15: brain/Dockerfile declares VOLUME '/var/cache/thing', and the row for 'cortex-brain' in scripts/imagevolumes.py does not carry it; ...
```

With the line removed the same command exits 0 and states the reading behind it, four declared
paths covered over ten compose files, eleven service definitions, eight images, and two Dockerfiles
here declaring nothing their rows do not carry.

## Addendum (2026-08-28): the bases the built rows stand on get rows of their own

Two addenda above made the record honest from two sides, and each named what it left. The
re-derivation now pulls every reference it did not build, and the gate now holds each built row to
what its own Dockerfile declares. What neither reached is the third side: `cortex-brain`,
`cortex-mcp-email` and `cortex-model-host` are asked with no pull, having no registry, so
`docker image inspect cortex-brain` answers out of whatever the machine running the recipe last
tagged. If that build is old and the base it stands on has since been republished with a new
`VOLUME`, the row is confirmed against the old build and `just image-volumes` reports agreement.
That is the defect the pull addendum fixed for pulled references, arriving on the three it
deliberately exempted.

**The exposure was measured before it was argued.** On this host, on 2026-08-28,
`python:3.12-slim-trixie` and `ghcr.io/ggml-org/llama.cpp:server-cuda` each declare no `VOLUME` at
all, so nothing is wrong today. That is a dated reading and not a property: both are moving tags,
and the record has to survive one of them gaining a declaration. The staleness itself is not
hypothetical and was live on this host while the deferral was open: `cortex-mcp-email` carried a
build from 2026-07-03 while the `python:3.12-slim-trixie` beside it had been republished on
2026-08-25, an eight week window in which that row answered for an image no fresh build would
produce.

**The mechanism was measured too**, because the decision rests on it. A base declaring
`/probe/base` was built, an image built `FROM` it declares `/probe/base` itself, so a declaration
really is inherited. A `FROM ... AS builder` stage declaring `/probe/builder` contributed nothing
to the built image, only the final stage's config surviving a build. Those two readings are what
make the answer below complete rather than approximate: what a built image declares is exactly the
union of what its Dockerfile declares and what the image its **last** stage stands on declares, and
this tree can already read the first half.

**Decision: the record holds a row for each base a Dockerfile here stands on, and every path that
row carries must appear in the row for the image built from it.** The rule is one-directional, like
its sibling, and runs in the same walk over the same read of the same file. The base rows are
ordinary pulled references, so the recipe that already refreshes correctly refreshes them, and the
gate that already runs on a machine with no docker reads the result. A base republished with a new
`VOLUME` therefore reddens `just check` on the next re-derivation, rather than waiting for somebody
to rebuild on the machine that happens to run the recipe.

That also retires a claim this document used to make. `imagevolumes.py` argued at length that no
base needs a row, on the grounds that whatever a base declares is already inherited into the built
image, which is the thing a container really runs. The premise was true and the conclusion did not
follow: inherited into the image *this machine last built*, which is not the image the next build
produces, and a record whose freshness depends on when somebody last ran `docker build` is the
cache read the pull addendum exists to refuse.

The three other shapes the deferral framed stay declined against that.

- **Building before inspecting** would make the recipe answer about a fresh image, and it is the
  honest version of the question. It costs a CUDA image build on every machine that runs the
  recipe, minutes and gigabytes, for an answer the two rows above compute from two pulls the
  recipe already does. It also changes what the recipe is: a verification that rebuilds and retags
  the artifacts it was verifying is no longer only reading, and a build failing for a reason that
  has nothing to do with volumes would stop the record being checked at all.
- **Refusing to answer for a built image older than its Dockerfile** aims at the half that is
  already closed, and closed better, since the Dockerfile rule runs on every commit rather than on
  a hand run. It says nothing about the base, which is the whole of what is left. The comparison is
  also unreliable: a fresh clone gives every file a checkout time, so every built image would be
  older than every Dockerfile and the recipe would refuse to answer for all three rows.
- **Declaring the exposure too small to act on** is the one with a real case, since both bases
  declare nothing today and the symptom of the class is clutter on a host rather than lost data.
  It loses on cost. The answer taken here needs no build, no schedule and no second daemon, and it
  moves the question out of "run the recipe and hope somebody rebuilt first" into a rule that runs
  on every commit. A residue named on a recipe is the tier-three answer this ADR already argues is
  the last resort, and it is not the last resort here.

**What it cost.** `dockerfilebases.py` is the new reader: the image a file's last stage stands on,
followed back through stage names when the last `FROM` names an earlier stage, `scratch` answered
as standing on nothing, a `--platform` flag dropped, and every other shape refused rather than
guessed at, including a stage standing on itself. The file's own grammar moved there with it, the
comment and continuation handling and the `escape=` refusal, because a stage cannot be found before
the lines are joined and both readers now work over the same ones. `volumecheck.py` was at 294 of
the 300 line cap and had been within a line or two of it through both preceding addenda, so
`base_project` moved to `composefiles.py`, which already owns the bare stems that answer it and is
therefore where the knowledge belonged. The stale-row rule needed no second mechanism: a base is
counted among the references the walk named, so a base row nothing stands on is reported by the
rule that already reports an image row nothing runs.

### Proven able to fail

**Suite: `scripts/tests/test_volumecheck.py`, `scripts/tests/test_dockerfilevolumes.py` and
`scripts/tests/test_dockerfilebases.py`, 98 tests** (86 before this change), run against a mutated
gate and restored from a copy after each. Baseline 98 passed, 0 failed. Twelve mutants planted, all
twelve killed, none of them by a crash: each leaves a gate that runs and answers wrongly.

| mutant planted in the gate | tests killed |
|---|---|
| the last stage is not the one that decides | 9 |
| a stage name is never followed back to its image | 6 |
| a stage name is matched case-sensitively | 1 |
| scratch is looked up as if it were an image | 24 |
| a FROM naming more than an image and a stage is accepted | 4 |
| a file with no FROM answers instead of being refused | 1 |
| a flag is read as the image it precedes | 2 |
| an unrecorded base is a silent pass | 2 |
| a path the base declares and the row lacks is not reported | 2 |
| the built row is compared against the base without normalizing | 1 |
| the gate never asks a build what its base declares | 4 |
| a base never reaches the record's naming half | 5 |

The live proof beside it, which is the deferral's own subject acted out. With
`python:3.12-slim-trixie` recorded as declaring `/var/cache/base` and nothing else changed,
`volumecheck.py --root ..` exits 1 and reddens both rows built from the file that stands on it,
naming each image separately because each is a container of its own:

```
$ cd scripts && uv run python volumecheck.py --root ..
docker/docker-compose.email.yml:37: brain/Dockerfile builds 'cortex-mcp-email' FROM 'python:3.12-slim-trixie', which declares VOLUME '/var/cache/base', and the row for 'cortex-mcp-email' in scripts/imagevolumes.py does not carry it; ...
docker/docker-compose.yml:15: brain/Dockerfile builds 'cortex-brain' FROM 'python:3.12-slim-trixie', which declares VOLUME '/var/cache/base', and the row for 'cortex-brain' in scripts/imagevolumes.py does not carry it; ...
```

With the row put back the same command exits 0 over four declared paths, ten compose files, eleven
service definitions, ten images counting the two bases, and two Dockerfiles here declaring and
inheriting nothing their rows do not carry. `just image-volumes` against a real docker exits 0 on
the same day, over all ten images, three of them built here and seven pulled before they were
asked.

What stays open is smaller and is filed rather than named on a recipe. The two base rows are now
the only rows a built row's correctness depends on that nothing derives: the gate reads the `FROM`
and looks the reference up, so a repointed base is caught, but the row's *contents* are still a
recorded measurement rather than something the built row is computed from. Deriving a built row
entirely, as the union of its Dockerfile's declarations and its base's row, would leave the record
holding only what a registry can answer for, and would make the three built rows unnecessary
([R-473](../refinements/tasks/473-a-built-row-is-recorded-where-it-could-be-derived.md)).

## Addendum (2026-08-29): the three built rows stay recorded, because the union is a floor

The addendum above closed the base question and named what it left: with a row for each base, what
a built image declares looked computable, and
[R-473](../refinements/tasks/473-a-built-row-is-recorded-where-it-could-be-derived.md) asked
whether `cortex-brain`, `cortex-mcp-email` and `cortex-model-host` should be derived from their two
readable sources rather than recorded. Deriving them would leave the record holding only what a
registry can answer for, would give `just image-volumes` nothing to ask about a built image, and
would retire the last reason a built row can be wrong.

The whole of it rests on one claim, which the addendum above stated as a measurement: *what a built
image declares is exactly the union of what its Dockerfile declares and what the image its last
stage stands on declares*. The entry said that claim had to be measured rather than assumed before
any row was removed, since deriving makes it load-bearing in a direction it is not load-bearing
today. It was measured. **It is false**, and the decision follows from how it fails.

### The falsifying reading

Taken on this host against docker 29.7.2 on 2026-08-29, with `Config.Volumes` read through the
same `INSPECT_FORMAT` the record is measured with, and `Config.OnBuild` beside it. A base whose
only instruction is `ONBUILD VOLUME /probe/onbuild` declares no volume of its own, so the row
`imagevolumes.py` would hold for it is the empty tuple, the same row both real bases have today. An
image built `FROM` that base by a Dockerfile carrying no `VOLUME` instruction at all declares
`/probe/onbuild`:

```
$ docker image inspect --format '{{json .Config.OnBuild}}' cortex-probe-onbuild-base
["VOLUME /probe/onbuild"]
$ docker image inspect --format "$INSPECT_FORMAT" cortex-probe-onbuild-base
$ cat Dockerfile.onbuildchild
FROM cortex-probe-onbuild-base
$ docker image inspect --format "$INSPECT_FORMAT" cortex-probe-onbuild-child
/probe/onbuild
```

Both halves the derivation reads say nothing: the base's row is empty and the Dockerfile declares
nothing, while the built image really does declare a path and every container of it really does
take an anonymous volume there. The same build under `DOCKER_BUILDKIT=0` answers `/probe/onbuild`
too, so this is the builder's behaviour rather than one frontend's. The child's own `Config.OnBuild`
is `null`, so the instruction fires once and clears, which is what makes it invisible one level
down: nothing in the built image records that it was ever there.

Three readings taken in the same session say the rest of the mechanism is as the addendum above
described it. A base declaring `/probe/base` and a child declaring `/probe/own` produce a built
image declaring both, so the union really is inherited and really does merge. A
`FROM ... AS builder` stage declaring a path contributes nothing to an image whose last stage
stands elsewhere. And `VOLUME []` is refused by the builder rather than un-declaring an inherited
path, so no Dockerfile can shrink what it inherits.

Put together: the union of the two readable sources is a **floor** under what a built image
declares, never a ceiling. `ONBUILD` is one way past it and is the one that was found; a claim
already falsified once is not worth re-stating with an exception bolted on, since what the record
has to survive is a base gaining a mechanism nobody here enumerated.

### Decision: the three built rows stay recorded, and the one-directional rules are required

The record goes on holding a measured row for each of the three images this repo builds. The two
rules over them stay one-directional, and the reading above upgrades that from a cheapness
concession to a correctness requirement: a built row legitimately carries paths neither the
Dockerfile nor the base's row declares, so a rule demanding equality would redden a correct record.
The addendum above justified one-directionality by saying a recorded path neither half declares is
nobody's fault. It is better than nobody's fault. It is the only place a third source can appear.

What derivation would cost is the point. A derived row is computed from two sources that both say
nothing in the case above, so the gate would report a clean pass on an image that declares a path
no compose file mounts, which is the exact leak `volumecheck.py` exists to catch, arriving through
the gate rather than past it. A recorded row is read off a real built image and therefore carries
whatever produced the declaration, enumerated or not. That is the whole argument for recording an
out-of-reach fact instead of modelling it, and it is the argument this ADR already made when it
chose to record what an image declares rather than to reason about it.

The entry's own suggestion, that `--rederive` compare the derivation against a real built image and
that this is stronger than the row it replaces, does not survive either. It is the same single
reading, with the tree's side now computed from a claim measured false, and it moves the only check
of that claim onto a hand-run recipe. Today the record and the derivation are two independent
readings of one image, and the gate holds the second under the first on every commit. Deriving
collapses them into one.

Two consequences are worth stating plainly rather than leaving to be re-derived.

- **`imagevolumes.py` says so beside the paragraph explaining the base rows**, because that
  paragraph is exactly the reasoning a reader follows to arrive at this question, and it should not
  have to be re-measured to be answered.
- **Three places asserted the retired claim** in the present tense and are corrected: the
  `volumecheck.py` docstring, the `check-volumecheck` comment in the justfile, and the
  `volumecheck.py` entry in `docs/modules/repo-gates.md`. Each said the two halves account for the
  whole of what a built image declares. They account for a floor under it.

### Alternatives considered

- **Derive the three rows** is the entry's own proposal and is what the reading above rules out. It
  is not merely unproven; it is unsound in a case a moving base tag can produce, and both bases here
  are moving tags by design.
- **Derive, and add `ONBUILD` as a third readable source.** This is the honest version of deriving,
  and it does close the case that was found. It loses on what it assumes rather than on cost: it
  keeps the shape of the false claim, an enumeration of sources believed complete, and buys safety
  only against the mechanism that happened to be measured on the day it was written. The record has
  no such enumeration to be wrong about.
- **Record, and hold the record two-directionally against the derivation.** Rejected for the reason
  in the decision: with a third source real, the record is *supposed* to be able to carry more, and
  the rule would fail on a correct record the first time a base carried an `ONBUILD VOLUME`.
- **Record `ONBUILD` alongside each base row so the gate sees the third source too.** Not rejected,
  filed. It is a real gap and it is a slice rather than a sentence: it needs a second dimension on
  every row, a second thing for the inspector to ask, and the rule that spends it
  ([R-493](../refinements/tasks/493-a-base-may-declare-a-volume-through-onbuild.md)).

### No mutation table, and what stands in for one

No rule was wired or changed by this close, so there is nothing new to prove able to fail; the
twelve mutants in the addendum above still name the suite they were counted over and still cover
every rule that runs. The evidence here is the measurement instead, four readings against a real
docker rather than four claims about one, and the arrangement it endorses was exercised the same
day: `just image-volumes` was run against a real daemon and agreed with all ten rows, and
`volumecheck.py --root ..` exits 0 over the same tree with no docker involved at all, which is the
property the whole recorded-answer arrangement exists to keep.
