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
  vertical geometry and the motion into it (`overlay/usePanelMotion.ts` drives
  `overlay/panelPlacement.ts` and its neighbours, which own `bottom` and `max-height` as inline
  styles; `overlay/useViewTransition.ts` names the view being left behind
  long enough to fade it, ADR-0033/ADR-0034), the overlay state
  machine (`overlay/overlayState.ts` is a pure reducer over a `Mode` = hidden/panel/orb/preview,
  with two halves split off for the line cap and re-exported from it, so components import one
  module: the session-switching helpers in `overlay/sessionState.ts`, and the turn fold, meaning
  what a `Message` is and how one `Converse` turn's events apply, in `overlay/turnState.ts`),
  and the controller hook (`overlay/useOverlay.ts`, which likewise hands the chat catalog to
  `overlay/useSessionCatalog.ts` and spreads it back in, keeping one flat controller).
  Components (`components/`) depend only on the
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
- **Where both indicators sit** (`components/ChatView.tsx` + the `.head` block of
  `src/overlay.css`, 2026-07-20). The chat header is title, then the link dot and the capture
  ring, then the four buttons. The two indicators are **one row of state and move together**: the
  ring renders only mid-capture, so splitting them would leave it alone beside the title as the
  one mark there, appearing and vanishing per turn, while at the head of the button cluster the
  pair reads as "what the panel currently is" against "what you can do to it". Neither carries an
  optical margin any more; they ride the header's own 10px gap. The title, now starting the row,
  carries **`margin-left: 14px`, putting its first glyph 31px from the panel's edge**, which is
  the number the panel's 28px corner asks for: the title's centre is already 31px below the top
  edge, so the text starts on the corner's 45-degree diagonal, as far from the side of the panel
  as from the top of it (on the bare padding it is 17px in against 31px down), and 31px
  is where a switcher row's title already starts (an assistant bubble's glyph is at 32px, the
  composer's text at 33px, all measured in Chromium at the panel's 560px). The rule is
  `.head > .title:first-child`, scoped that way because every other view's header opens with the
  back button, which supplies its own inset. `.title` keeps `flex: 1` with `overflow: hidden`, so
  at a narrow panel the title ellipsises and the buttons keep their 30px (checked at a 368px and
  a 294px panel). What is left once the title has shrunk away is a fixed chain: 14px of inset, four
  30px buttons, six 10px gaps, the 7px dot, the 7px ring while a capture is lit, and the header's
  32px of padding, so with the ring showing the row wants a 240px panel. Under that (a viewport
  below 261px, since the panel is `min(560px, 92vw)`) the cluster starts spending the right
  padding: measured at a 239px panel, the last button sits 14.2px from the edge instead of 17px.
  The body's overlay window is 640px wide and gives a 560px panel, so no window it opens reaches
  this; it is recorded as the edge of the row rather than as a case to design for.
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
  `ConsoleView.tsx`, ADR-0034): `Panel` is a router over views of one window, not a window with
  sheets over it, and the views are `chat` plus one per **console** tab
  (`console:appearance` | `console:shortcuts`, ADR-0035 decision 1). Only the active view is in the
  layout flow, so it alone
  decides the height the panel eases to; the view being left is held for one morph, lifted out of
  flow, and faded out over the one arriving; the chat is never unmounted (a half-typed draft and the
  history's scroll position survive a trip to the console). Naming the TAB in the view is what makes
  switching tabs the same resize-and-recentre morph as opening the console, with the cross-fade
  already in place carrying it: measured, appearance 411px and the shortcut list 571px, both edges
  moving 80px over about 150ms and back. Two panes that share their chrome cross without the rise:
  `Panel` marks both `.view.swap` when the view being left is another console tab, which zeroes the
  `--rise` both view keyframes read, so the header and the strip hold still (traced pixel-identical
  in both panes) while only the content changes. It is a distance and not a second pair of
  keyframes because the mark is dropped when the crossing ends, and changing an animation's NAME
  restarts it, which replayed the rise on a pane that had already arrived. Whichever pane is on its
  way out is `aria-hidden`, chat or console, so two mounted panes are never two announced ones. `usePanelMotion` is the WHEN of the panel's
  geometry (every render, a window resize, and both ends of a roll) over three files that are the what:
  `overlay/panelGeometry.ts` is the pure arithmetic (the centre, the ceiling clamp, the max height
  in whole pixels, since that one number is both written to the DOM and predicted against and the
  two must not round apart, and a duration paced by the distance the further-travelling edge
  covers, 120ms floor and 380ms
  ceiling, because one fixed duration cannot serve both a streamed line and a whole view changing,
  which the placement pairs with resuming rather than restarting a move whose destination a render
  did not change, so a token landing mid-ease shortens that ease instead of deferring it);
  `overlay/panelMemory.ts` is what the panel remembers between placements and how it reads its own
  box (heights off `offsetHeight`, which the summon's scale transform does not touch, the bottom
  edge off the rect, which it does not either); `overlay/panelPlacement.ts` decides where the panel
  belongs; `overlay/panelRide.ts` is the slide it makes alongside a section's roll. The rules: a
  summon centres the panel on what it arrives with for the length of its own 0.44s pop (so the
  reminders pulled on that same rising edge are the panel appearing with them, not growth
  afterwards) and stops the moment the user touches it, a press or a key being the difference
  between content the panel arrived with and a section they opened and will close again;
  entering another view centres it, coming back to the chat restores the edge it was
  left at, and everything else pins the bottom edge, so growth inside the chat and a new chat (the
  same view with less in it) leave the composer alone. The pinned edge is kept UNCLAMPED and the
  ceiling is applied only on the way out to the DOM, which is what makes a grow-then-shrink round
  trip exactly reversible. `components/Collapse.tsx` gives the switcher list, the reminder stack and
  a reply's Thoughts trace
  their own height animation, the closing one filling forwards so no frame paints at the old size
  before React removes it, and committing that height by hand where nothing animates at all
  (`prefers-reduced-motion`, or a roll too small to see). The contract between it and the panel is
  `overlay/morph.ts`, which also holds the curve and the "too small to bother" threshold both sides
  share: `data-morphing` on the section makes the panel leave the height alone and carries the
  height the section is rolling to, which is what lets the panel take its bottom edge off the
  ceiling over that same roll (`MORPH_ROLL_MS`) instead of afterwards, capped at the height the
  panel is allowed to reach. A move of the panel's own still in the air when a roll starts is
  carried through it (in-flight height to where the roll will leave the panel, on the roll's clock)
  rather than cancelled, since cancelling hands the used height back to layout in one frame. Two
  bubbling events bracket the roll, and both exist because a roll is not always a render the panel
  sees: `cortex:morphstart` (dispatched once the attribute is set and the animation exists) is what
  lets the panel ride along with a section whose open state is owned locally, a reply's trace being
  the one that is, and `cortex:morphend` when the attribute clears is its only word that a section
  rolling *open* has finished, since that changes no state and so triggers no render of its own.
  Traced at 60Hz before the start event existed: a trace opened over its 300ms with the panel's
  `auto` height following it, and the panel, hearing only the end and placing itself from the
  geometry it remembered from before, snapped back to its old height for one frame and moved a
  second time. `usePanelMotion` therefore reads what it is placing FOR out of a ref assigned during
  the render rather than out of each handler's closure: the start arrives from inside a layout
  effect, before any passive effect of that render has re-subscribed.
- **The console** (`components/ConsoleView.tsx` + `AppearanceTab.tsx` + `ShortcutsTab.tsx` +
  `ThemeMini.tsx`, ADR-0032 + ADR-0035 decision 1): the panel's one non-chat view, a tab strip
  over the appearance choices and the complete shortcut list. State is a single
  `consoleTab: "appearance" | "shortcuts" | null` on the reducer, with three actions that say what
  each surface does: `toggleConsole(tab)` for the two openers in the hint strip (each owns its
  tab, so its own button closes the console and the other switches), the idempotent
  `openConsole(tab)` for the strip, and `closeConsole()` for Esc and the header chevron, which is
  why Esc now leaves in one press instead of unstacking two sheets. `CONSOLE_TABS` is exported
  beside the type because `Panel` walks it to mount tabs and `ConsoleView` walks it to draw the
  strip. The appearance tab maps over `THEMES` and `MARKS` rather than naming what ships, so both
  registries keep the plug-and-play property they claim: a theme previews itself through
  `ThemeMini` (a miniature panel built from that theme's own tokens, with Auto split diagonally
  between the two themes `resolveTheme(null, …)` answers with), and a mark style draws the real
  `BubbleMark` at 40px. The shortcut list is grouped, and each key is its own `<b>` cap carrying
  the same `icons.tsx` glyph the hint strip uses; the strip separates its own chords the same way,
  so `Shift`+`Return` reads as two keys on both surfaces. Focus travels with the view: the arriving
  pane's selected tab takes it (the strip that was clicked is inside the pane leaving, one morph
  from `display: none`, which would drop focus to the body), and the chat takes it back into the
  composer, whose `active` prop is "the panel is open AND no console tab is up". That is not
  decoration: a browser refuses to hide the focused element's ancestor from assistive tech, so
  without the handoff the `aria-hidden` on the pane being left is ignored and the tab just left
  stays in the tree as a second, equal console.
- **The chat's floor is the empty state** (`components/ChatView.tsx` + `src/overlay.css`, ADR-0035
  decision 12). The history's children sit in one column, `.log`, which carries a `min-height` of
  the empty state's measured height (185px: the mark, the invitation, the example chips and their
  padding), so replacing that invitation with a short user bubble and a thinking one cannot ease
  the panel down at the moment the chat starts. Two things about it are load-bearing and easy to
  undo by accident. The floor is on the **content** and never on `.history`, because a scroll box
  that will not shrink has nowhere to go when the switcher and the reminder stack are both open
  (76px of history at a 720px window) and takes the composer out past the panel's clipped edge;
  floored content simply scrolls. And the column is bottom-aligned, so the reserved height lands
  above the bubbles rather than under them, where `scrollTop = scrollHeight` would faithfully
  scroll the newest bubble out of sight to reach blank space. The empty state is unaffected by the
  alignment: `margin: auto` outranks `justify-content`, so it stays centred in whatever the column
  is. A third thing is load-bearing and looks like styling: the example chips are held to one row
  (`flex-wrap: nowrap`, shrinking to an ellipsis) because they are the only part of the invitation
  whose height depends on the panel's width, and one number can only be the floor while the thing
  it measures is one height. `Panel.test.tsx` pins the structure the stylesheet cannot defend (the
  empty state and the bubbles both inside `.log`); the number itself is a frozen measurement,
  recorded in `docs/refinements/body-overlay.md`.
