# body/app (`cortex-body`, overlay + Tauri shell)

**Purpose.** The host-native body app (ADR-0011): a React + Vite overlay summoned by a global
hotkey, talking to the brain over the `Converse` stream, wrapped in a thin Tauri shell. It is its
own project outside the `body` Cargo workspace (`body/Cargo.toml` excludes it), so `just check`
never builds Tauri. The frontend is covered to 100% by Vitest; the Tauri Rust shell is validated by
hand on Windows, like the brain's real adapters.

The two halves meet at one typed port, `BrainBridge`. Components depend on that port and on a
`cortex:activate` DOM event, never on Tauri, so the whole overlay runs and tests in a plain browser.
Look and feel is [overlay-ux.md](../design/overlay-ux.md), and the motion measurements are in
[panel-motion.md](../readings/panel-motion.md).

## The `BrainBridge` port

`src/bridge/types.ts` declares it, along with the TypeScript mirrors of the Rust `body_core`
values: `TurnEvent`, `TransportError`, `SessionSummary`, `SessionMessage`, `DueReminder`,
`LinkState`, `LinkStatus` and `Preference`.

- `converse(sessionId, text, sink) -> Cancellation` runs one turn. Nothing is delivered during the
  call itself, and cancelling silences the turn however often it is called.
- The session reads `listSessions(limit)` and `sessionMessages(sessionId)` (ADR-0021). A zero
  limit means the brain's default listing and a positive one cuts that listing.
- The session writes `renameSession(sessionId, title)` (`""` clears the override),
  `deleteSession(sessionId)` and `setSessionPinned(sessionId, pinned)` (ADR-0021 decisions 10
  to 12). Each is user-driven, and `useOverlay` re-lists after it resolves. Deleting the open chat
  tears down its in-flight turn and falls back to a fresh chat, so a deleted transcript is never
  rendered.
- `listDueReminders()` and `ackReminder(reminderId, firedAtUnixMs)` (ADR-0025), and `checkLink()`,
  the connection probe (ADR-0011 decision 8).
- `getPreferences()` and `setPreference(key, value)` (ADR-0032) store opaque pairs the overlay
  reads once at startup and writes one at a time. An unrecognised key belongs to another surface
  and is ignored; an empty value clears a key, which is how "follow the system" is stored for the
  theme.
- Three implementations: `TauriBridge` over the Tauri IPC, `DemoBridge` for `vite dev` (its canned
  stream and chats live in `demoScript.ts`), and `FakeBridge` for tests. Only `tauriBridge.ts` and
  `main.tsx` are excluded from coverage, as the untested glue.

**The shared check list** (`src/bridge/bridgeContract.ts`, driven by `bridgeContract.test.ts`) is
the TypeScript counterpart of the brain's `*_contract.py` files: one list of thirteen named checks
and one parametrized driver over every implementation CI can run, rather than a suite restated per
implementation. It covers the turn handle, the probe, the catalog, the stored history, the reminder
ack, the settings record, and a stale confirm answer being absorbed rather than rejected.
A new claim about the port is appended there, where it reaches every implementation at once. It
leaves out where two implementations may legitimately differ: the content of a turn's stream, what
a cleared title falls back to, where an unpinned chat sits, and what an ack does to the due list.
`TauriBridge` is outside it, every method of it crossing the IPC boundary.

## The overlay

