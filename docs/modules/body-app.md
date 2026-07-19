# body/app (`cortex-body`, overlay + Tauri shell)

**Purpose.** The host-native body app (ADR-0011): a React + Vite overlay summoned by a global
hotkey, talking to the brain over the `Converse` seam, wrapped in a thin Tauri shell. It is its
own project *outside* the gated `body` Cargo workspace (`body/Cargo.toml` excludes it) so
`just check` never builds Tauri. The **frontend** is gated at 100% (Vitest); the **Tauri Rust
shell** is host-validated on Windows, like the brain's real adapters.

Two halves meet at one seam. That seam is the typed `BrainBridge` port:

- **Frontend** (`src/`, gated). Pure logic first: the theme system (`theme/`), the activity mark
  (`mark/`: `bubble.ts` is the pure geometry, `marks.ts` the style registry, `useMarkClock.ts` the
  frame clock, ADR-0031), the appearance record (`overlay/usePreferences.ts`: hydrates the theme
  and mark from the brain once and writes each change back optimistically, ADR-0032), the panel's
  vertical geometry and the motion into it (`overlay/usePanelMotion.ts` owns `bottom` and
  `max-height` as inline styles; `overlay/useViewTransition.ts` names the view being left behind
  long enough to fade it, ADR-0033/ADR-0034), the overlay state
  machine (`overlay/overlayState.ts` is a pure reducer over a `Mode` = hidden/panel/orb/preview,
  with the session-switching helpers split into `overlay/sessionState.ts` for the line cap),
  and the controller hook (`overlay/useOverlay.ts`). Components (`components/`) depend only on the
  `BrainBridge` port and a `cortex:activate` DOM event (never on Tauri), so they run and test in a
  plain browser. That activation is a **pending request, not a moment** (`overlay/activation.ts`):
  it is recorded before it is announced, and the app takes any outstanding one when its listener
  attaches. Passive effects flush after paint, so both the browser self-summon and a hotkey press
  during a cold start land before anything is listening; measured at 2ms early on load, which is
  why `npm run dev` used to come up to an empty stage. Look and feel is [overlay-ux.md](../design/overlay-ux.md) (colour = activity,
  sleek at rest, light + dark).
- **Tauri shell** (`src-tauri/`, host-validated). Tray + hidden always-on-top window; the global
  hotkey (`os_windows`) toggles the window and emits `cortex:activate`; the `converse` command
  drives one `BrainSeamClient` turn and streams each event to the webview over a Tauri `Channel`.
  It also **hosts the `BodyService` gRPC server** (Slice 9, ADR-0023, opening the first brain→body
  direction), so the brain can dial the host for OS actions like read/set system volume.

**Public contract.**

