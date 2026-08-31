# body/app (`cortex-body`, overlay + Tauri shell)

**Purpose.** The host-native body app (ADR-0011): a React + Vite overlay summoned by a global
hotkey, talking to the brain over the `Converse` seam, wrapped in a thin Tauri shell. It is its
own project *outside* the gated `body` Cargo workspace (`body/Cargo.toml` excludes it) so
`just check` never builds Tauri. The **frontend** is gated at 100% (Vitest); the **Tauri Rust
shell** is host-validated on Windows, like the brain's real adapters.

Two halves meet at one seam. That seam is the typed `BrainBridge` port:

- **A theme change crosses the whole surface together.** `applyTheme` sets `data-swapping` on the
  root for `THEME_SWAP_MS`, and `[data-swapping] *` puts ONE transition (colour, background, border,
  fill, stroke) on everything for that window. It exists because a theme moves the same `color` every
  control eases for its own hover: left alone the swap was a ragged 20 frames, most text taking the
  new value at once, the pin, pencil, trash and tab labels crossing at 0.16s to 0.35s behind it, and
  the chat title and the reminder lines (the two things that INHERIT the ground's colour instead of
  setting their own) following a 0.4s ease on the ground. Two details decide whether it works: the attribute
  goes on BEFORE the tokens, since a transition is started from the after-change style, and it comes
  off on a timer rather than a flush, since taking it off in the same task leaves nothing to ease.
  The duration lives in `THEME_SWAP_MS` and is written to the root as `--theme-swap` for the
  stylesheet to read, so the number holding the attribute on cannot drift from the number easing the
  colours. The first application is not a crossing: there is nothing to cross from.
- **A gradient is not a colour.** `--accent` is a `linear-gradient`, so `color: var(--accent)` and
  `border: 1px solid var(--accent)` do not compute, and a declaration invalid at computed-value time
  is set to `unset`, which for `color` means `inherit` and for a border shorthand means no border.
  Four rules ask for it. The pinned row's pin asked and always rendered as inherited text, which is
  also what made it jitter across a theme change (it chased the ground's easing colour through its
  own 0.16s ease); it now asks for `var(--text)` in as many words, and the pinned row's dead
  `border-left` is gone. The thinking chip's label and the rename box's border still ask, and still
  render as inherited text and no border. Giving a gradient to a colour needs a solid token
  (`--spark`) or `background-clip: text`, not a var swap.
- **Frontend** (`src/`, gated). Pure logic first: the theme system (`theme/`), the activity mark
  (`mark/`: `bubble.ts` is the pure geometry, `marks.ts` the style registry, `useMarkClock.ts` the
  frame clock, ADR-0031), the window's dreaming edge (`edge/`: `liquid.ts` the pure geometry and
  the eased working depth, `edges.ts` the style registry on the same clock, rendered by
  `components/PanelEdge.tsx` as a clipped background slab under the content so the words never
  sit on the warping layer, ADR-0036), the whispered streaming (`whisper/`: `front.ts` the pure
  front engine and tokenizer, `metrics.ts` what a bubble measures about itself, the box that
  measurement poses and the watch that says when a window change has expired it,
  `useWhisperClock.ts` the frame clock that writes the letter ramps,
  the gliding mist and the bubble's posed box, rendered by `components/WhisperBubble.tsx`,
  ADR-0037), the appearance record (`overlay/usePreferences.ts`:
  hydrates the theme, mark and window edge from the brain once and writes each change back
  optimistically, ADR-0032), the panel's
  vertical geometry and the motion into it (`overlay/usePanelMotion.ts` drives
  `overlay/panelPlacement.ts` and its neighbours, which own `bottom` and `max-height` as inline
  styles; `overlay/useViewTransition.ts` names the view being left behind
  long enough to fade it; `overlay/useLogScroll.ts` owns where the reader is in the conversation and
  keeps them there, spending `overlay/logRide.ts` on a section rolling open, whether in the middle
  of the log or in the chrome beside it, ADR-0033/ADR-0034), the overlay state
  machine (`overlay/overlayState.ts` is a pure reducer over a `Mode` = hidden/panel/orb/preview,
  with three halves split off for the line cap and re-exported from it, so components import one
  module: the session-switching helpers in `overlay/sessionState.ts`, the turn fold, meaning
  what a `Message` is and how one `Converse` turn's events apply, in `overlay/turnState.ts`, and
  the panel's own sections, the switcher list and the console's tabs, in `overlay/chromeState.ts`),
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
  `DemoBridge` (canned stream + three canned chats for `vite dev`, with everything it says or serves
  in `demoScript.ts` beside it and only the behaviour left in the class; all four catalog writes are
  held rather than rebuilt per call, so a rename, a pin and now a DELETE all stick for the session,
  the delete having been the one left as a no-op, which made a deleted row's exit unmeasurable by
  hand because the refresh right behind it listed the chat again; and a turn adds the chat it was
  spoken in to that list, titled by `deriveTitle`, so a chat can ARRIVE and not only leave, which is
  what the empty line's filling direction is measured on), `FakeBridge` (tests). Only
  `tauriBridge.ts` and `main.tsx` are coverage-excluded (the un-gated glue); everything else is
  100% line + branch, `demoBridge.ts` and its script included since the shared check list below
  started driving them. `useOverlay` owns the `session_id` (minted per new chat)
  and the store-backed chat list (loaded on mount + after each turn; a chat's history loads on
  select/cycle). The open-chat **header title** is the switcher's own `SessionSummary.title` for
  that chat, read from the loaded `state.sessions` by `openSession`/`adoptSession` (`headerTitle` in
  `sessionState.ts`), so the header and the switcher row agree by construction (a stored generated
  title, a user rename, or the brain-side truncation bound, ADR-0021 header-title addendum) instead
  of re-deriving the header locally; only a chat absent from the loaded list (a reminder deep-link
  past the recency window) falls back to the local `deriveTitle`. That local derivation, which also
  names a chat on its first submit before the brain has listed it, is a **stand-in** for the
  brain's and not a bound of its own: `sessionState.ts` declares `TITLE_MAX` 48, the same number
  `cortex_core.sessions` bounds every listed title to, tied to it by `scripts/crosscheck.py` so
  neither can move alone (ADR-0021 truncation addendum, where the 48-against-32 disagreement that
  showed one chat under two names is measured). On cold start the first list
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
- **The port's shared check list** (`src/bridge/bridgeContract.ts`, driven by
  `bridgeContract.test.ts`). Thirteen named checks that every implementation CI can run must pass,
  which is the TypeScript counterpart of the brain's `*_contract.py` files: one list of checks and
  one parametrized driver over both implementations, rather than a suite restated per
  implementation, because a restatement drifts the moment a check is appended to one copy and not
  the other. The list holds the turn HANDLE (a cancellation comes back, nothing is delivered during
  the call, and cancelling silences the turn however often it is called), the probe (a classified
  status rather than a rejection, and it keeps answering), the catalog (a seeded chat is listed; a
  zero limit means the default listing and a positive one cuts that same listing; a rename shows in
  the next listing and an empty one clears the override; a delete stays gone across the refresh
  behind it; a pin groups the chat above an unpinned one and the flag round-trips), the stored
  history (well-formed messages, and a chat nobody has spoken in answers rather than rejecting),
  the reminder ack (true for what is due, false for what nobody was told about), the settings
  record (a write reads back, a second write to one key replaces it, an empty value clears it), and
  the stale confirm answer (absorbed rather than rejected). The port has no "create a chat" call, so
  seeding one is the fixture's job, per implementation and outside the shared list: the demo bridge
  comes by a chat the way the brain does, by being spoken in, and the fake serves the table its
  test assigns.
  **Where the two legitimately disagree**, and so what the list deliberately does not hold: the
  CONTENT of a turn's stream, since `DemoBridge` plays a recorded conversation on a timer and
  `FakeBridge` streams nothing at all until the test that owns it says so, which is why the cadence
  (reasoning statuses, then the reply, then exactly one completion, last) is pinned by
  `demoBridge.test.ts` instead; what a cleared title falls back to, empty in the fake and "New
  chat" in the demo, where the brain would derive one, so the shared claim is only that the custom
  title is gone; where an UNPINNED chat sits, the demo sorting its held catalog by recency and the
  fake serving its table in the order it was assigned, so the shared claim is the pinned grouping
  and the flag; and what an ack does to the due list, the demo dropping the reminder and the fake
  leaving its table for the test to say, so the shared claim is the boolean. `TauriBridge` is not
  under the list at all: every method of it crosses the Tauri IPC boundary, which makes it the
  frontend analog of the Rust host adapters, and holding it to these checks would mean faking
  `invoke`, which measures the fake rather than the crossing.
  **What the list found on its first run**, before any implementation was changed to suit it:
  `FakeBridge.listSessions` ignored its `limit` argument, so a test could pass against a listing
  production would have cut; `FakeBridge.setPreference` recorded a write the served record never
  carried, alone among its writes in that, the three catalog writes beside it having always
  reflected theirs; and `DemoBridge.listSessions` read `limit === 0` as "at most none" where the
  port documents it as the brain's own default, so browser dev would answer an empty switcher to a
  caller that asked for the default listing. A fourth came out of the turn-handle check rather than
  from the two arms disagreeing: `DemoBridge` announced a capture activity INSIDE the `converse`
  call, which is a delivery the real bridge cannot make, its events arriving over a Tauri channel
  after the call has handed back the cancellation its caller stores. The ask rides a short timer
  now, like everything else the demo says. All four are fixed.
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
- **The screen-capture indicator** (`state.capture` + `components/CaptureDot.tsx`,
  ADR-0029). `state.capture` is a two-rung claim (`"asked" | "read" | null`), not a flag. The
  reducer raises it to `"asked"` when a `toolActivity` event names `CAPTURE_SCREEN_TOOL`
  (`"capture_screen"`, matched by name because the event already carries it and a second seam
  field would be one more place the two ends could disagree), to `"read"` when the `toolOutcome`
  settling that dispatch comes back `ok` (ADR-0029 outcome addendum), and clears it only when
  the turn ends, on completion or failure alike. It therefore stays lit for the rest
  of the turn rather than blinking past with the tool chip, because the fact the user is owed is
  "the assistant went for my screen during this reply", not "a tool ran for a moment". This is
  a **consent surface** and part of why the capture tool ships without an approval card: the
  dot renders only when it means something and carries a fixed accessible label per rung, either
  *"The assistant asked to look at your screen during this reply"* or *"The assistant looked at
  your screen during this reply"*.
  **The ladder only climbs.** Nothing short of the turn ending may weaken a claim: a second ask
  after a read stays at `"read"`, a not-`ok` outcome changes nothing, and an `ok` outcome for an
  ask this side never saw still promotes. Over-reporting a screen read is the safe direction for
  a privacy indicator and under-reporting is the dangerous one, and the two are not symmetric
  brain-side either: a capture that failed *after* the shutter fired, where the pixels really did
  leave the display and the body really did show its own receipt, is indistinguishable from one
  that never happened. So `"asked"` remains what a capture the host rejected
  (`CORTEX_HOST_CAPTURE` unset is the shipping default), one whose self-exclusion failed closed,
  one the body never answered, and a gated one the user declined all leave on screen. Visually
  the ring only ever gains: `"asked"` is the open ring unchanged, and `"read"` grows a 2.5px
  pupil inside it (an eye opening, not a fill, since a solid 7px `--warn` disc is what the
  connection dot beside it looks like when the brain is degraded). The body fires its own OS
  notification independently; this is the half the user is already looking at.