- **A live activity chip and the settled "Thoughts" disclosure are one row in two states**
  (`components/Message.tsx` + `src/overlay.css`, ADR-0035 decision 13). Both floor themselves on
  `--trace-row` (24px, the chip's own box), so the frame where a turn completes swaps one for the
  other in place instead of easing the whole panel down by the 4px difference their natural boxes
  had. `Message.test.tsx` pins what the stylesheet cannot: that the disclosure stands exactly where
  the chip stood, one row for one row.
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
  chip drops and a collapsed "Thoughts" disclosure above the bubble holds the whole trace
  (`components/Thoughts.tsx`: a button carrying `aria-expanded` over a `Collapse`, its `›` marker
  turning over the roll's own 300ms, resting chrome only since the thinking is done). It is not a
  `<details>`, which reveals its content in one frame and cannot be made to animate it; reusing
  `Collapse` is also what puts the trace under the same `data-morphing` contract, so the panel grows
  to hold it over the same movement. The trace opens where it is: nothing touches the history's
  `scrollTop`, so the row the reader clicked stays exactly where they clicked it and the trace
  unfolds beneath it, at the cost of pushing the reply below the fold when the panel is already at
  its ceiling (filed in [refinements/body-overlay.md](../refinements/body-overlay.md)). Each delta
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
- **A scroll container reserves its scrollbar; it never borrows the content's width.** All seven
  (`.history`, `.switcher`, `.reminders`, `.thoughts-body`, `.confirm-draft`, `.rows`, and the
  composer's `.field`) carry `scrollbar-gutter: stable`, so overflowing changes nothing about
  where a bubble, a row, or a wrapped line sits. Paying for that rail (`--rail`, 6px) takes one of
  two shapes, and which one depends on whether the container already had inline-end padding.
  `.history` and `.rows` (16px) and `.switcher` and `.reminders` (6px) had enough to hold the rail,
  so it is **subtracted** from theirs and their resting margins are unchanged. `.thoughts-body`,
  `.confirm-draft`, and `.field` had 0, 0, and 2px, which is not enough to both hold the rail and
  keep a wrapped line off the thumb, so a rail of padding is **added** beside the reserved one and
  their inline-end inset is now 12px. Adding an eighth container means picking the right one of the
  two: subtract where there is padding to spare, add where there is not (subtracting from nothing
  is a negative padding, and spending a 2px padding leaves the text about a pixel off the thumb),
  or the container jumps sideways the first time it fills up (`src/overlay.css`,
  [overlay-ux.md §2](../design/overlay-ux.md)). The gutter is inline-end only, so the second half
  of the rule is that nothing may grow along the other axis: a horizontal bar takes its height out
  of the content box and shoves every child up, unreserved. Any container holding text it did not
  author breaks long tokens instead (`overflow-wrap: anywhere` on `.bubble`, `.thoughts-body`,
  `.confirm-row dd`, `.confirm-raw`, `.reminder-text`; `.w`, the per-word streaming span, is
  `white-space: pre-wrap` rather than `pre` so that reaches inside it), and `.history` carries
  `overflow-x: clip` so a future child cannot bring the shift back.
- **The composer picks its layout at one width, never at the width it is using.** The pill has two
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 17): the send button beside the field on one
  line, and under it on more, where the field spans the pill instead of stopping 44px short for the
  button's column. `Composer.tsx` asks which to use with the pill forced into the INLINE layout,
  always, because a stacked field is that same 44px wider: a draft that just wrapped fits on one
  line again once the button leaves its side, so a decision taken at the width in use would unstack
  it, re-wrap it, and stack it again (the band is five or six characters wide and where it starts
  depends on the glyphs: 60 through 65 on one traced line at the shipping 560px, 62 through 66 on
  another). The question itself is asked of the DOM rather than of a constant, `scrollHeight >
  clientHeight` at `height: auto`, a `rows={1}` textarea's auto height being exactly one row, so
  nothing here restates a font metric and a wrapped long line counts as multiline like a typed
  newline does. Two rules follow for anyone editing this: `.composer`'s transition names its
  properties (an `all` transition restarted a gap animation on every keystroke, since the decision
  removes and restores the class inside one layout effect), and the button must stay in the same
  corner of the same content box in both layouts (the last item of a bottom-aligned row, then the
  last row of a column), which is what keeps its rect identical across the switch. A third rule
  guards the measurement itself: it pins the pill's `min-height` for the length of the effect
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 18). At the panel's ceiling the column is in
  deficit, the pill only holds its height because of the floor under it, and taking the class off
  drops that floor, so the log above grew into the gap mid-measurement and Chromium clamped its
  `scrollTop` to the taller reading and kept the clamp. Anything added here that changes the pill's
  box before reading it belongs inside the same pin. The whole measurement lives in a `useCallback`
  because the width is the other half of the question and it can move on its own: a `resize`
  listener runs it too ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 21), since a keystroke
  is not the only thing that changes the answer, and the listener is removed on unmount because
  React nulls the refs the measurement writes through.