- **The `BrainBridge` port** (`src/bridge/types.ts`): `converse(sessionId, text, sink) →
  Cancellation`, the read-only `listSessions(limit)` / `sessionMessages(sessionId)` (ADR-0021),
  the user-driven `renameSession(sessionId, title)` write (ADR-0021 management addendum; `""`
  clears the override, and `useOverlay` re-lists after it resolves so the switcher shows the new
  label), the user-driven DESTRUCTIVE `deleteSession(sessionId)` write (ADR-0021 delete addendum;
  fired only after the switcher row's local "are you sure" confirm, then `useOverlay` drops the row
  and re-lists on success; deleting the currently-open chat first tears down its in-flight turn and
  then falls back to a fresh new chat so a deleted transcript is never rendered), the user-driven
  `setSessionPinned(sessionId, pinned)` write (ADR-0021 pinning addendum; a per-row pin toggle
  fires it, then `useOverlay` re-lists so the switcher re-groups, a pinned chat lifting above the
  recency window with a filled-pin indicator; `SessionSummary` carries a `pinned` bool the brain
  lists first), plus the
  `TurnEvent` / `TransportError` / `SessionSummary` / `SessionMessage` types, the
  TS mirror of the Rust `body_core` values. Three implementations: `TauriBridge` (real, over IPC),
  `DemoBridge` (canned stream + canned chats for `vite dev`), `FakeBridge` (tests). Only
  `tauriBridge.ts`, `demoBridge.ts`, and `main.tsx` are coverage-excluded (the un-gated glue);
  everything else is 100% line + branch. `useOverlay` owns the `session_id` (minted per new chat)
  and the store-backed chat list (loaded on mount + after each turn; a chat's history loads on
  select/cycle). The open-chat **header title** is the switcher's own `SessionSummary.title` for
  that chat, read from the loaded `state.sessions` by `openSession`/`adoptSession` (`headerTitle` in
  `sessionState.ts`), so the header and the switcher row agree by construction (a stored generated
  title, a user rename, or the brain-side truncation bound, ADR-0021 header-title addendum) instead
  of re-deriving the header locally; only a chat absent from the loaded list (a reminder deep-link
  past the recency window) falls back to the local `deriveTitle`. On cold start the first list
  arrival adopts the most recent chat into the
  still-hidden overlay (ADR-0021 addendum): the `adoptSession` reducer action hydrates like
  `openSession` but preserves `mode` and no-ops unless the overlay's `touched` flag is still
  false (set by open/submit/new-chat/cycle, so a racing user action wins; a `seq`/`messages`
  proxy cannot tell an explicit new chat from a pristine boot); the hook attempts it once per
  mount. The port also carries reminder pull delivery (ADR-0025): `listDueReminders()` /
  `ackReminder(reminderId)` plus the `DueReminder` mirror, and the connection probe
  (ADR-0011 addendum): `checkLink()` plus the `LinkState` / `LinkStatus` mirrors of
  `body_core::link`. It also carries the user's settings record (ADR-0032):
  `getPreferences()` / `setPreference(key, value)` plus the `Preference` mirror, opaque pairs the
  overlay reads once at startup (`usePreferences`) and writes one at a time on every appearance
  change. An unrecognised key belongs to another surface and is ignored; an empty value clears a
  key, which is how "follow the system" is stored for the theme.