- **The connection indicator** (`overlay/linkState.ts` + `overlay/useLink.ts` +
  `components/LinkDot.tsx`, ADR-0011 addendum). `state.link` is a `LinkView { state, detail,
  probing }`: `state` is the last thing the brain **proved** (`ready` | `degraded` | `down`,
  plus the overlay's own `unknown` before anything is asked) and `probing` is the overlay's own
  fact, kept separate so a probe never overwrites what was last true. `describeLink` renders the
  pair as `{ tone, busy, label }`, keeping the last known colour while a probe is out (a
  reconnect neither flashes green nor forgets it was red) and not reporting busy for the
  routine probe on an already-ready link. Three sources keep it current, and **none is a
  liveness timer**: the reducer folds every `TurnEvent` as proof of serving and every
  `transportError` through the same classification `body_core::link` uses (`connection` and
  `timeout` → down, because nothing answered; `rpc`/`protocol` → degraded, because the brain
  answered); `useLink` probes once per summon;
  and it re-probes every `LINK_RECHECK_MS` (5 s) **only while the overlay is visible and the
  link is not ready**, stopping the moment it answers ready. The re-check is an interval keyed
  on "visible and unhealthy" rather than a timer re-armed per answer, because a probe answering
  inside one React batch never renders the in-flight flip and would end the recovery after one
  retry with nothing to report that it had stopped; an in-flight ref keeps a slow probe from overlapping a tick. A **rejected**
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
  32px of padding, so with the ring showing the row needs a 240px panel. Under that (a viewport
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
  `onSelectSession`, so a reminder and the switcher load a chat by the same path, parting only on
  whether the arriving chat is announced, which this control asks for and a row does not. Opening never
  acks (an ack destroys the reminder, navigation does not), and the control is *absent* for a
  session-less row (`""`) or for the chat already on screen, where it would cancel that chat's
  running turn to arrive where it already is. The card's own **exit** is the row's, not the list's
  (ADR-0035 addendum): `overlay/usePresence.ts` renders a list that outlives the caller's, keeping
  an item that has left `state.reminders` in the gap it left, marked `leaving` and carrying the
  last version of itself that was on screen, until that row's `Collapse` reports its roll over
  through `onClosed`. So the ack leaves in the frame the check is pressed and only the exit lags,
  which is the opposite of the first version: it delayed the ACK behind a `MORPH_ROLL_MS` timer, so
  an unmount inside those 300ms (the stack is keyed to its chat, and Ctrl+N remints it) cancelled
  the timer and the reminder was never acked at all. The hook holds no clock of its own, a key that
  returns before its exit ends stops leaving (which is what a re-listed reminder after a lost ack
  is), and the row's `<li>` sits OUTSIDE the roll wrapper as `.reminder-slot` so the stack stays a
  list to a screen reader and the `.reminder-slot + .reminder-slot .reminder` hairline still has two
  siblings to sit between.
- **A deleted chat's row leaves the same way, and reordering is what the switcher adds to it**
  (`components/SessionList.tsx`, ADR-0035 addendum, 2026-08-03). The switcher renders from the same
  `usePresence`, so a row that leaves `state.sessions` rolls out over `MORPH_ROLL_MS` while its
  neighbours close the gap (traced at 900x900: 50.00px to zero over 300ms, the row below travelling
  269.63 to 220.00 in the same frames, the row above holding at 170.00 exactly, and the panel and
  composer both moving 0px because the history absorbs it). Three things are the switcher's own.
  **The row is `withdrawn` while it leaves** (`overlay/withdrawn.ts`): the chat is gone, so its four
  buttons must not spend 300ms still offering to open or re-delete it. **The `<li>` carries nothing
  but its place**, `.switcher-slot` outside the roll and `.switcher-row` inside it, because the
  50px `min-height` that keeps every shape of a row the same height is also a floor the roll cannot
  get under (proved by putting it back: the row stood at 50.00 for the whole 300ms and then vanished
  in one frame, the old defect arriving 300ms late). **And a leaving row goes back under the row it
  was under, not at the index it held**: the switcher re-lists pinned-first and then by recency after
  every write, so a pin landing mid-roll reorders the list around a row that is still going. Traced
  at 900x900 with a pin 120ms into a delete, the neighbour rule carries the rolling row from y=220 to
  y=270 with the row it sat under; the index rule leaves it at y=220 and walks that neighbour down
  past it to y=240.47, so the gap ends up between two rows it was never between. The reminder stack
  only ever loses rows, so the two rules agree on every frame of it and it never had to choose.
- **The switcher is a named list of rows, and the row says which chat is open**
  (`components/SessionList.tsx` + `components/SessionRow.tsx`, ADR-0035 addendum, 2026-08-03; the
  row's three shapes moved into their own file on 2026-08-06 with the caret rule below). The `<ul>`
  carries `aria-label` and
  no role, the reminder stack's arrangement, because the `role="listbox"` it used to carry was one
  no child satisfied: an option is a leaf and a row is four buttons, and a `<li>` inside a listbox
  is not a listitem either, so Chromium announced a listbox with no options in it over three rows of
  role `none`. Removed, the implicit list and listitem roles come back with nothing written on the
  `<li>`, and the four buttons keep their own tab stops (twelve across the demo's three chats,
  identical before and after). The open chat was a background tint and nothing more, and
  `aria-selected` needs the role that came off, so the row's button carries `aria-current`, `true`
  on the open row and `false` on the others. `Ctrl+↑` and `Ctrl+↓` are unchanged, being an
  application-wide cycle rather than movement inside a list; what they say when they swap the chat
  is the next bullet.
- **One live region says what happened to the panel: the chat that arrived, the list that shrank,
  the list the reader opened, or several of them in one sentence** (`overlay/notice.ts` +
  `components/Announcer.tsx`, ADR-0035 addenda, 2026-08-04 and 2026-08-07). The overlay keeps one
  polite region, `role="status"` at the overlay's ROOT rather
  than in the panel, because a dismissed panel is `inert` and the cycle keys are global, so a press
  can open the panel and swap the chat in one commit and a region inside it would enter the
  accessibility tree with the words it would have read. `overlay/notice.ts` holds **everything the region
  may carry**: `speak` counts the announcements and joins what it was given, and `arrived`,
  `chatDeleted`, `reminderDismissed` and `switcherOpened` build the sentences, so the question of
  what may go in the region has one file for an answer. `OverlayState.notice` is `{ text, count }` and `Announcer`
  renders the text as given rather than composing a prefix.
  **A swap** is announced by the gesture rather than by the transition, so `openSession` and
  `newChat` carry an `announce` flag set by the gesture that dispatched them: one arm serves a
  switcher row and a cycle key both. Speaking are the cycle keys, `Ctrl+N`, a reminder card's open control, and the fresh chat
  that replaces a deleted one, none of whose gestures name a chat; silent are a switcher row and the
  header's pencil, each already labelled with the arriving title, and cold-start adoption, which
  answers no gesture and cannot land over something said (it runs only while `touched` is false). A
  silent gesture CLEARS the notice, a removal not being announced under the default
  `aria-relevant`.
  **A list that shrank** is announced by either of the overlay's two lists, with no flag, because a
  row leaving is destroyed rather than merely unspoken: it is out of the tree by the time the caret
  lands, and the reader's gesture is a request rather than an outcome (a failed delete leaves the
  row). Both arms guard on the list having really shrunk, so a repeated dispatch claims nothing.
  A delete of the chat on screen does both in one commit and says both in **one** sentence
  (`Chat deleted. 1 chat left. Switched to New chat.`), deliberately rather than in a second region:
  two regions mutating together leave which is spoken, and in what order, to the reader's own speech
  queue, which no accessibility tree can observe. `NO_OTHER_CHATS` is exported here and rendered by
  `SessionList`, so the switcher's empty line and the sentence about an emptied switcher are one
  string, and `RECENT_CHATS` the same way for the header control, the list's own label and the
  sentence below.
  **A list the reader OPENED** says what it holds (`Recent chats open. 3 chats.`, and the empty
  line's own words when it holds none), carried by `chromeState.ts`'s toggle arm with the gesture
  deciding as a swap's does: `Ctrl+K` speaks, the header's chats button does not, since it carries
  `aria-expanded` under the caret that pressed it. It is the CONTENTS and not the toggle, so the
  closing direction has no mirror: a close is answered by the caret landing on that same button
  (`overlay/sectionCaret.ts`), and what an opening reader wants is the one fact walking cannot give
  them, the empty line not being a tab stop at all. The arm has no silent gesture left: it stood the
  sentence down while the chat was not the view on screen, and since 2026-08-07 it cannot open a
  list there at all, the key landing on the chat first (the console bullet below carries the rule).
  The notice carries a count that keys the region's child, since a live
  region reports a mutation rather than a value and two announcements can read alike. Where focus
  goes is the next bullet.
- **A chat arriving on the panel takes the caret with it** (`OverlayState.arrival` +
  `components/Composer.tsx`, ADR-0035 addendum, 2026-08-06). Every gesture that replaces the
  conversation puts focus in the composer, which is where a summon already puts it, so the reader is
  left in the conversation that arrived. Before it, three of those controls sat inside sections the
  swap takes away (a switcher row, a reminder card's open control, a delete confirm) and the pressed control
  simply stopped existing, focus falling to `<body>`; so did any global key pressed while focus was
  inside the switcher. `arrival` is a count each swap arm raises, and the composer's `arrival` prop
  is that count while the chat is the view on screen and null otherwise, the field taking focus on
  every change to it. **Unlike the notice above, no flag travels with the action**: that rule is
  about the gesture and this one about the transition, so each arm answers for every gesture that
  reaches it.
  It is a count rather than the session id because re-selecting the open chat is still an arrival and
  still takes its row away; cold-start adoption is excluded by being its own arm, and would be moving
  focus inside an `inert` panel besides. What it does NOT reach is a row gesture that swaps nothing,
  which is the bullet after next. What the caret lands IN is the next bullet.
- **A draft belongs to the conversation it was typed into** (`OverlayState.drafts` +
  `overlay/drafts.ts` + `components/Composer.tsx`, ADR-0035 addendum, 2026-08-06). Unsent composer
  text is keyed by session id in the reducer and the field is CONTROLLED by the entry for the chat
  on screen, so a swap hands the arriving conversation its own sentence in the same commit that
  swaps the transcript: no arm parks anything, no effect runs in between, and no frame can paint the
  wrong conversation's text. Before it the field held one text for the whole overlay, which cost
  nothing while a swap dropped focus and cost the reader a stranger's half sentence once the caret
  started landing there. **It is view state and dies with the body process**, which is a decision and
  not an omission: the hard rule about surviving a model swap is satisfied by being in the body at
  all, and what a store would add is survival of a RESTART, which text nobody has sent, nothing but
  its own field can read, and no surface promises to keep does not earn. It sits in the reducer
  rather than in the component because the delete cascade has to take a deleted chat's draft with it
  and a swap has to be synchronous, which also leaves it one hydrate from a store if that ever
  changes. **An empty field is stored as nothing**, which is the whole of the eviction policy: only
  chats with a sentence waiting in them hold an entry. **Sending a text empties the field that held
  it**, asked of the text rather than of the control that sent it, so the composer's own send spends the draft and an
  example prompt on the empty state does not. A send the reducer rejects spends nothing. **Typing
  sets `touched`**, which that flag has always documented and could not do until a keystroke reached
  the reducer, so a cold-start adoption can no longer replace the conversation a half-typed line was
  written in. The caret lands at the END of a restored draft, the field's own answer to having its
  value assigned and the one worth having, since coming back to a half-typed thought is coming back
  to finish it.
- **A list that reshapes under the hand keeps the caret** (`overlay/rowCaret.ts` +
  `components/SessionRow.tsx` + `components/Reminders.tsx`, ADR-0035 addendum, 2026-08-06). The rule
  above answers the gestures that replace the conversation; these are the ones that do not, and there
  are thirteen of them across the two lists. Three clauses. **A row that changes shape** hands the
  caret to the control its new shape puts in the place of the one that left: a rename opens on its
  editor with the old title selected, closes (either way) on the pencil that opened it, a delete
  opens on the confirm's CANCEL and closes on the trash that asked. **A row that leaves** hands it to
  the same control in the row that inherits its place, below where there is one and above for the
  last row, which is the composite-row reading of the list-deletion pattern and the reading these
  rows need, having been taken out of `listbox` for being four buttons each. **A list with no row
  left** hands it to its `anchor` prop, a control outside the list that `ChatView` holds: the
  header's chats button for the switcher, which is still open in front of the reader, and the
  composer's field for the reminder stack, whose section leaves with its last row. The pin toggle is
  answered by saying nothing, its button surviving the regroup it causes. The move is a layout effect
  at the commit, never at the end of the roll, and every focus call is `preventScroll`. `heir` and
  `caretKey` are pure; `useRowCaret(list, anchor)` returns the function a gesture calls, and the
  control it aims at is named through a `data-caret` attribute rather than held as a ref, because it
  usually does not exist yet when the gesture fires. Two neighbours came with it: **both of a row's
  overlays keep a cancelling Escape to themselves**, the window listener having dismissed the whole
  panel on the same press, and **the `?` guard asks about `HTMLInputElement` too**, that key having
  opened the console out from under a half-typed rename.
- **A field holds the chords it would lose text to** (`overlay/fieldKeys.ts` +
  `components/SessionRow.tsx` + `components/Overlay.tsx`, ADR-0035 addendum, 2026-08-07). The rule
  the two neighbours above left open, answered about the TEXT rather than about the key: **a chord
  passes through a field whose text the overlay keeps and is held by a field whose text it would
  throw away.** The composer keeps every keystroke under the chat it was typed into, so `Ctrl+N`,
  `Ctrl+K` and the cycle keys all still work from where a summon lands; the switcher's rename editor
  keeps nothing, so it holds the press until Enter or Escape has settled the name, both one press and
  both leaving the caret on the pencil. Measured before it: all four chords discarded a typed name
  with no undo behind it, and two of them are not the overlay's to take at all, `Ctrl+↑` and `Ctrl+↓`
  being a single-line input's own start-of-text and end-of-text jumps. `chord(press)` is the one
  definition of a modified press and the global handler asks it too, so the two sides cannot drift;
  `fieldKey(press)` answers `cancel`, `hold` or `pass` for a field that would lose its text, with `?`
  on the `pass` side because the element-type guard above answers it one layer up. A hold is
  `stopPropagation` and never `preventDefault`, so select-all, copy, paste, undo and those two caret
  jumps are untouched. The delete confirm is deliberately outside the rule, holding no text to lose.
  **And the hold is silent by decision** (ADR-0035 addendum, 2026-08-07), which is why nothing here
  writes to the live region: the branch is reached by every chord, not by the four the overlay binds,
  and measured, seven of nine presses through it do something in the field anyway (`Ctrl+Z` undoes
  the whole edit), so a sentence raised here would be false for most of the presses that reach it.
  Nothing a hold
  touches is destroyed either, the input's name, value and selection reading identically across the
  press, which is the test the region's contract sets.
- **A section the reader closes hands the caret to its anchor** (`overlay/sectionCaret.ts` +
  `components/SessionList.tsx` + `components/ChatView.tsx`, ADR-0035 addendum, 2026-08-07). The third
  landing, and the one the two rules above leave: no conversation arrives and no row moves, the whole
  section goes and takes its controls with it, so `Ctrl+K` used to ride a row's pencil for the 300ms
  roll and drop the caret on `<body>` at the unmount. **Only when the caret is INSIDE the section**,
  which is what keeps `Ctrl+K` from a half-typed sentence from moving anything, and what makes the
  header's chats button need no case of its own: its own press puts the caret on the anchor at 45ms,
  before the close is dispatched. The anchor is the control each section already carries for its
  emptied case, so a list that runs out of rows and a list that closes land in one place: the chats
  button for the switcher, the composer's field for a section whose work is over. **It stands down
  when `arrival` changed in the same commit**, which is most of the ways the switcher closes (seven
  of its thirteen closing gestures are chat swaps), stated in code rather than left to the composer's passive
  effect winning a race a screen reader could hear. `useSectionCaret(section, anchor, open, arrival)`
  fires on the true-to-false edge at the commit, the rows being mounted for their roll; `handOff` is
  the same move told at a gesture instead, for the empty state's example chips, whose section is
  unmounted in the commit that submits and which are the one control the overlay has that its own
  press removes with no heir to give the caret to. The reminder stack is deliberately not wired: its
  own three closings are each answered elsewhere.
- **The empty line waits for a row and yields to one, and a row the list moves travels there**
  (`components/SessionList.tsx` + `overlay/useTravel.ts`, ADR-0035 addendum, 2026-08-03). The empty
  line is asked of `sessions` rather than of the rendered rows, so deleting the last chat puts it up
  in the frame that row starts leaving and `Collapse`'s `enter` prop (read once, at mount) grows it
  from nothing over that row's own roll: the card eases 64 to 53 over 283.9ms at a largest single
  frame of 1.66px where it used to roll to 14 and snap 39px back, and the panel holds its edge
  throughout. The other direction is not the same rule reversed: the line is unmounted in the frame
  a chat arrives, an 11px step kept on purpose, because a line rolling away under a row that has
  already landed is a bigger overshoot than the step it removes. It renders BELOW the rows so the
  first `data-morphing` in the tree during those 300ms is the leaving row's, which is the target the
  panel's ride-along should read. `useTravel` is the reorder half: a hook over a ref and a selector
  (so the next list to need it wires it in one line) that reads each row's `offsetTop`, lets the
  commit place it, and hands the difference back as a `translateY` decaying to nothing over
  `MORPH_ROLL_MS` and `EASING`. Rows are remembered by element rather than by key, since React moves
  the node a keyed row owns; travels are `composite: "add"` so an interrupted one composes instead of
  stranding the row; and while a roll is in flight inside the list the record is refreshed every
  animation frame and never played from, because a roll moves rows by layout with no commit in it
  and the release at the end of an exit would otherwise read the neighbour's travelled 50px as a jump
  to answer. A travel is a transform, so nothing outside the list can be fought by it.
- **The panel's views** (`components/Panel.tsx` + `ChatView.tsx` + `ConsoleView.tsx`, ADR-0034):
  `Panel` is a router over views of one window, not a window with sheets over it, and the views are
  `chat` and `console` (ADR-0035 decision 1). The console's TAB is deliberately not part of the view
  name: both tabs are mounted inside it and stacked in one grid cell, so a tab change is not a view
  change, replaces none of the chrome, and re-runs neither the enter animation nor the centring. A
  view per tab was the first shape and it flinched, jumping 12px between two tabs that differ by
  12px while the header and the chevron faded out and in around content that was the only thing
  actually changing.
  Whether a tab change resizes the panel at all is one number, `TAB_SPREAD_PX` in `ConsoleView`:
  within 15px the two tabs share the taller one's height (they ship 278px and 290px, measured at
  640x720), beyond it each gets its own and the panel morphs between them like any other size change
  inside a view. They are measured unstretched, in a pose the stack does not otherwise hold, because
  a pane stretched to the cell reports the cell's height and so hides the very difference being
  looked for; the read is synchronous, in a layout effect React runs before the panel's own.
  Only the active view is in the layout flow, so it alone
  decides the height the panel eases to; the view being left is held for one morph, lifted out of
  flow, and faded out over the one arriving; the chat is never unmounted, so the composer's focus and
  its field survive a trip to the console (the draft would survive an unmount too, being state above
  the component, but the caret would not). The history's scroll position does NOT survive
  on that alone, since the view being left is `display: none` at the end of the morph, and is parked
  and handed back by `overlay/useLogScroll.ts`.
  The view being left is bounded by the panel (`.view.out` carries a `bottom`) and not only lifted
  out of it: laid out at its own natural height, its composer dropped from 388px down the panel to
  558px inside a panel 347px tall, so the chat's bottom furniture was clipped away in the first
  frame of a fade the rest of it took a quarter of a second over.
  Whichever pane is on its
  way out is `aria-hidden` AND `inert`, chat or console, so two mounted panes are never two
  announced ones and never two tabbable ones. Both attributes come from one function,
  `overlay/withdrawn.ts`, and the same call sits on the panel itself while it is dismissed and on
  the console's tab not showing: wherever the overlay holds something mounted that is not on screen,
  what is hidden from a reader is hidden from the tab key in the same frame
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md), the 2026-08-03 addendum on the strip's
  keyboard, has the before and after counts and the react-dom 18 probe behind the `inert=""` form).
  `usePanelMotion` is the WHEN of the panel's
  geometry (every render, a window resize, both ends of a roll, and the panel's own box changing
  under it) over the files that are the what:
  `overlay/panelGeometry.ts` is the pure arithmetic (the centre, the ceiling clamp, the max height
  in whole pixels, since that one number is both written to the DOM and predicted against and the
  two must not round apart, and a duration paced by the distance the further-travelling edge
  covers, 120ms floor and 380ms
  ceiling, because one fixed duration cannot serve both a streamed line and a whole view changing,
  which the placement pairs with resuming rather than restarting a move whose destination a render
  did not change, so a token landing mid-ease shortens that ease instead of deferring it);
  a move's keyframes carry the CEILING as well as the two edges, because `max-height` clamps an
  animated height exactly as it clamps a laid out one and the ceiling already belongs to where the
  panel is going: written straight to the element, a 450 to 347 shrink stood at 351 one frame after
  the click and eased the last 4px, which is the whole move in a single frame and an animation of
  nothing after it. The panel also centres only on an aside inside the view being PLACED: a reminder
  stack belonging to the view being LEFT was subtracted from the height of the one arriving, which
  centred a 347px console as though it were 155 and capped it at 351px where 448 would have fitted;
  `overlay/panelMemory.ts` is what the panel remembers between placements and how it reads its own
  box (heights as the USED height off the computed style, which keeps the sub-pixels the box has and
  which the summon's scale transform does not touch either, the bottom edge off the rect, which it
  does not touch; plus the probe that asks what the panel WOULD be while a move of its own is
  overriding the box, an important inline `height: auto` outranking the animation origin in the
  cascade); `overlay/panelParts.ts` is the probes a placement
  makes into the panel's own tree (the aside it centres shy of, a multi-shape view's published
  slack, the scroll positions the measurement is about to cost), shared so that a ride-along's
  prediction and the placement after it cannot ask the same question two ways;
  `overlay/panelPlacement.ts` reads the box, plays the move and writes the two inline numbers, with
  `overlay/panelPin.ts` beside it holding the four rules that decide which EDGE it holds (entering a
  view keeps the edge it arrived on, coming back to the chat restores the parked one, growth in the
  chat pins the bottom so the composer stays under the hand, and a resize in any other view holds
  the top so the console's tab strip stays under the cursor); `overlay/panelBudget.ts` is the one
  write that caps it, putting the ceiling on the
  element as `max-height` and beside it as a `--ceiling` custom property, because `max-height` is
  the one thing a descendant cannot read and the two roll-open sections in the panel's chrome are
  capped out of that same number (overlay.css reserves the header, the composer's floor, the hint
  strip and the history's padding off it, and splits what is left between the switcher and the
  reminder stack in the ratio of the `vh` numbers they are written in, whenever both are GOING TO BE
  open at once, a section rolling shut having already published `data-morphing="0"` and so already
  stopped counting; both caps then ease to a new share over the roll's own duration and curve, gated
  on both sections standing open rather than on a roll running, because a section joins the tree one
  style recalc before it announces its roll). A section's SHARE of that split bounds its whole outer
  box and is applied to the roll's
  wrapper, which has no border, padding or margin of its own and holds the card's air inside its own
  clip; the card carries a second cap at the share less that air, so a list too long for its room
  scrolls instead of being clipped. Capping the card alone left its own frame outside every cap,
  `box-sizing: border-box` flooring a 14px border box under any shorter cap, so two sections cost 20px
  each however little they were given; `overlay/panelRide.ts` is the slide it makes alongside a section's roll, counting its
  prediction through the same `centringHeight` a placement counts its measurement with and bounding
  it at `openHeight` first, because that is the order the measurement happens in;
  `overlay/panelWatch.ts` is the `ResizeObserver` that catches a resize no render and no roll
  announced (a released row, content that settles after the render that brought it). It answers a change to the
  height the panel WANTS rather than to the box it has: a roll owns the height and is left alone, a
  move of the panel's own is asked through the probe instead of through the box (so a growth that
  lands mid-move redirects that move rather than queueing behind it), a reading that matches the
  height the panel was last placed for is answered with nothing, and the watch is lifted for the
  frame the panel writes in and taken up again on the next, since an observer that resizes its own
  target inside its own callback is the case the specification cannot deliver and reports as a loop
  error.
  `overlay/measured.ts` is the budget's idea pointed the other way: two numbers overlay.css cannot
  express are read off the boxes they restate instead of being frozen beside them, the empty state
  publishing `--chat-floor` (what `.log` stands on, so a first message does not shrink the panel out
  from under the composer) and a live activity chip publishing `--trace-row` (the row the settled
  Thoughts disclosure matches). It renders nothing of its own, both elements being in the tree
  exactly when their number is knowable and leaving exactly when it starts to matter. The empty
  state is a reading as React attaches it plus a `ResizeObserver` after it, because a reading taken
  in the commit frame alone catches it at 183px before the system font stack resolves and 185px
  after; a chip is one reading, being unable to appear before the user has typed and able to appear
  twice at once (a tool and a status), which one watch could not represent. Neither can feed itself (`.log.bare`'s own `min-height: 0` outranks the floor while
  the empty state is up, and the disclosure is never on screen beside the chip), and an element with
  no layout publishes nothing, so the values declared on `:root` stand as fallbacks.
  The rules: a
  summon centres the panel on what it arrives with for the length of its own 0.44s pop (so the
  reminders pulled on that same rising edge are the panel appearing with them, not growth
  afterwards) and stops the moment the user touches it, a press or a key being the difference
  between content the panel arrived with and a section they opened and will close again;
  entering another view centres it, coming back to the chat restores the edge it was
  left at, and everything else pins the bottom edge, so growth inside the chat and a new chat (the
  same view with less in it) leave the composer alone. A new chat or a cycle started while the
  console is up now clears the tab in the same commit, so those two take the first branch rather
  than the last: it is the ordinary return to the chat, at the edge the chat was left at.
  The pinned edge is kept UNCLAMPED and the
  ceiling is applied only on the way out to the DOM, which is what makes a grow-then-shrink round
  trip exactly reversible. That clamp is `max(0, pinned)` and nothing more, the ceiling having moved
  onto the HEIGHT: a shrink against the ceiling therefore moves the composer 0px as well, and the
  two are not in tension (measured 2026-08-06 at 640x720 and 900x900, every frame of an ack, a
  switcher round trip and a shrink clean off the ceiling). `components/Collapse.tsx` gives the switcher list, the reminder stack and
  a reply's Thoughts trace
  their own height animation, rolled to the used height off the computed style (`heightOf`, the
  panel's own reading, so a target and the prediction made from it are one number: an opening roll
  does not fill, and a rounded target left the section stepping the remainder when its layout took
  it back), the closing one filling forwards so no frame paints at the old size
  before React removes it, and committing that height by hand where nothing animates at all
  (`prefers-reduced-motion`, or a roll too small to see). Its optional `onClosed` fires once a
  CLOSING roll has finished, after the `cortex:morphend` dispatch so the section is still part of
  what the panel re-measures, and it is the only thing that ends a held exit (the reminder stack's
  rows and the switcher's, above). The contract between it and the panel is
  `overlay/morph.ts`, which also holds the curve and the "too small to bother" threshold both sides
  share: `data-morphing` on the section makes the panel leave the height alone and carries the
  height the section is rolling to, which is what lets the panel take its bottom edge off the
  ceiling over that same roll (`MORPH_ROLL_MS`) instead of afterwards, capped at the height the
  panel is allowed to reach. **That duration and that curve reach the cascade as two tokens**,
  `--roll` and `--ease` on `:root`, each restating its constant once for the rules that have to
  move with a roll rather than beside it (the section share caps' `max-height` and the thoughts
  marker's turn), both tied to `overlay/morph.ts` by `scripts/crosscheck.py`, which since
  2026-08-11 holds the spends as well as the declarations: it renders each token's NAME into
  `var(--roll)`, counted at 2 because those two rules are the set, and into `var(--ease)` as a
  presence check because 52 transitions ride that curve. Four other
  declarations in that sheet last exactly as long and stay literal on purpose, being coincidences
  rather than the roll: the panel's summon fade and the three arrival animations. That publication
  has a second reader, the cascade: overlay.css matches
  `[data-morphing="0"]` to know a section is rolling to nothing and stop counting it into the
  section budget's split a whole roll before React removes it. That cap goes on the ELEMENT for the length of the roll and not only on
  the prediction: a roll is not a placement, so the measuring cap `place` writes on its way in would
  otherwise stand there for the whole roll and let the section carry the panel clean past the clear
  space at the top (traced at 640x720 on a panel already at its ceiling: 450 to the loose 547 with
  the top edge 11px off the screen, held for 300ms, back to 450 in one frame). Capped, the section
  rolls to its full height and the history gives the room up.
  A move of the panel's own still in the air when a roll starts is
  carried through it (in-flight height to where the roll will leave the panel, on the roll's clock)
  rather than cancelled, since cancelling hands the used height back to layout in one frame. Two
  bubbling events bracket the roll, and both exist because a roll is not always a render the panel
  sees: `cortex:morphstart` (dispatched once the attribute is set and the animation exists) is what
  lets the panel ride along with a section whose open state is owned locally, a reply's trace being
  the one that is, and `cortex:morphend` when the attribute clears is its only word that a section
  rolling *open* has finished, since that changes no state and so triggers no render of its own.
  The observer does not retire that event and cannot: a roll ends without changing the panel's size,
  an opening one filling nothing so its last value is the height the element already has and a
  closing one filling forwards at zero, so no notification is produced anywhere near it (traced at
  900x900, the roll's last notification at t=456 and the event at t=471 with the next notification
  2.3 seconds later).
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
  each surface does: `toggleConsole(tab)` for the two openers in the hint strip (`HintStrip.tsx`,
  the row of keyboard affordances under the composer; each opener owns its
  tab, so its own button closes the console and the other switches), the idempotent
  `openConsole(tab)` for the strip, and `closeConsole()` for Esc and the header chevron, which is
  why Esc now leaves in one press instead of unstacking two sheets. Beyond those three it is the
  chat's own arms that decide the tab's fate, and the rule between them is **a conversation
  arriving on the panel brings the chat
  with it** (ADR-0035 addendum, 2026-08-03): `newChat` and `openSession` clear the tab, so Ctrl+N
  and the Ctrl+Up / Ctrl+Down cycle land in the conversation they were aimed at instead of
  emptying or swapping it behind a standing console (those two keys are the whole reachable
  surface, the pencil and
  the switcher rows being under the console); a summon clears it too, and a
  dismiss deliberately does not, the panel fading out with the tab it had open. **The `?` key is the
  third control that reaches `toggleConsole`, and the only one that can be pressed off the chat**, so since
  2026-08-07 that arm lands on the chat as the swap arms do and asks the SCREEN whether the tab is
  already up (`mode === "panel" && consoleTab === tab`) instead of asking the flag; `Ctrl+K` does
  the same for the switcher, and off the chat both OPEN rather than toggle, a reader who cannot
  see a section having none to close (ADR-0035 addendum, 2026-08-07). `sessionDeleted` and
  `adoptSession` leave it exactly as it was, the first because a delete comes from a switcher row
  and keeps the surface the user is managing chats in (as it already keeps the switcher open), the
  second because a cold-start restore must take nothing off the panel. `CONSOLE_TABS` is exported
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
  composer, whose `arrival` prop is the arrival count while "the panel is open AND no console tab is
  up" and null otherwise, so a return from the console is the same landing a swap is. That is not
  decoration: a browser does not hide the focused element's ancestor from assistive tech, so
  without the handoff the `aria-hidden` on the pane being left is ignored and the tab just left
  stays in the tree as a second, equal console.
  **The strip is a full tab list from the keyboard** (ADR-0035 addendum, 2026-08-03). It is ONE stop
  in the page's tab order, carried by a roving `tabIndex` that is 0 on the selected face and -1 on
  the others, which needs no state of its own because selection follows focus and the tab that has
  focus is the tab that is selected. `overlay/tabStrip.ts` is the pure map of what the keys do:
  ArrowLeft and ArrowRight step along the strip and wrap at both ends, Home and End go to the ends
  and do not wrap, everything else is left alone (the vertical arrows included, since Ctrl with
  those cycles chats overlay-wide). The four it answers are `preventDefault`ed, because the panel
  clips its overflow and they would scroll a box the user cannot scroll back. Focus following the
  selection is a layout effect on the tab that is up rather than an `autoFocus`, which covers the
  way in exactly as before and additionally covers a switch, the console pane not being remounted
  when the tab changes; the switch that needs it is the global `?`, which can change the tab while
  the keyboard is down among the theme tiles of the pane about to go inert. Each face also carries
  `aria-controls` naming the pane it opens, over a `useId` prefix rather than a hand-written id.
- **The empty state does not scroll; it is clipped** (`components/ChatView.tsx` + `src/overlay.css`).
  The history's children sit in one column, `.log`, which carries `bare` while the empty state is
  the whole of it (no messages and no approval card, asked of the same state the empty state itself
  is rendered from). `bare` is the one case where the column may be SHORTER than its content: it
  shrinks, centres what is left, and clips, which is what the history reads as "nothing here
  overflows" so it never offers a bar. An opening screen is a picture rather than a log, with no
  more of it further down, so a scrollbar on it offers to reveal nothing. It is the ordinary case
  and not a corner: at the body's 640x720 window the reminder stack leaves 101px of history against
  a 195px column, and the session list on top of it leaves 10px. Clipping is symmetric by
  construction, centring with negative free space overflowing both ends alike, so the mark stays on
  the middle line. Do NOT try to buy room by dropping the empty state's block padding: those 58px
  are part of the height the panel sizes itself to, so the panel shortens, the history shortens with
  it, and 58px of saving comes back as 29px of lost panel (measured 185 to 127 of content against
  101 to 72 of history). A log with any message in it keeps every one of the old rules: it is
  bottom-aligned, so a reply arrives against the composer, and it scrolls.
  One more thing decides the layout and looks like styling: the example chips are held to one row
  (`flex-wrap: nowrap`, shrinking to an ellipsis) because they are the only part of the invitation
  whose height depends on the panel's width, and everything sized against that height needs it to be
  one number. `Panel.test.tsx` pins what the stylesheet cannot defend: the structure (the empty
  state and the bubbles both inside `.log`) and which of the two the class says it is.
- **A log with messages in it stands on the empty state it replaced** (`components/ChatView.tsx` +
  `overlay/measured.ts` + `src/overlay.css`, ADR-0035 decision 12 and its 2026-08-03 addendum). The
  floor is `--chat-floor`, published from the empty state's own box while that box is on screen, so
  editing the mark, the invitation or the chips moves the floor with it. Without one the first
  message a user sends drops the panel 90px and the reply walks it back up. The one thing to know
  before touching it: the floor has to sit on `.log` and not on `.history`, because a floor on the
  scroll box cannot yield, and with both chrome sections open there is 76px of history to yield in.
- **A live activity chip and the settled "Thoughts" disclosure are one row in two states**
  (`components/Message.tsx` + `overlay/measured.ts` + `src/overlay.css`, ADR-0035 decision 13). The
  chip IS the row and publishes its own box as `--trace-row` (24px in Chromium at HEAD); the
  disclosure floors on that, so the frame where a turn completes swaps one for the other in place
  instead of easing the whole panel down by the 4px difference their natural boxes had.
  `Message.test.tsx` pins what the stylesheet cannot: that the disclosure stands exactly where the
  chip stood, one row for one row, and that whichever chip a turn shows says how tall it is.
- **The confirmation card** (`components/ConfirmCard.tsx` + `components/draftValue.ts`,
  ADR-0022): the gated call's `argumentsJson` as key/value rows, shown verbatim because what is
  approved is what runs (a malformed one falls back to the raw string). `formatDraftValue`
  renders one value: a string is untouched, so newlines stay newlines; an object or array becomes
  indented `key: value` lines, which is what lets an attachment's content read as a file instead
  of as escaped JSON. It reads JSON shapes and never a tool's schema. The draft block caps at
  `42vh` and scrolls, so a long draft cannot push Approve and Deny out of view.
- **The whispered reply** (`components/WhisperBubble.tsx` + `whisper/`, ADR-0037): an assistant
  bubble streams by condensation. `whisper/front.ts` is the pure half (the front position with
  one eased velocity, the nine-letter smoothstep band, the tokenizer that chunks giant words,
  and the confirmed-letter hold that keeps a partial trailing word invisible so a mid-word wrap
  never moves visible letters); `whisper/useWhisperClock.ts` is a rAF loop in `useMarkClock`'s
  shape that writes letter opacity and blur, the mist's transform and the bubble's posed box
  imperatively, its only `setState` being the breath-to-talking and talking-to-settled
  transitions. `whisper/metrics.ts` holds what the bubble measures about itself, the box that
  measurement poses for a front standing at a given letter (`boxFor`, so a frame and a resize
  cannot pose differently), and `watchWrap`, which re-measures on the window's own `resize` and
  reports only a wrap width that actually moved. A change re-lays the letter DOM at the new
  width; a bubble still streaming lets its next frame ease the box there, and one whose loop has
  already stopped is re-posed at once from the last letter and tells the tail pin, since nothing
  else in the overlay ever revisits a settled bubble's hard px box. The trigger is the window
  alone, which is complete while the panel's width stays viewport-derived and would not be if it
  stopped being; a `ResizeObserver` on the log is the wrong instrument here, because the log's
  height follows the posed bubble every frame and writing the text's width inside an ancestor's
  observation raises the undelivered-notifications error `overlay/panelWatch.ts` documents. Letters are INLINE spans inside the inline-block word boxes (an inline-block
  letter is laid on whole pixels and reads as a ransom note; inline keeps the text's own
  sub-pixel advances). The bubble announces its growth in the panel's roll contract
  (`overlay/morph.ts`): it carries `data-morphing` from its first spoken letter to its settle,
  so placements defer and the panel's auto height follows the box frame by frame instead of
  replaying it from a render-old measurement, which snapped the top edge backwards on every
  token (ADR-0037 addendum has the traces). The value it publishes is `tH.toFixed(1)`, the same
  rounding the box itself is written with, so the panel predicts from the height the bubble will
  stand on: rounded to a whole pixel it sat half a pixel under that at every wrap, and a summon
  landing inside the roll pinned the panel to the centre of the wrong number and kept it. The
  settle itself waits a few frames of coda for
  the mist to reach the last word, so the evaporation plays at the reply's end and never
  mid-line. The bubble latches whether the message was streaming when it mounted: history
  renders one plain text node with none of the machinery, and a message this instance streamed
  keeps its letter DOM after settling so nothing re-wraps under the reader. The letter DOM is
  `aria-hidden` behind a visually hidden copy of the content; the mist carries the "Thinking"
  label during the breath. Growth reports through `onGrow`, which `ChatView` wires to the
  history's tail pin, so the drain that outlives the last render cannot slide a pinned reader
  off the tail. Reduced motion schedules no frames: the stylesheet reveals letters as they
  arrive and a CSS floor holds the breath pill.
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
  its ceiling (filed in [refinements/index.md#body-overlay](../refinements/index.md#body-overlay)). Each delta
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
  outcome }`, ADR-0022). A `TransportError` carries its own `kind` on the same wire
  (`connection` | `rpc` | `protocol` | `timeout`, the TS `TransportErrorKind`), which the
  reducer classifies into the link exactly as `body_core::link` classifies a probe's failure. The
  eagerly dialed client is handed to a `RetryingTransport` before the turn runs on it (ADR-0024
  idle-gap addendum): that decorator does not retry a turn, exactly as the plan says, so the one
  thing wrapping buys is the bound on the stream's **silence**, which turns a brain that accepts
  the turn and then stops sending into a reported `timeout` instead of a reply that streams for as
  long as the process lives. One `RetryPlan` is read for the dial's deadline and the stream's gaps
  together, so the two cannot drift. For the turn's duration it parks a decision sender in the managed
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
  `CORTEX_BRAIN_PROBE_BUDGET_MS` as the ceiling on a `Health` probe's whole run and the two
  per-attempt deadlines, `CORTEX_BRAIN_PROBE_DEADLINE_MS` and `CORTEX_BRAIN_CALL_DEADLINE_MS`,
  plus the turn's two silences, `CORTEX_BRAIN_TURN_FIRST_GAP_MS` and
  `CORTEX_BRAIN_TURN_IDLE_GAP_MS`
  (`env_millis` parses every duration knob here, since all of them are spelled in ms). Which
  calls may be retried at all is *not* configurable here and deliberately so; that is the gated
  `RetryPlan` gate, decided by what each seam method does. `connect()` reads that plan **once**
  and hands the one value to both halves it governs, the `RetryingTransport` that enforces its
  per-attempt deadline and the client that announces it as `grpc-timeout` (`announcing(plan)`,
  ADR-0024 courtesy-header addendum): the announcement is longer than the enforced bound by the
  plan's own grace margin, and one plan value reaching both is what keeps that ordering
  structural. The read commands use `connect()`;
  `converse` keeps its **eager** dial but wraps it in `retry_with` (ADR-0024 addendum), so a turn
  started against a briefly-down brain retries the *dial* (safe: the non-idempotent turn has not
  begun) while a turn that fails after its first event stays terminal (decision 2). It first runs
  the lazy constructor as a synchronous config gate, so a bad URI or non-ASCII token fails fast
  instead of being retried for the whole budget, and each dial is wrapped in `within_deadline`
  at the plan's call deadline, so a dial that hangs cannot hang the turn behind it. The turn's
  own **length** is deliberately unbounded, a model thinking not being a failure, and its
  **silence** is not: the dialed client goes into a `RetryingTransport` carrying the same plan, so
  the stream runs under `turn_gaps` (ADR-0024 idle-gap addendum). The turn's client is
  the one that announces nothing, and needs no `announcing`: `Converse` has no deadline in the
  plan, so there is none to tell the brain about, and a gap is not a deadline the wire could
  carry.
- **The `body_server` module** (`src-tauri/src/body_server.rs`, ADR-0023/0025): `start()` (`cfg(windows)`)
  binds `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`, the port declared once as
  `DEFAULT_BODY_PORT` and tied by `scripts/crosscheck.py` to every other place that states it:
  the body override and its header comments, three runbooks, three module contracts including
  this one, the brain's gateway and its live test, and the four `docs/host/` files that tell an
  operator to export it before a sitting, ADR-0023 port and port-prose addenda), reads
  `CORTEX_SEAM_TOKEN` and
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
  probe's whole run is trimmed to so raising the read knobs cannot slow the connection
  indicator's verdict, and the two per-attempt deadlines (ADR-0024 deadline addendum)
  `CORTEX_BRAIN_PROBE_DEADLINE_MS` (250) and `CORTEX_BRAIN_CALL_DEADLINE_MS` (5000). At the
  defaults the budget leaves the probe two of the reads' three attempts, so the dot resolves
  inside 700 ms worst case and still spends one real retry on a restarting brain. The turn's own
  two knobs are the odd pair out, bounding silence rather than a call (ADR-0024 idle-gap
  addendum): `CORTEX_BRAIN_TURN_FIRST_GAP_MS` (`DEFAULT_TURN_FIRST_GAP_MS = 600000`) is the
  longest a turn may say nothing before its first event, and `CORTEX_BRAIN_TURN_IDLE_GAP_MS`
  (`DEFAULT_TURN_IDLE_GAP_MS = 7200000`) the longest between two of them. The second is the larger
  because a delegated subtask, which can only happen once a turn is under way, may wait an hour for
  admission and then run for forty minutes without the seam seeing anything.

**Invariants.**

- Components depend on the `BrainBridge` port, not Tauri, so the whole overlay is browser-runnable
  and 100%-gated; the Tauri glue is the single un-gated edge (ADR-0011 addendum).
- **Every `BrainBridge` implementation CI can run is driven over the one shared list.** A new
  implementation adds a case to `bridgeContract.test.ts`, not a suite of its own, and a new claim
  about the port is appended to `bridgeContract.ts`, where it reaches every implementation at once,
  rather than asserted against whichever one the author had open. What an implementation does that
  the port never promised is its own suite's business.
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
- **Whatever is hidden from a reader is hidden from the tab key, in the same frame and from the
  same call.** The overlay keeps three things mounted that are not on screen: the panel while it is
  dismissed, the view being left for the length of its morph, and the console's tab not showing.
  Each spreads `withdrawn(away)` (`overlay/withdrawn.ts`), which writes `aria-hidden` in both
  directions and `inert` in one, `inert` being a boolean attribute whose absence is its false. A
  fourth such place spreads the same call or it is a defect: `aria-hidden` alone leaves the subtree
  in the tab order, and CSS that takes it out (`visibility: hidden`, `display: none`) arrives after
  the fade rather than with the state change, which is the window every one of these was reachable
  in. The `inert=""` string form is deliberate and necessary: React 18 writes a string attribute
  straight through and drops a boolean one with a warning, so the empty string is how this tree
  spells a present boolean attribute until it moves to React 19
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md), 2026-08-03 addendum, has the probe).
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
  `.confirm-row dd`, `.confirm-raw`, `.reminder-text`; a whispered reply's word boxes are
  `white-space: pre` and unbreakable, so `whisper/front.ts` chunks a run of non-whitespace
  longer than 24 letters into boxes the bubble can break between, ADR-0037 decision 6, which is
  what keeps the reach inside a streamed token), and `.history` carries
  `overflow-x: clip` so a future child cannot bring the shift back.
- **The send button's hover is on the GLYPH, and the stop's is the one hue change in the overlay.**
  The arrow rises 3px on the spring while the cap holds still, which is the hover the maintainer picked
  over three that move the cap (and the only one that leaves the pill's geometry alone). Two
  exceptions carry the meaning. A `live` button keeps `#fff` through the hover, because white is
  what makes the glyph legible on the accent gradient and `--text` is near black in the light theme.
  A `stopping` button turns `--halt` on a 13% wash of it and its square eases shut rather than
  travelling: streaming, the button has swapped what it means, from how a turn begins to how one is
  called off. `--halt` is the overlay's one non-status red, named once and worn by the two controls
  that undo something in flight, this and the trash on a chat row, and only ever on hover.
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
- **The composer takes focus without scrolling anything.** The panel clips its overflow, which makes
  it a scroll container the user can never scroll and the engine can, and bringing a newly focused
  element into view is when it does. Coming back from the console the field is below the panel's
  clipped edge for the length of the ease, so `panel.scrollTop` went 0 to 139 in the frame focus
  landed and unwound over the ease, lurching every row in the window. `focus({ preventScroll: true })`
  is the fix, and anything else in here that takes focus while the panel is mid-move needs the same.
- **The composer tells the chat when the pill resizes, because the log pays for it.** They are flex
  siblings and the log is the one that yields, so a draft that restacks or wraps takes that height
  straight out of the visible window (52px, and 122px at the field's ceiling, measured at 640x720).
  `Composer` calls `onResize` when its measured height actually changes and `ChatView` answers with
  the same tail-pin it uses for a new message, reader override included. A `ResizeObserver` on the
  log would be the obvious alternative and is the wrong one: the log also resizes when a trace rolls
  open, which is a cause of its own with its own answer (`overlay/logRide.ts`) rather than a draft
  the tail pin should chase.
- **The history's scroll position is decided here, not by the engine.** `overlay/useLogScroll.ts`
  holds the log at its tail while the reader is at the tail, parks where they are otherwise and
  hands it back after a trip to the console, and ignores the scrolling the layout does on that trip
  (which is not the reader's, and which reads as sitting at the tail because the box being out of
  the flow has nothing left to scroll). A section rolling open is answered by
  `overlay/logRide.ts`: for a reader at the tail it holds their distance from it for every frame of
  the roll, so the growth comes out of the scroll rather than out of the end of the reply, capped so
  the rolling section's own top edge never leaves the window and abandoned the moment the reader
  takes the scroll back; for a reader who has scrolled up it does nothing, and the row stays under
  the pointer that opened it. The cap is the one thing that asks WHERE the section is: a roll in the
  panel's chrome (the switcher list, the reminder stack, a row leaving either) takes the log's
  window rather than growing its content, and there is nothing in the log for the reader to be
  carried away from, so nothing bounds the ride but the box's own range. Those rolls are heard on
  the column the panel renders the view into, `Panel` handing that element to `ChatView`, because
  the chrome's sections are siblings of the box and their bubbling start event goes up past it; a
  roll inside the log reaches the same listener through the box on its way. The panel's placement
  leaves
  it alone too, which it had to be taught: `place` measures the panel by growing it to the loosest
  cap any edge could allow, every scroll box inside a taller panel is a taller box, and the engine
  clamps a box that has outgrown its scroll range and does not undo it when the real cap goes back
  on. That put a reader 60px off the tail back to 97px off it on every token of a reply, so `place`
  now takes the positions before it measures and hands them back after
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md), the addendum on the second maintainer pass, has the
  traces). `.history` therefore carries
  `overflow-anchor: none`: Chromium's scroll anchoring is a third decider of the same number, and
  the roll is the only mid-log resize in the overlay for it to react to. A roll measures its content
  at full height and animates from zero, which the anchor reads as the log shrinking, and it
  compensated by 76px in one frame before walking the compensation back over the roll
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 15 has the traces; the one service it
  had been performing, easing the log down as a trace above the window closes, is the ride's now).
  A future scroll container that holds rolling content needs the same line, or its own reason not
  to.
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
[body-overlay](../runbooks/body-overlay.md).