`overlay/overlayState.ts` is a pure reducer over a `Mode` of hidden, panel, orb or preview. Three
halves are split off it for the line cap and re-exported, so components import one module:
`sessionState.ts` (session switching and the header title), `turnState.ts` (what a `Message` is and
how one `Converse` turn's events apply) and `chromeState.ts` (the panel's sections, the switcher
list and the console's tabs). `overlay/useOverlay.ts` is the controller hook, handing the chat
catalog to `overlay/useSessionCatalog.ts` and spreading it back in.

`useOverlay` owns the `session_id`, minted per new chat, and the chat list, loaded on mount and
after each turn. The header title is the switcher's own `SessionSummary.title` for that chat, read
from the loaded list by `openSession` and `adoptSession`, so the header and the switcher row agree
by construction; only a chat absent from that list falls back to the local `deriveTitle`. That
local derivation is a stand-in for the brain's, not a bound of its own: `sessionState.ts` declares
`TITLE_MAX` 48, the same number `cortex_core.sessions` bounds every listed title to, tied to it by
`scripts/crosscheck.py` (ADR-0021 decision 14). On cold start the first list arrival adopts the
most recent chat into the still-hidden overlay (ADR-0021 decision 6): `adoptSession` hydrates like
`openSession` but preserves `mode` and does nothing unless the `touched` flag is still false, which
open, submit, new chat, cycle and typing all set, so a racing user action wins. Activation is a
pending request rather than a moment (`overlay/activation.ts`): it is recorded before it is
announced, and the app takes any outstanding one when its listener attaches.

**Pure modules.** `theme/` is the theme system. `mark/` is the activity mark (`bubble.ts` the
geometry, `marks.ts` the style registry, `useMarkClock.ts` the frame clock, ADR-0031). `edge/` is
the window's dreaming edge, drawn by `components/PanelEdge.tsx` as a clipped slab under the content
(ADR-0036). `whisper/` is the whispered streaming (`front.ts` the front engine and tokenizer,
`metrics.ts` what a bubble measures, `useWhisperClock.ts` the frame clock, drawn by
`components/WhisperBubble.tsx`, ADR-0037). `overlay/usePreferences.ts` hydrates theme, mark and
edge from the brain once and writes each change back (ADR-0032).

**The panel's geometry** is `overlay/usePanelMotion.ts` deciding when to place the panel, over the
modules that decide what: `panelGeometry.ts` (the arithmetic, including a duration paced by the
distance the further edge travels, between 120ms and 380ms), `panelMemory.ts` (what it remembers
and how it reads its own box), `panelParts.ts` (the probes into the panel's tree),
`panelPlacement.ts` (plays the move, writes the two inline numbers), `panelEdge.ts` (which edge is
held), `panelBudget.ts` (the ceiling, as `max-height` and as a `--ceiling` property, and the split
between the switcher and the reminder stack), `panelRoll.ts` (the slide alongside a section's roll)
and `panelWatch.ts` (a `ResizeObserver` for an unannounced resize). `overlay/measured.ts` publishes
`--chat-floor` off the empty state's box and `--trace-row` off a live activity chip.

**Sections that roll** use `components/Collapse.tsx`, and `overlay/morph.ts` is the contract
between a section and the panel. A rolling section sets `data-morphing` with the height it is
rolling to, so the panel follows the roll frame by frame rather than replaying a render-old
measurement, and `cortex:morphstart` and `cortex:morphend` bracket it, a roll not always being a
render the panel sees. The roll's duration and curve also reach the stylesheet as the `--roll` and
`--ease` tokens on `:root`, tied to `overlay/morph.ts` by `scripts/crosscheck.py`.

**Focus and announcements** (ADR-0052). The overlay keeps one polite live region at its root,
`role="status"`, whose whole vocabulary is `overlay/notice.ts`. A conversation arriving takes the
caret with it (`OverlayState.arrival` plus the composer's `arrival` prop); a list that reshapes
under the hand keeps the caret through `overlay/rowCaret.ts`; a section the reader closes hands it
to its anchor through `overlay/sectionCaret.ts`. `overlay/fieldKeys.ts` decides which chords a
field keeps: one passes through a field whose text the overlay stores and is stopped by a field
whose text it would throw away. `overlay/tabStrip.ts` is the console strip's key map.

**Views and drafts.** `components/Panel.tsx` routes between the `chat` and `console` views
(ADR-0034, ADR-0035). The console's tab is not part of the view name: both tabs are mounted in one
grid cell, so a tab change replaces no chrome, and `TAB_SPREAD_PX` in `ConsoleView` decides whether
it resizes the panel. Unsent composer text is kept per session in `OverlayState.drafts`
(`overlay/drafts.ts`), so a swap hands the arriving conversation its own sentence in the same
commit; an empty field stores nothing, and a draft dies with the body process.

**The screen-capture indicator** (`state.capture` plus `components/CaptureDot.tsx`, ADR-0029) is a
two-rung claim, `"asked" | "read" | null`, not a flag. The reducer raises it to `"asked"` when a
`toolActivity` event names `CAPTURE_SCREEN_TOOL` (`"capture_screen"`), to `"read"` when the
`toolOutcome` settling that dispatch comes back `ok`, and clears it only when the turn ends, so it
stays lit for the whole reply. The ladder only climbs: a second ask after a read stays at `"read"`,
a not-`ok` outcome changes nothing, and an `ok` outcome for an ask this side never saw still
promotes, over-reporting being the safe direction here. Each rung has a fixed accessible label.

**The connection indicator** (`overlay/linkState.ts`, `overlay/useLink.ts`,
`components/LinkDot.tsx`, ADR-0011 decision 8). `state.link` is a `LinkView { state, detail,
probing }`, where `state` is the last thing the brain proved (`ready`, `degraded`, `down`, plus the
overlay's own `unknown`) and `probing` is the overlay's own fact, kept apart so a probe never
overwrites what was last true, rendered as `{ tone, busy, label }` by `describeLink`. Three
sources keep it current and none is a liveness timer: the reducer folds every `TurnEvent` as proof
of serving and every `transportError` through the same classification `body_core::link` uses;
`useLink` probes once per summon; and it re-probes every `LINK_RECHECK_MS` (5 s) only while the
overlay is visible and the link is not ready. A rejected probe changes nothing but `probing`, and
the dot never claims more than the brain proved: `unknown` is a real state with its own colour, and
`degraded` (the brain answered, but is not serving) is never `down` (nothing answered).

## The Tauri shell

`src-tauri/` is a tray plus a hidden always-on-top window. The global hotkey (`os_windows`) toggles
the window and emits the `cortex:activate` Tauri event, which `main.tsx` re-dispatches as the DOM
event the overlay listens on; in a plain browser `main.tsx` self-summons instead.

- **`converse(session_id, text, channel)`** (`converse.rs`) drives one `BrainSeamClient` turn and
  streams each event to the webview over a Tauri `Channel`, serialising every `TurnEvent` and
  `TransportError` to a `WireMessage` (`{ event }` or `{ error }`) that matches the TypeScript
  `WireMessage` in `tauriBridge.ts` field for field: tag `kind`, camelCase, so a confirm request is
  `{ kind: "confirmRequest", confirmId, toolName, argumentsJson, reason }` and the brain closing it
  unanswered is `{ kind: "confirmResolved", confirmId, outcome }` (ADR-0022). A `TransportError`
  has its own `kind` (`connection`, `rpc`, `protocol`, `timeout`). For the turn's duration the
  command parks a decision sender in the managed `ConfirmRoute` state, one slot, at most one turn
  running at a time.
- **`confirm_response(confirm_id, approved)`** (`confirm.rs`, ADR-0022) pushes the user's answer
  into that slot. An absent or closed route is silently ok: an unanswered confirm is denied
  brain-side by timeout, so a late answer is harmless.
- **The session commands** (`sessions.rs`, ADR-0021): `list_sessions(limit)` and
  `session_messages(session_id)` return `Vec<WireSummary>` and `Vec<WireMessage>`; `rename_session`,
  `delete_session` and `set_session_pinned(session_id, pinned)` map success to `()`. The reads are
  retried with backoff; the writes make one attempt, not being repeatable.
- **`check_link()`** (`link.rs`) returns `body_core::probe_link`'s answer as `{ state, detail }`. It
  cannot fail on purpose: an unreachable brain, a bad address and a non-ASCII token are all `down`
  with the reason, a failed probe being an answer about the brain rather than an error.
- **The reminder commands** (`reminders.rs`, ADR-0025): `list_due_reminders()` returns
  `Vec<WireReminder>`, and `ack_reminder(reminder_id, fired_at_unix_ms)` returns a `bool` that is a
  state report rather than a failure. The list is retried; the ack is not.
- **The read transport** (`brain.rs`, ADR-0024). `connect()` builds a
  `body_core::RetryingTransport<BrainSeamClient, TokioSleeper, ShellRandomness>` over
  `BrainSeamClient::connect_lazy_with_token`, a lazy channel that never fails at construction and
  reconnects on demand. `TokioSleeper` and `ShellRandomness` are the real `Sleeper` and
  `Randomness`, kept in the untested shell so the retry logic stays in `body_core`. Which
  calls may be retried is decided by the `RetryPlan` in `body_core` and is not configurable here.
  `connect()` reads that plan once and hands the one value to both halves it governs, the transport
  that enforces the per-attempt deadline and the client that announces it as `grpc-timeout`.
  `converse` keeps its eager dial but wraps it in `retry_with`, so a turn started against a briefly
  down brain retries the dial while a turn that fails after its first event stays terminal. A
  turn's length is unbounded; its silence runs under the three turn gaps below.
- **`body_server.rs`** (ADR-0023, ADR-0025) binds `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`,
  declared once as `DEFAULT_BODY_PORT` and tied by `scripts/crosscheck.py` to every other file that
  states it), reads `CORTEX_SEAM_TOKEN` and `CORTEX_TOAST_APP_ID`, and serves `body_rpc`'s
  `body_service` on Tauri's async runtime with the audio backend, the toast backend, a
  screen-capture backend, whether capture receipts are on, and the token. The real
  `WindowsScreenCapture` is wired only when `CORTEX_HOST_CAPTURE=1` and the setup call that hid the
  overlay's own window from capture succeeded; on either failure it wires `DeniedScreenCapture`,
  which answers `PermissionDenied` to every `CaptureScreen`. Both conditions are required, because
  a capture including the overlay is a self-injection loop: the overlay is always on top and
  opaque, so the prompt, the prior reply and any confirm card would be read back as screen content.
  `CORTEX_HOST_CAPTURE_NOTIFY=0` turns off the body-authored receipt, and a non-windows build logs
  and does nothing. Nothing on this path has ever touched a real screen (`docs/runbooks/vision.md`
  has the check nothing else stands in for, capturing while the overlay is visible).

**Config** (shell only): `CORTEX_HOTKEY` (chord, default `ctrl+alt+space`),
`CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`), `CORTEX_BODY_ADDR` (the `BodyService`
bind, default `127.0.0.1:50151`), `CORTEX_SEAM_TOKEN` (empty means the validator passes everything
through), `CORTEX_TOAST_APP_ID` (the `AppUserModelID` the reminder toast is attributed to, default
`dev.cortex.body`), and the retry settings (ADR-0024) `CORTEX_BRAIN_RETRY_ATTEMPTS` (3),
`_BASE_MS` (200), `_MULTIPLIER` (2), `_MAX_MS` (2000), plus `CORTEX_BRAIN_PROBE_BUDGET_MS` (1000),
the ceiling on a `Health` probe's whole run, and the two per-attempt deadlines
`CORTEX_BRAIN_PROBE_DEADLINE_MS` (250) and `CORTEX_BRAIN_CALL_DEADLINE_MS` (5000). At the defaults
the budget leaves the probe two of the reads' three attempts, so the dot resolves within 700 ms and
still spends one real retry on a restarting brain. The turn's three settings bound silence rather
than a call (ADR-0024 decisions 19 and 20, ADR-0069). `CORTEX_BRAIN_TURN_FIRST_GAP_MS`
(`DEFAULT_TURN_FIRST_GAP_MS = 600000`) and `CORTEX_BRAIN_TURN_IDLE_GAP_MS`
(`DEFAULT_TURN_IDLE_GAP_MS = 14400000`) bound the turn's own silence before its first event and
between two, counting each heartbeat as silence; the second is sized by a delegated subtask's
admission wait and runs. `CORTEX_BRAIN_TURN_HEARTBEAT_GAP_MS` bounds the stream's silence,
heartbeats included (`DEFAULT_TURN_HEARTBEAT_GAP_MS = 120000`), so a dead brain shows in minutes.

**Invariants.**

- Components depend on the `BrainBridge` port, not on Tauri, so the whole overlay runs in a browser
  and is covered to 100%. The Tauri glue is the single untested edge (ADR-0011 decision 6).
- Every `BrainBridge` implementation CI can run is driven over the one shared check list: a new
  implementation adds a case to `bridgeContract.test.ts` rather than a suite of its own. The wire
  types on both sides are one contract, so `types.ts`, `tauriBridge.ts`, `converse.rs`,
  `confirm.rs`, `sessions.rs`, `reminders.rs` and `link.rs` change together.
- Nothing the overlay displays is ever linkified, and reminder text is why it matters: it is the
  one string on screen no output guardrail inspected (ADR-0015 filters streamed replies, not store
  rows). `DueReminder.tainted` badges the untrusted ones and the text stays a plain text node. A
  card's controls are app chrome with fixed labels, beside that text and never wrapping it.
- Whatever is hidden from a reader is hidden from the tab key, in the same frame and from the same
  call. Three things stay mounted while off screen: the dismissed panel, the view being left for
  the length of its morph, and the console tab not showing. Each spreads `withdrawn(away)`
  (`overlay/withdrawn.ts`), which writes `aria-hidden` in both directions and `inert` in one, and a
  fourth such place spreads the same call or it is a defect. The `inert=""` string form is
  deliberate: React 18 writes a string attribute straight through and drops a boolean one with a
  warning (ADR-0052 decision 2).
- A scroll container reserves its scrollbar and never borrows the content's width. All seven
  (`.history`, `.switcher`, `.reminders`, `.thoughts-body`, `.confirm-draft`, `.rows` and the
  composer's `.field`) set `scrollbar-gutter: stable`. Paying for that rail (`--rail`, 6px) takes
  one of two shapes: subtract it where there is inline-end padding to spare (`.history` and `.rows`
  at 16px, `.switcher` and `.reminders` at 6px), or add a rail of padding where there was none
  (`.thoughts-body`, `.confirm-draft` and `.field`, now 12px). An eighth container picks the right
  one, or it jumps sideways the first time it fills up. The gutter is inline-end only, so nothing
  may grow along the other axis. A container holding text it did not author breaks long tokens
  instead (`overflow-wrap: anywhere`), and `whisper/front.ts` chunks a run of non-whitespace longer
  than 24 letters, a whispered reply's word boxes being `white-space: pre` (ADR-0037 decision 6).
- `.history` sets `overflow-anchor: none`, Chromium's scroll anchoring being a third decider of a
  number `overlay/useLogScroll.ts` and `overlay/logRoll.ts` already own. A future scroll container
  holding rolling content needs the same line, or its own reason not to.
- A theme change crosses the whole surface together. `applyTheme` sets `data-swapping` on the root
  for `THEME_SWAP_MS`, and `[data-swapping] *` puts one transition on everything for that window.
  The attribute goes on before the tokens, a transition starting from the after-change style, and
  comes off on a timer, removing it in the same task leaving nothing to ease. The number also
  reaches the root as `--theme-swap`, so the two cannot drift apart.
- A gradient is not a colour. `--accent` is a `linear-gradient`, so `color: var(--accent)` and
  `border: 1px solid var(--accent)` do not compute and are set to `unset`; giving a gradient to a
  colour needs a solid token (`--spark`) or `background-clip: text`.
- The shell stays thin. Every decision with a branch in it (accelerator mapping, wire translation)
  lives in the covered `body_core` and `body_rpc`, and the app holds wiring only, which is what
  keeps the coverage exclusion safe. `src-tauri` is its own Cargo workspace, excluded from
  `body/Cargo.toml`, and never enters CI; its `.rs` files are still under the 300-line cap, which
  `linecap.py` scans in every tree.

**Dependencies.** Frontend: React 18, Vite 5, Vitest, `@tauri-apps/api`. Shell: `tauri` 2
(`tray-icon`), `body-core` and `body-rpc`, `os-windows` (`cfg(windows)`), `serde`, `futures-util`,
`tonic`, `tokio` (`sync`, `net`, `rt-multi-thread`, `time`) and `tokio-stream`. Bring-up:
[body-overlay](../runbooks/body-overlay.md).