- **The capture switch and the overlay's self-exclusion** (`body_server.rs`, ADR-0029). The
  shell wires the real `WindowsScreenCapture` only when `CORTEX_HOST_CAPTURE=1` **and** the
  setup call to `exclude_from_capture` on the overlay's own window succeeded; on either failure
  it wires `DeniedScreenCapture`, which answers `PermissionDenied` to every `CaptureScreen`.
  Both conditions are required because a capture that includes the overlay is not a degraded
  picture but a **self-injection loop**: the overlay is always-on-top and opaque, so its
  contents (the user's prompt, the prior reply, any confirm card) would be re-ingested as screen
  content on the next capture, laundering model output back into untrusted model input.
  `CORTEX_HOST_CAPTURE_NOTIFY=0` silences the body-authored receipt. **Host-validated only, and
  not yet run:** nothing on this path has ever touched a real screen, and the self-exclusion in
  particular has no CI-visible failure mode, which is why capturing while the overlay is visible
  is the one check `docs/runbooks/vision.md` says nothing else can stand in for.
- **The screen-capture indicator** (`state.capturing` + `components/CaptureDot.tsx`,
  ADR-0029). The reducer sets `capturing` when a `toolActivity` event names
  `CAPTURE_SCREEN_TOOL` (`"capture_screen"`, matched by name because the event already carries
  it and a second seam field would be one more place the two ends could disagree), and clears it
  only when the turn ends, on completion or failure alike. It therefore stays lit for the rest
  of the turn rather than blinking past with the tool chip, because the fact the user is owed is
  "the assistant went for my screen during this reply", not "a tool ran for a moment". This is
  a **consent surface** and part of why the capture tool ships without an approval card: the
  dot renders only when it means something and carries a fixed accessible label saying exactly
  what the seam proved, which is *"The assistant asked to look at your screen during this
  reply"*. **"asked to look", not "looked":** the chip is emitted just before the dispatch, so
  the flag is set for a capture the host refused (`CORTEX_HOST_CAPTURE` unset is the shipping
  default), one whose self-exclusion failed closed, one the body never answered, and a gated one
  the user declined. No outcome crosses the seam, so the stronger claim would be false in every
  one of those cases; an outcome-driven indicator needs a seam change and is a recorded
  deferral (`docs/refinements/vision.md`). The body fires its own OS notification independently; this is the half the user is
  already looking at.
- **The connection indicator** (`overlay/linkState.ts` + `overlay/useLink.ts` +
  `components/LinkDot.tsx`, ADR-0011 addendum). `state.link` is a `LinkView { state, detail,
  probing }`: `state` is the last thing the brain **proved** (`ready` | `degraded` | `down`,
  plus the overlay's own `unknown` before anything is asked) and `probing` is the overlay's own
  fact, kept separate so a probe never overwrites what was last true. `describeLink` renders the
  pair as `{ tone, busy, label }`, keeping the last known colour while a probe is out (a
  reconnect neither flashes green nor forgets it was red) and refusing to look busy for the
  routine probe on an already-ready link. Three sources keep it current, and **none is a
  liveness timer**: the reducer folds every `TurnEvent` as proof of serving and every
  `transportError` through the same classification `body_core::link` uses (`connection` → down,
  `rpc`/`protocol` → degraded, because the brain answered); `useLink` probes once per summon;
  and it re-probes every `LINK_RECHECK_MS` (5 s) **only while the overlay is visible and the
  link is not ready**, stopping the moment it answers ready. The re-check is an interval keyed
  on "visible and unhealthy" rather than a timer re-armed per answer, because a probe answering
  inside one React batch never renders the in-flight flip and would silently end the recovery
  after one retry; an in-flight ref keeps a slow probe from overlapping a tick. A **rejected**
  probe (the IPC itself, not the brain) leaves the last known state and only clears `probing`.
- **The summon latch** (`overlay/useSummonEffect.ts`): `useSummonEffect(visible, effect)` runs
  its effect once per summon, on the rising edge of `mode !== "hidden"`, re-arming on hide. It
  absorbs StrictMode's double-fired mount effect and does not re-run when the overlay changes
  shape while staying visible (panel to orb to preview). Three things ride it: the reminder pull
  (ADR-0025), the connection probe, and the **chat-list refresh** (ADR-0021 addendum, joining
  the mount and turn-completion triggers, both of which can be days old for a tray-resident
  body, and giving a list that failed while the brain was down a way back).
- **The reminder pull loop** (`overlay/useReminders.ts`, ADR-0025 addendum):
  `useReminders(bridge, mode, dispatch)` returns the dismisser `useOverlay` re-exports as
  `dismissReminder`. The pull is latched on the **rising edge of visibility** (`mode !== "hidden"`,
  re-arming on hide), so the resident tray app reads once per summon rather than on mount into a
  window nobody is watching, and StrictMode's double-fired effect stays one read. Dismissal is
  **optimistic**: `reminderDismissed` drops the card immediately and the ack rides the bridge
  unawaited, so a lost ack simply leaves the reminder deliverable for the next open, which is what
  makes the transport's unretried `ack_reminder` safe. A failed pull dispatches nothing, leaving
  the previous cards in place (the chat list's rule). `remindersLoaded` replaces the list
  wholesale; the brain is the authority on each open. A card also offers its **origin chat**
  (ADR-0025 origin addendum): `DueReminder.sessionId` through `Panel`'s existing
  `onSelectSession`, so a reminder and the switcher load a chat by the same path. Opening never
  acks (an ack destroys the reminder, navigation does not), and the control is *absent* for a
  session-less row (`""`) or for the chat already on screen, where it would cancel that chat's
  running turn to arrive where it already is.
- **The panel's views** (`components/Panel.tsx` + `ChatView.tsx` + `PanelView.tsx` +
  `SettingsView.tsx` + `ShortcutsView.tsx`, ADR-0034): `Panel` is a router over three views of one
  window, not a window with sheets over it. Only the active view is in the layout flow, so it alone
  decides the height the panel eases to; the view being left is held for one morph, lifted out of
  flow, and faded out over the one arriving; the chat is never unmounted (a half-typed draft and the
  history's scroll position survive a trip to settings). `usePanelMotion` re-centres on a view change
  and pins the bottom edge in between, so growth inside the chat leaves the composer alone.
  `components/Collapse.tsx` gives the switcher list and the reminder stack their own height
  animation. The two-part contract between it and the panel is `overlay/morph.ts`: `data-morphing`
  on the section makes the panel leave the height alone, and a bubbling `cortex:morphend` when it
  clears is the panel's only word that a section rolling *open* has finished, since that changes no
  state and so triggers no render of its own.
- **The confirmation card** (`components/ConfirmCard.tsx` + `components/draftValue.ts`,
  ADR-0022): the gated call's `argumentsJson` as key/value rows, shown verbatim because what is
  approved is what runs (a malformed one falls back to the raw string). `formatDraftValue`
  renders one value: a string is untouched, so newlines stay newlines; an object or array becomes
  indented `key: value` lines, which is what lets an attachment's content read as a file instead
  of as escaped JSON. It knows JSON shapes and never a tool's schema. The draft block caps at
  `42vh` and scrolls, so a long draft cannot push Approve and Deny out of view.
- **The reasoning surfaces** (`components/Message.tsx` + `overlay/overlayState.ts`, ADR-0020): a
  reply's `"thinking"` statuses drive two affordances off the reducer's `statusState`. While the
  turn streams, the live chip bobs (`chip-think`) with the latest reasoning delta; the reducer
  also concatenates every thinking delta into `Message.thoughts`, so once the reply settles the
  chip drops and a collapsed `<details>` "Thoughts" disclosure above the bubble holds the whole
  trace (its `›` marker rotating open, resting chrome only since the thinking is done). Each delta
  is already guardrail-scrubbed brain-side (ADR-0020 addendum), so the section shows nothing the
  live chip did not and opens no channel the reply-side guardrail never inspected; like everything
  else the overlay renders it is **never linkified** (a plain text node). `thoughts` is in-memory
  only, dropped when the turn's message leaves `state.messages`: reasoning is never persisted
  (ADR-0020), so `hydrate` gives a reloaded chat's replies `""` and no disclosure.
- **The `converse` command** (`src-tauri/src/converse.rs`): `converse(session_id, text, channel)`.
  It serialises each `TurnEvent` / `TransportError` to a `WireMessage` (`{ event }` | `{ error }`)
  that matches the TS `WireMessage` in `tauriBridge.ts` field for field (tag `kind`, camelCase, so
  a mid-turn confirm request is `{ kind: "confirmRequest", confirmId, toolName, argumentsJson,
  reason }` and the brain closing it unanswered is `{ kind: "confirmResolved", confirmId,
  outcome }`, ADR-0022). For the turn's duration it parks a decision sender in the managed
  `ConfirmRoute` state (`src-tauri/src/confirm.rs`, one slot, as at most one turn runs at a time);
  the matching receiver stream feeds `BrainTransport::converse`'s `decisions` parameter and is
  cleared when the event loop ends.
- **The `confirm_response` command** (`src-tauri/src/confirm.rs`, ADR-0022):
  `confirm_response(confirm_id, approved)` pushes the user's answer into the `ConfirmRoute`
  slot, from where it reaches the open turn's request stream. An absent or closed route is
  silently ok (never a webview error) because an unanswered confirm is denied brain-side by
  timeout (fail-closed), making a late answer a harmless no-op.
- **The session-read commands** (`src-tauri/src/sessions.rs`, ADR-0021): `list_sessions(limit)` and
  `session_messages(session_id)` are unary calls returning `Vec<WireSummary>` / `Vec<WireMessage>`
  (camelCase, matching the TS `SessionSummary` / `SessionMessage`; `WireSummary` carries `pinned`,
  ADR-0021 pinning addendum). The session **writes** `rename_session`, `delete_session`, and
  `set_session_pinned(session_id, pinned)` (pinning addendum) live here too, each a unary call
  mapping success to `()`; a dial/RPC failure is the command's `Err`, which the bridge's `.catch`
  handles. They dial through `seam::connect()` (below), so a *transient* unreachable brain is
  retried with backoff before the error surfaces (ADR-0024), except the writes, which are not
  repeatable and so make exactly one attempt.
- **The `check_link` command** (`src-tauri/src/link.rs`, ADR-0011 addendum): dials
  `seam::connect()` and returns `body_core::probe_link`'s answer as `{ state, detail }`
  (the state names are `LinkState::as_str`). **Infallible on purpose**: an unreachable brain is
  `down` with the dial failure, and even a bad `CORTEX_BRAIN_ADDR` or a non-ASCII seam token is
  `down` with the reason, because a failed probe is an answer about the brain rather than an
  error about the command. Riding the resilient transport makes the probe the reconnect attempt
  too (`health` is retried, ADR-0024).
- **The reminder commands** (`src-tauri/src/reminders.rs`, ADR-0025): `list_due_reminders()` and
  `ack_reminder(reminder_id)` are unary calls returning `Vec<WireReminder>` (camelCase, matching
  the TS `DueReminder`) and the ack's `bool`, which is a state report ("nothing to clear"), never
  a failure. They dial through `seam::connect()` like the session reads, so the list is retried
  with backoff and the ack is not (ADR-0025 transport addendum). A brain with no schedule backend
  answers empty / `false` rather than a status, so neither command has a mode for it.
- **The resilient read transport** (`src-tauri/src/seam.rs`, ADR-0024): `connect()` builds a
  `body_core::RetryingTransport<BrainSeamClient, TokioSleeper, ShellRandomness>` over
  `BrainSeamClient::connect_lazy_with_token`
  (a lazy channel that never fails at construction and reconnects on demand), reading the address +
  seam token + retry knobs from env. `TokioSleeper` is the real `Sleeper` (`tokio::time::sleep`), the
  one timer effect, and `ShellRandomness` the real `Randomness` (a `RandomState`-seeded jitter draw,
  `CORTEX_BRAIN_RETRY_JITTER=off` pinning it to the deterministic schedule), both kept in the
  un-gated shell so the retry *logic* stays gated in `body_core`. `policy_from_env()` (the shared
  `RetryPolicy` builder) is `pub` so `converse` reuses it for its dial, and `plan_from_env()`
  wraps it in the `RetryPlan` `connect()` passes: the same read schedule, plus
  `CORTEX_BRAIN_PROBE_BUDGET_MS` as the ceiling on a `Health` probe's patience. Which calls may
  be retried at all is *not* configurable here and deliberately so; that is the gated
  `RetryPlan` gate, decided by what each seam method does. The read commands use `connect()`;
  `converse` keeps its **eager** dial but wraps it in `retry_with` (ADR-0024 addendum), so a turn
  started against a briefly-down brain retries the *dial* (safe: the non-idempotent turn has not
  begun) while a turn that fails after its first event stays terminal (decision 2). It first runs
  the lazy constructor as a synchronous config gate, so a bad URI or non-ASCII token fails fast
  instead of being retried for the whole budget.
- **The `body_server` module** (`src-tauri/src/body_server.rs`, ADR-0023/0025): `start()` (`cfg(windows)`)
  binds `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`), reads `CORTEX_SEAM_TOKEN` and
  `CORTEX_TOAST_APP_ID` (default `dev.cortex.body`, the app's Tauri identifier), and serves
  `body_rpc::body_service(WindowsAudioControl::new(), WindowsNotify::new(&app_id), &token)` on
  Tauri's async runtime
  (`tauri::async_runtime::spawn`); a non-windows stub logs and does nothing. Wired into `run()`'s
  `.setup()`. All the coverable translation (`OsService` + the `SeamTokenValidator`) lives in
  the gated `body_rpc`; this module is thin un-gated glue, host-validated on Windows.
- **The activate seam**: the hotkey and tray emit the `cortex:activate` Tauri event; `main.tsx`
  (in-shell only) re-dispatches it as the DOM event the overlay listens on. In a plain browser,
  `main.tsx` self-summons instead.
- **Config** (shell only): `CORTEX_HOTKEY` (chord, default `ctrl+alt+space`),
  `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`), `CORTEX_BODY_ADDR` (the `BodyService`
  bind, default `127.0.0.1:50151`), `CORTEX_SEAM_TOKEN` (empty = the validator is a
  pass-through), `CORTEX_TOAST_APP_ID` (the `AppUserModelID` the reminder toast is attributed
  to, default `dev.cortex.body`), and the read-transport retry knobs (ADR-0024)
  `CORTEX_BRAIN_RETRY_ATTEMPTS` (default 3), `_BASE_MS` (200), `_MULTIPLIER` (2),
  `_MAX_MS` (2000), plus `CORTEX_BRAIN_PROBE_BUDGET_MS` (1000), the ceiling the `Health`
  probe's schedule is trimmed to so raising the read knobs cannot slow the connection
  indicator's verdict. At the defaults it does not bind (the schedule's worst case is 600 ms).

**Invariants.**

- Components depend on the `BrainBridge` port, not Tauri, so the whole overlay is browser-runnable
  and 100%-gated; the Tauri glue is the single un-gated edge (ADR-0011 addendum).
- The wire types on both sides of the seam are one contract: change `types.ts`,
  `tauriBridge.ts`, and `converse.rs` / `confirm.rs` / `sessions.rs` / `reminders.rs` /
  `link.rs` together.
- **The indicator never claims more than the seam proved.** `unknown` is a real state with its
  own colour, `degraded` (the brain answered and is not serving) is never collapsed into `down`
  (nothing answered), and a rejected probe changes nothing. The v1 dot was removed for being
  always green; this one is allowed to be uninformative but never wrong.
- **Nothing the overlay displays is ever linkified**, and reminder text is why it matters: it is
  the one string on screen that no output guardrail inspected (ADR-0015 filters streamed replies,
  not store rows), so a URL in it has had no redaction pass. `DueReminder.tainted` badges the
  untrusted ones; the text itself stays a plain text node. The card's controls are all app chrome
  with fixed labels, sitting *beside* that text and never wrapping it, so nothing a stranger
  wrote can become the label on a working button.
- The shell stays thin. Every branchy decision (accelerator mapping, seam translation) lives in
  the gated `body_core` / `body_rpc`; the app holds wiring only, which is what keeps the coverage
  exclusion safe (ADR-0011 risk: coverage creep).
- `src-tauri` is its own Cargo workspace, excluded from `body/Cargo.toml`; it never enters CI. Its
  `.rs` files are still under the 300-line cap (linecap scans every tree).

**Dependencies.** Frontend: React 18, Vite 5, Vitest (the gate), `@tauri-apps/api` (the real
bridge). Shell: `tauri` 2 (`tray-icon`), `body-core` + `body-rpc` (the gated crates), `os-windows`
(`cfg(windows)`, provides `WindowsAudioControl`), `serde`, `futures-util`, `tonic` (serving the
`BodyService`, ADR-0023), `tokio` (`sync` for the ADR-0022 confirm channel; `net` +
`rt-multi-thread` for the ADR-0023 `BodyService` server; `time` for the ADR-0024 retry
backoff sleeper) + `tokio-stream` (`net` for
`TcpListenerStream`, the `BodyService` incoming, ADR-0023; its receiver wrapper also carries the
ADR-0022 confirm decision channel). Bring-up + validation:
[body-overlay.md](../runbooks/body-overlay.md).