- **The draft's window fades where it cuts a line.** `.field` scrolls in two states, past its 120px
  ceiling and under the squeeze below, and neither bound is a whole number of line boxes, so the
  edge line was sliced through its glyphs ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 20).
  A `mask-image` band the size of the field's own padding fades it instead, and
  `scroll-padding-block` of that same padding keeps the caret's line out of the band, Chromium
  otherwise scrolling a caret flush to the edge it moved toward. Three numbers now agree by
  declaration rather than by the font's accident: `line-height` is pinned at the 16px `normal`
  computed to, and the 34px one-line field, the 84px floor below and the 9px band are all read off
  it. Changing the field's padding changes the fade band with it, which is the point of the
  `--field-pad` custom property they share.
- **The pill yields before the panel's edge does, and only after the history has nothing left.**
  Three declarations in `overlay.css` carry it ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision
  19), and each is load bearing: `.composer.stacked` has an explicit 84px `min-height` (one row of
  field plus the button's row, measured off the boxes) that replaces the automatic minimum a flex
  item gets from its content; `.composer.stacked .field` keeps its measured height as the basis but
  gives the shrink back (`flex: 0 1 auto`), so a squeeze comes out of the draft's window rather than
  the button's row; and `.history` carries a shrink factor of 100000, which is an ORDERING and not a
  ratio, since flexbox has no way to say "shrink last". Without them, at 640x720 with the switcher
  open and the reminder stack up a draft at the field's ceiling put the pill's own bottom edge 13px
  past the panel's clipped edge and the whole hint strip 55px past it. Anyone changing what is in
  this pill re-measures the 84, and anyone giving another child of `.view` a shrink weight is
  changing who pays first.
- **The composer tells the chat when the pill resizes, because the log pays for it.** They are flex
  siblings and the log is the one that yields, so a draft that restacks or wraps takes that height
  straight out of the visible window (52px, and 122px at the field's ceiling, measured at 640x720).
  `Composer` calls `onResize` when its measured height actually changes and `ChatView` answers with
  the same tail-pin it uses for a new message, reader override included. A `ResizeObserver` on the
  log would be the obvious alternative and is the wrong one: the log also resizes when a trace rolls
  open, where leaving `scrollTop` alone is deliberate (ADR-0035 decision 15).
- **The history's scroll position is decided here, not by the engine.** `ChatView` holds the log at
  its tail while the reader is at the tail, and a section rolling open inside the log leaves
  `scrollTop` alone so the row stays under the pointer that opened it. `.history` therefore carries
  `overflow-anchor: none`: Chromium's scroll anchoring is a third decider of the same number, and
  the roll is the only mid-log resize in the overlay for it to react to. A roll measures its content
  at full height and animates from zero, which the anchor reads as the log shrinking, and it
  compensated by 76px in one frame before walking the compensation back over the roll
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 15 has the traces and what turning it off
  gives up). A future scroll container that holds rolling content wants the same line, or its own
  reason not to.
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
