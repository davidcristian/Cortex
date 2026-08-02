# Body & overlay

These deferrals originate in [ADR-0011](../adr/ADR-0011-body-v1.md), the Slice 8 body v1
decision covering the host-native shell and the overlay UI, and in
[ADR-0031](../adr/ADR-0031-bubble-mark.md), the bubble mark that replaced its living rings.
Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries
are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** multi-turn-within-one-stream + proto `Cancel`, streamed
brain status (its producer landed 2026-07-18; only the push RPC remains), an exit for the
switcher's rows (the reminder stack's landed 2026-08-03 and left the hook behind for
it), the composer's move on a shrink against the ceiling (a user's choice between two
designs), two sections that are both full outrunning the panel on their own,
the demo bridge staying over the line cap, the two tradeoffs the reserved scrollbar rail accepts (its width
is assumed rather than measured off the engine, and the two 6px cards spend their whole inset on
it), the chat floor's frozen measurement of the empty state, a mid-stream retarget restarting
from a rounded height, a Thoughts trace opening a reply off the bottom of a full history, the
console tab strip's missing keyboard half, and the whisper's three follow-ups (a pickable voice
row in the console, the wrap
width a mid-stream resize cannot move, and kerning inside the letter boxes under a changed
font; its drain-growth entry landed the same day it was filed, and the console outliving a new
chat landed 2026-08-03), and a resize that lands inside the panel's own move waiting for it. A
placement left computed for a stale height, the composer's own growth being the one resize the panel
never eases, and a touch mid-roll pinning the session to a prediction all landed together on
2026-08-03, the first two as the `ResizeObserver` they asked for and the third as something else
entirely (the arrival was counting an aside the placement was counting out); the waiting resize is
the one thing that watch deliberately does not do, and was opened with it.

**Body / overlay in Slice 8 ([ADR-0011](../adr/ADR-0011-body-v1.md)):**
- **Multi-turn-within-one-stream + an explicit proto `Cancel` event.** One turn per `Converse`
  call; drop-to-cancel covers v1 (ADR-0011 decision 1 / risks). The interleaving half was
  taken by **Slice 8.8** (ADR-0022): the body's client stream now stays open past the first
  `UserTurn` to answer `ConfirmRequest`s mid-turn. Still deferred: multiple turns per call
  body-side and the client actually sending `Cancel` (drop-to-cancel remains the mechanism).
  When multiple turns per call land, Slice 8.8's single-slot `ConfirmRoute` (Tauri) and the
  `SeamConfirmer`'s "at most one confirm outstanding per stream" assumption need per-turn keying
  (a map, not one slot); the route is already generation-tagged, so the change is contained there.
  - **Read against the code 2026-07-16: the proto and the whole server half are already built and
    proven; what remains is body-side only, and its two parts are coupled so the smaller cannot
    cleanly precede the larger. Sharpened to fix-when-it-bites with the same Slice 11 trigger as
    the reconnect and streamed-status entries.** Both halves the entry names are satisfied on the
    proto and the brain:
    - **The proto `Cancel` exists** (`proto/body.proto` `Cancel cancel = 3`, in the seam since the
      first proto commit), round-tripped by `test_client_event_oneof_carries_a_cancel`
      (`brain/packages/seam/tests/test_facade.py`).
    - **The server carries multiple turns per stream and handles `Cancel` end to end.** A
      `UserTurn` arriving mid-turn is queued and starts when the running turn finishes
      (`_enqueue_turn`/`_start_next_turn`/`_drain_turns`, `converse.py`); a `Cancel` stops the
      in-flight turn and drops the queue and the stream stays open (`_cancel_turn`, dispatched from
      the pump on `kind == "cancel"`). Pinned by `test_cancel_behind_a_queued_turn_stops_current_and_drops_queued`
      (A dies mid-stream, B never runs, A's user message persisted with no partial reply) and
      `test_cancel_mid_confirm_drops_the_turn_and_the_stream_stays_open` (a pending confirm on a
      cancelled turn runs no tool and the stream survives), both in `test_converse.py` /
      `test_converse_confirm.py`.
    - **The lease-cancellation crux (the tricky part the entry flags) is clean and now has a
      dedicated proof.** The GPU lease is a non-reentrant `asyncio.Lock` held across the whole
      streaming block (`SingleResidentModelManager._lock`, taken in `LlamaCppBackend.stream` via
      `async with manager.acquire(...)`); a `CancelledError` mid-inference propagates out through
      that `async with` and frees the lock before the next turn leases it. Proven by
      `test_cancelling_mid_stream_frees_the_model_lease` (`brain/packages/inference/tests/test_backend.py`):
      it suspends a turn mid-stream with the lease held, cancels it, and asserts a fresh acquire
      returns at once. Distrust-green: releasing the lock outside a `finally` (so a mid-`yield`
      cancel skips it) deadlocks the re-acquire and reddens the test. No partial reply is persisted
      on cancel (`TurnEngine.handle_turn`'s `finally: await loop.aclose()` drops the in-flight
      generation; `test_aclose_mid_generation_keeps_user_and_drops_partial_reply`, `test_engine.py`).
    - **What is genuinely deferred is body-side and coupled.** The `BrainTransport::converse` port
      is one turn per call (`turn_request` sends exactly one `UserTurn`, `body/crates/rpc/src/converse.rs`),
      and the overlay opens a fresh `Converse` per submit (`useOverlay.ts`). A client-sent `Cancel`
      cannot cleanly precede body multi-turn: on the one-turn-per-call body, a `Cancel` then a
      half-close ends the body stream **with no terminal event** (the server emits none for a
      cancelled turn), which `converse_turn` maps to `TransportError::Protocol("converse stream
      ended before the turn completed")`. So client `Cancel` needs either multi-turn-within-one-stream
      (keep the stream and send the next `UserTurn`, the case it earns its keep) or a new terminal
      cancelled-ack (a server-semantics change), and multi-turn-within-one-stream carries the
      per-turn-confirm-keying knock-on above.
    - **Today's Stop is UI-only in the Tauri embedding, and that is why the deferral is
      fix-when-it-bites rather than actionable-now.** The overlay's Stop denies a pending confirm
      and mutes the JS sink (`tauriBridge.ts` sets `live = false`), but does not half-close or abort
      the RPC (documented in `useOverlay.ts`), so the Rust `converse` command streams the turn to
      completion: the brain finishes generating, persists the **full** reply, and holds the lease
      until the turn ends naturally. Drop-to-cancel therefore behaves as "stop showing me this
      turn", not "abort the compute", and the overlay can show a truncated reply while the store
      keeps the full one. That is adequate at loopback personal scale where compute is cheap; a real
      abort (release the lease, drop the partial, keep the store consistent) earns its keep only when
      Slice 11's real model swap makes mid-turn compute expensive and evictable, the same trigger
      the reconnect and streamed-brain-status deferrals wait on. The clean v1 fix for one-turn-per-call
      is a real drop-to-cancel: make the Tauri command abort its RPC on Stop (a body-local signal, no
      proto change), which the brain already tears down cleanly through `events()`'s finally. Both
      that and the multi-turn+`Cancel` build live entirely in the ungated, host-validated Tauri
      shell + overlay glue, so neither is a gated slice today.
- **Deferred overlay polish moved to [docs/host/overlay-polish.md](../host/overlay-polish.md) on
  2026-07-19** with its text kept verbatim. It was the one entry in this whole backlog that is
  **authoring by the user** rather than deferred design anyone can pick up: a transparent window
  and click-through margins can only be judged against a real Win32 window, and a first attempt
  bled through the panel and left a border. Leaving it here would have meant this backlog could
  not empty until the maintainer wrote Rust, which is the wrong contract for a backlog whose emptiness
  gates the README. The design source is unchanged
  ([overlay-ux.md §4](../design/overlay-ux.md), [body-overlay.md](../runbooks/body-overlay.md),
  ADR-0011's 2026-07-03 addendum), and the design doc's smaller "later" marks (custom theme token
  sets, a licensed `@font-face`, a `Ctrl+K` command palette) ride along in §2-3 of the same doc.
- **A real connection indicator landed 2026-07-16 ([ADR-0011 addendum](../adr/ADR-0011-body-v1.md)),
  without the status stream this entry expected.** The entry text was accurate about the code
  (`Health` exists, `BrainBridge` did not carry it) and wrong about the shape of the answer: it
  assumed the indicator had to wait for a slice that *streams* brain status. It did not. The
  honest signal was already derivable from what the overlay does anyway, and a poll was the
  design to avoid, not the design to build. What shipped, in order of cost: every `TurnEvent`
  is proof the brain is serving and every transport failure is proof it is not, both already in
  the reducer (so a live turn keeps the dot exact for free); one probe per **summon**, latched
  on the rising edge of visibility (`useSummonEffect`, shared with the reminder pull); and a
  recovery re-check every 5 s **only while the overlay is visible and the link is not ready**,
  which stops the moment it answers ready, so a healthy system spends nothing. A liveness poll
  was rejected outright: it burns a request per interval forever, mostly while nobody is
  looking, and is still stale in exactly the window the turn covers for free.
  **Four states, not three:** `ready` (green), `degraded` (amber, the brain **answered** and is
  not serving: a non-OK status such as `Unauthenticated` for a bad seam token, an unreadable
  reply, or a future `ready = false`), `down` (red, `Connection`, the only failure where nothing
  answered), and `unknown` (neutral, not asked yet, because the v1 dot's sin was claiming a
  state it had not earned). "Connecting" is deliberately a modifier rather than a state: the dot
  keeps its last known colour and pulses, and the probe itself rides the retrying transport, so
  one probe already spans the reconnect window. Classification is pure and gated
  (`body_core::link`), CI-gated at 100% on both sides, browser-validated in both themes, and
  checked against a real brain by the `body-rpc` live suite (`Ready` from a running brain,
  `Down` from a dead address). **One defect the gate caught:** re-arming the recovery check off
  each answer dies after a single retry when the probe resolves inside one React batch, since
  the in-flight flip is never rendered; it is an interval keyed on "visible and unhealthy"
  because of that.
- **Streamed brain status (opened 2026-07-16 behind the landed indicator).** The push half this
  entry originally assumed, still unbuilt, and now with a named blocker rather than a wish:
  **nothing produces a status the overlay cannot ask for.** The brain's `Health` answers
  `ready = True` unconditionally (`server.py`), and a mid-turn `StatusUpdate` already reaches
  the overlay on the `Converse` stream as a chip. So the amber "not ready" path ships shaped and
  tested with no producer, and the rule that any successful call means ready is honest only
  while that holds. Both change together when the model manager (Slice 11) can make the brain
  not-ready *between* turns: that is when a push earns its keep and when "any success means
  ready" stops being true.
  **Half the producer landed 2026-07-17 with the brain-handoff conductor
  ([ADR-0030](../adr/ADR-0030-brain-handoff.md) decisions 6 and 7).** An escalating turn now
  streams `StatusUpdate(state="swapping")` through drain, load, work, and restore on the
  `Converse` stream the user already holds, so the swap window says what it is doing, with no
  proto change (the overlay renders it as a chip today).
  **The producer is whole as of 2026-07-18** (the honesty-surfaces sub-slice, ADR-0030 decision
  6): `Health` reads the swapping manager's published residency and answers `ready=false` with a
  truthful detail while the deep model is loading, working, or being swapped back, after a
  restore that gave up, and (from the 2026-07-18 audit repair) after a boot whose recovery could
  not settle the cortex, which was the one machine state the first landing still called ready.
  The blocker this entry named is therefore met and the entry is **no
  longer blocked**, with **zero overlay change**, exactly as designed: the landed indicator
  already classifies a not-ready reply as amber `Degraded` and shows the brain's line verbatim,
  and the 5 s recheck (visible-and-unhealthy) turns it green again on its own when the cortex is
  back. Two limits worth knowing before the push half is designed against them. The amber shows
  **between** turns only: the reducer folds every streamed event as proof of serving, so during
  the escalating turn's own stream the dot is green and the chips carry the story instead. And a
  handoff's **drain** is deliberately still ready, the cortex being resident and answering
  throughout it. What remains deferred is only the **push** itself: a server-streamed status RPC
  is a seam change (proto + both stubs + a consumer), and probe-on-summon plus the escalating
  stream's own chips cover personal scale, so it waits for a consumer that needs the brain to
  speak first.
- **Design-doc interaction gaps closed 2026-07-12 ([ADR-0011 addendum](../adr/ADR-0011-body-v1.md)).**
  All nine items surfaced by the 2026-07-03 browser pass landed behind the unchanged
  `BrainBridge` port / reducer, CI-gated at 100% and browser-validated in both themes: history
  auto-scroll while streaming (a pinned-at-bottom latch; scrolling up holds the reader's place),
  composer focus-on-summon, click-away dismiss (the Esc path: orb mid-stream, hidden idle), the
  tool/status chips the reducer already tracked (slim accent-dotted pills above the streaming
  bubble, giving the ADR-0020 thinking status a visible surface), the empty-state mark + tappable
  example prompts, the pre-first-token thinking shimmer, the `?` shortcut sheet (`sheetOpen` in
  the reducer; Esc closes it before dismissing), composer auto-grow, and preview **hover now
  pausing the fade timer itself** (leaving restarts the full countdown, with the drain bar
  remounting in step so bar and timer always agree).
  **The streaming stop control landed 2026-07-07**. The send button becomes a real stop mid-turn
  (a `stop` reducer action drops the stream via the bridge `Cancellation` and ends the reply in
  place); browser-verified. The header/composer glyphs were also unified onto one outline icon set
  (`components/icons.tsx`) the same day.

**The bubble mark ([ADR-0031](../adr/ADR-0031-bubble-mark.md), 2026-07-19):**
- **Appearance choices do not survive a restart. LANDED the same day
  ([ADR-0032](../adr/ADR-0032-preference-record.md)), by the option this entry called the more
  expensive one.** The entry recorded two choices and declined to pick: `localStorage` in the
  webview, or a preferences record the brain owns. The maintainer chose the brain's record, so what
  shipped is a `PreferenceStore` port with a Redis adapter, two RPCs on `BrainService`, and
  `usePreferences` hydrating the theme and mark at mount. The entry's framing held up: this was
  the overlay's first persistence of any kind, and the reason to prefer the record was exactly
  what the entry said, that it survives a reinstall and reaches surfaces other than the window
  that set it. One thing the entry did not anticipate: because the record arrives a round trip
  after mount, hydration had to be taught not to overwrite a choice made in that window, which is
  the feature's only real race and now has its own test.
- **The mark picker has no click-away close and no other route in. LANDED the same day**
  ([ADR-0032](../adr/ADR-0032-preference-record.md)), and the entry's own diagnosis is what fixed
  it: both symptoms were the missing settings surface, so a settings sheet shipped (theme + mark,
  opened from the hint strip or from the mark itself) and `MarkPicker` was deleted rather than
  patched. Neither affordance needed to be built in the end. There is no inline popover left to
  click away from, and the sheet is reachable from a chat that already has messages. The entry
  guessed the `Ctrl+K` command palette would be the host; a sheet in the shortcut-sheet family
  turned out to be the smaller step, and the palette can absorb it later without changing where
  the choices live.

**The panel's size ([ADR-0033](../adr/ADR-0033-panel-growth.md), 2026-07-19):**
- **Sections do not animate out.** *Landed 2026-07-19*
  ([ADR-0034](../adr/ADR-0034-panel-views.md) decision 4.) The deferral read: the panel's size
  change eases in both directions, but the section itself vanishes on the first frame because
  React unmounts a removed child immediately, and animating an exit means keeping the element
  mounted through it. That is exactly what shipped, and the guess about the cost was right and
  the guess about the symptom was wrong. It cost one component (`components/Collapse.tsx`, which
  holds its children through the close and animates its own height) and no reducer change at all.
  But the asymmetry was not "barely visible": the section's rows vanished, everything below them
  snapped up into the hole, and the panel eased down afterwards, which the user reported as the
  animation feeling wrong. Two lessons for the next entry of this shape. A defect described as
  cosmetic deserves one look at the actual frames before it is sized, and "the collapse the eye
  follows is the panel's" was an assumption about what the eye follows, made without watching it.

**The panel's views ([ADR-0034](../adr/ADR-0034-panel-views.md), 2026-07-19):**
- **A single reminder leaving the stack still goes in one frame.** `Collapse` wraps the whole
  stack, so the stack rolls shut when the last reminder is acked, but acking one of three just
  deletes that row. The history absorbs the slack rather than jerking the composer, so what is left
  is one row's worth of instant against a smooth panel.
  Fixing it properly is a `usePresence(items, key)` hook that keeps a removed item rendered until
  its own roll finishes, which the switcher's rows would want too. Deferred as genuinely small,
  not as invisible: it is one row, and the surrounding motion no longer amplifies it.
  - **LANDED 2026-08-03 as the hook this entry named, and the entry was stale about the defect
    while being right about the fix** ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)).
    Half of what it describes had been fixed on 2026-07-20, the day after it was written, by the
    settings-tab slice: the stack has wrapped each ROW in its own `Collapse` since then, and traced
    at 60Hz that roll is the right one, the acked row running 57.25px to 0 while its neighbour
    travels the same distance in the same frames. Nobody closed the entry. What was left underneath
    it was not motion at all and was worse than "one row's worth of instant": that first version
    held the row by holding the ACK, behind a `setTimeout(MORPH_ROLL_MS)` whose unmount cleanup
    cancelled it, and the stack is keyed to the chat it belongs to. Measured at 900x900 over the
    demo bridge, acking the middle of three reminders and pressing Ctrl+N 100ms later left all three
    cards on screen and a fresh summon listed all three again: the gesture had done nothing. The
    same local list never forgot an id either, so a reminder that came back, which is exactly what a
    lost ack leaves behind, rendered into a `Collapse` that was already shut and stayed invisible
    for the life of the panel. `overlay/usePresence.ts` inverts it: the ack goes up in the frame the
    check is pressed, the reducer drops the reminder as it always did, and the ROW is what is held,
    at the index it kept, until its own `Collapse` reports the roll over through a new `onClosed`.
    The hook owns no clock, `MORPH_ROLL_MS` and `EASING` staying the one vocabulary, and it is
    written to be shared with the switcher's rows, which are not wired to it (a new deferral,
    below). Two repairs came with the restructure, both live and unnoticed since the wrapper landed:
    the stack's `<ul>` had `<div>` children, so it was not a list to a screen reader, and the
    hairline between two rows is an adjacent-sibling rule that two rows in two wrappers cannot
    satisfy, so it had been switched off (computed `border-top-width` 0px on all three rows; the
    stack now measures 187.75px where it measured 185.75px, which is the two restored hairlines
    exactly). One lesson is worth more than the feature: the hook's first shape remembered its last
    render by writing a ref DURING the render, passed every test written against it, and dropped the
    row on the first frame in a real browser, because `StrictMode` invokes a render twice and the
    second pass read back what the first had written. A hook deriving from what it rendered last
    time has to mean the last COMMIT, and only an effect knows which render that was.
- **Two richer directions for the settings and shortcuts views were open, and are CLOSED
  2026-07-20.** What shipped first was the plainest of three pitched to the user: rows, hairlines,
  one way back. The maintainer picked the other two together, and both were built as predicted, inner
  markup on plumbing that did not move: the theme choices are thumbnails of the panel wearing each
  theme, and the two destinations are one console with a tab strip
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 1). The motion is the panel's
  existing view morph, because the tab is part of the view name, so nothing about the geometry
  changed.

**The console and the motion a user's eye corrected
([ADR-0035](../adr/ADR-0035-console-and-motion.md), 2026-07-20):**
- **A shrink while the panel is against its ceiling still moves the composer, and only the user
  can settle it.** Two of the four fixes pull in opposite directions once the panel is tall enough
  to be clamped: keeping the pinned edge unclamped is what makes the switcher's round trip exactly
  reversible ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 4), and it is also what pulls
  the bottom edge back toward that pinned edge the moment a shrink gives it room, which is the one
  thing the maintainer asked never to happen. Centring the summon (decision 8) took it from constant to
  rare: measured at a 900px viewport, a correctly pinned panel has to grow 615px before the ceiling
  binds at all, and acking a reminder, the pencil on a chat with a full reply in it, and a switcher
  round trip now all move the composer 0px where they moved it 40, 13 and 3 before. A long
  conversation still reaches the ceiling, and there it is a real choice, not a bug to be found: the
  alternative design re-pins to the clamped edge on every content change (so the composer never
  moves) and saves the pre-roll edge PER SECTION to hand back when that section rolls shut (so the
  switcher's round trip stays reversible), at the cost of a panel that keeps whatever low edge its
  tallest moment left it with until the next summon or view change. The user has been shown both;
  this waits on which they want. Measured 2026-07-20.
- **A touch mid-roll leaves the session pinned to a prediction, not to a measurement.** The summon's
  hold on the panel's geometry ends the moment the user touches it
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 8), and if that touch lands while a section
  is still rolling in behind the summon, the last arrival-time placement was the ride-along, which
  places the panel for the height it PREDICTS the roll will reach. The measurement that would have
  corrected it (`cortex:morphend`, at the end of the roll) is no longer an arrival, so the
  prediction's own error becomes the session's pinned edge. Measured 2026-07-20 at a 900px viewport:
  the reminder stack predicts 550px where it lands on 546, and a switcher round trip started 100ms
  or 300ms after the summon leaves the panel's bottom edge 725px down the viewport against a true
  centre of 722.9, where one started after the roll had finished lands on 723 exactly. It is 2.1px, it is stable rather than
  drifting, and it is the same 4px prediction error that the entry below is about from the other
  end. The fix is the same `ResizeObserver` that entry wants, which would make the roll's real
  height available continuously rather than at its end.
  - **LANDED 2026-08-03, and the entry was wrong about the cause, the size and the fix**
    ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). The prediction cannot be wrong in
    the way this describes: the rolling section's current height cancels out of it (the panel will
    be as tall as it is now, less what the section takes now, plus what it is about to take) and a
    roll is announced at its START, where both readings are taken in the same frame. What the
    ride-along got wrong was the ASIDE. It asked whether the section that is ROLLING is the reminder
    stack, where `centringHeight` asks whether the view being placed HAS one, so a stack merely
    standing in the panel while something else rolled was counted into the arrival's centring and
    out of the placement's. Measured at 900x1000 over the demo with Ctrl+N pressed while the
    switcher list is open, which summons the panel and rolls that list shut in one commit with the
    stack standing through both: the summon pinned the edge at 227 and the placement at the end of
    the roll re-centred it to 324, so the panel's bottom edge travelled 97px down the viewport
    across the roll and came back at the end of it, and a key pressed inside the arrival window,
    which is what stops that placement re-centring, left the session pinned 97px low for the rest of
    it. That is 97px and a visible excursion, not 2.1px of stable error. The ride-along now counts
    its prediction through `centringHeight` itself, bounded at `openHeight` before the aside comes
    off because that is the order the measurement happens in, so the arrival and the placement agree
    by construction: the bottom edge holds at 676 for every frame of that roll and settles there
    whether the panel is touched mid-roll or not, at 900x900 (edge 274, the panel on its ceiling)
    and 900x1000 (edge 324) alike. The `ResizeObserver` the entry expected to retire it had nothing
    to do with it, and the aside's own roll behind a summon never had the defect, the two spellings
    being the same number for that case.
- **A placement can be left computed for a height the panel no longer has.** `usePanelMotion` runs
  on renders and on `cortex:morphend`, so content that resizes the panel without either (the demo's
  canned chat settles 1.9px after its last render) leaves the last placement standing. It is
  half-priced now that the resting panel is centred rather than derived from the ceiling, a stale
  height costing half its error rather than all of it: measured 2026-07-20 at a 900px viewport, the
  panel rests at `bottom: 177px` where its real 545.75px earns 177.1px, and every switcher round
  trip after it is bit-exact. The fix is a `ResizeObserver` on the panel driving the same placement
  the morph end event does, which would also retire the event; the care needed is that the observer
  must not fight the animations, since every placement resizes the element it is watching.
  - **LANDED 2026-08-03 as the observer this entry names, `overlay/panelWatch.ts`, and the event
    STAYS** ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). It cannot be retired,
    which the observer is itself the instrument for saying: a roll ends without changing the panel's
    size at all, an opening roll filling nothing so its last value is the height the element already
    has and a closing one filling forwards at zero. Instrumented at 900x900 across the reminder
    stack's roll, the last notification lands at t=456 with the panel at 518 and `cortex:morphend`
    fires at t=471 with none anywhere near it, the next arriving 2.3 seconds later when a
    conversation is loaded. The published cost did not move and could not have: it was at most a
    pixel by this entry's own measurement, and the demo's canned chat no longer settles after its
    last render at all, so that 1.9px could not be reproduced at HEAD. What changed is that the
    panel is now placed for the height it has. The general case, measured rather than argued: 40px
    of content appended straight into the log from the console, where React never hears about it,
    moved the panel's top edge 368.13 to 328.13 in one frame before, and now runs 368.13, 365.77,
    355.66, 342.16, 334.52, 330.59, 328.67, 328.02, 328.13 over about 120ms. The care this entry
    names is the whole of the design and is written out in the addendum: a roll owns the height, a
    move of the panel's own owns it too, a reading with nothing behind it is answered with nothing,
    and the watch is lifted for the frame the panel writes in, because an observer that resizes its
    own target inside its own callback is the one case the specification's depth rule cannot
    deliver and reports as a loop error (measured over the demo: one error event per keystroke that
    grew the pill, now zero).
- **The composer's own growth is the one resize the panel never eases, and the restack made it
  bigger.** `usePanelMotion` is driven by renders of `Panel` and by a roll's end event, and the
  draft lives in `Composer`'s own state, so a field growing a line re-renders nothing above the
  composer and `place` is never called: the panel's `auto` height simply follows in the frame the
  character lands, with the bottom edge pinned, so nothing slides under the hand but nothing eases
  either. That was 16px a wrapped line before
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 17) and the restack put a whole button row
  into the same unpainted frame, so the size of the step now depends on what the keystroke did.
  rAF-traced at 640x720 with the reminder stack acked, reading the panel's top edge across two
  consecutive samples with no third state between them:
  - **16px**, a further line on an already-stacked pill (229 to 213). Unchanged, and the common case.
  - **36px**, the character that restacks a one-line draft (281 to 245). The wrapping character
    always lands in the band decision 17 describes, so the field is still one line at the stacked
    width and only the button's row is new. The line it wrapped to arrives a few characters later
    as a separate 16px step.
  - **52px**, one keystroke that restacks AND adds a line at once (281 to 229). Shift+Enter on a
    one-line draft is the reachable case: a typed newline needs two lines at any width, so the band
    cannot absorb it.
  - **122px**, a paste that fills the field to its 120px ceiling from one line (281 to 159). The
    ceiling bounds the whole entry: no single frame can be worse than this one.

  The send button and the pill's bottom edge are identical in every sample of all four (the button
  read `top 547, left 541` throughout), which is why it ships: it reads as a relayout under a still
  hand rather than as a jump. The fix is the `ResizeObserver` the entry above wants: the panel
  would then ease its own content's growth from wherever it is, and the composer would be its
  largest and most frequent case. Filed rather than taken here because driving `place` from a
  non-render is exactly the care that entry names (the observer must not fight the animations,
  every placement resizing the element being watched), and it is a panel-motion change rather than
  a composer one. What the growth costs the history is NOT part of this entry: the log now holds
  its own tail across a pill resize ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 18), so
  what is left here is the easing and nothing else. Measured 2026-07-20.
  - **LANDED 2026-08-03 on the watch the entry above asked for**
    ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). All four steps are now paced eases
    rather than one unpainted frame, re-measured at 640x720 with the stack acked, per animation
    frame, reading the panel's top edge after the placement has run in each. A further line on an
    already stacked pill: 148, 147.13, 143.11, 137.64, 134.61, 133.03, 132.28, 132.02, 132. The
    character that restacks a one-line draft: 184, 182.02, 172.98, 160.75, 153.86, 150.33, 148.61,
    148.02, 148. A Shift+Enter that restacks and adds a line at once: 184, 181.14, 168.08, 150.41,
    140.5, 135.34, 132.88, 132.03, 132, largest single frame 17.67px against the 52 it was. A paste
    that fills the field to its ceiling: 184, 180.98, 168.19, 141.92, 118.2, 103.77, 95.05, 89.92,
    87.14, 86.06, 86, largest single frame 26.27px. That last total is 98px rather than the 122 this
    entry published, and the difference is not the fix: the panel is on its own ceiling at that
    size, so the history absorbs the other 24. The one thing that looked like a regression is not
    one: `requestAnimationFrame` runs BEFORE the resize observer steps, so a trace taken there reads
    the frame's layout before the placement has had its say and appears to show the panel jumping to
    the new height and back. A second observer reading the same frame after the placement reads the
    OLD height with one animation attached (352 where the rAF probe read 404), so the frame paints
    the height the panel had and eases from it.
- **A resize that lands inside the panel's own move waits for that move rather than joining it.**
  Opened 2026-08-03 with the panel's watch on its own box
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md), the 2026-08-03 addendum). The watch refuses a
  reading while the panel's own ease is running, because answering one would cancel that ease to
  measure the natural box and start another, once per frame, which is the mid-stream retarget the
  entry below is about arriving sixty times a second instead of once per token. So a keystroke that
  grows the pill while the panel is already moving is not eased until the move it landed inside has
  landed. **The cost is latency and not a jump**, which is what makes it a deferral rather than a
  defect: traced at 900x1000 with 200px injected into the log and 40px more injected 100ms into the
  resulting ease, the first move runs the top edge 368 to 168 over about 316ms with the second
  growth invisible throughout (the running height animation overrides the box it would have
  changed), the frame that hands the element back reads 168, the frame after reads 165.83, and the
  residue eases 40px to 128 over about 120ms, monotonic, with no step anywhere. The wait is bounded
  by the 380ms move ceiling ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 7) and is
  usually far shorter, and during a stream the panel's own renders cover most of it, a token landing
  about every 55ms. The fix is not a second observer but whatever answers the mid-stream retarget
  below, since both want a move that can be redirected from where it is without being restarted;
  taken separately, this one would simply reintroduce that harm.
- **A switcher and a reminder stack that are both full outrun the panel before the composer is
  asked for anything.** `.switcher` may be `40vh` and `.reminders` `30vh`, each capped as if it
  were alone with the panel, and at the body's 720px window that is 504px of a 547px panel with the
  header (54px) and the hint strip (33px) still to place. The composer now yields down to one row
  of field plus its button row before the panel's edge does
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 19), which is what turned this from "the
  pill and the hint strip are outside the panel" into "the hint strip is", and the pill's 84px
  floor is where the yielding stops. Forced with the panel's ceiling overridden to 300px and a
  draft at the field's ceiling: the pill floors at 84px with its text and its button inside it and
  the hint strip 34.75px past the clipped edge, where at the real 640x720 with both sections full
  everything is inside (the hint strip clears the edge by 1px, the same 1px it clears it by with an
  empty field). The fix is a cap that knows about its neighbours, since the two `vh` numbers cannot
  both be right at once; what makes it a deferral rather than a defect is that the sections are the
  user's own transient chrome, both are dismissible, and the state needs a full list AND a full
  stack AND a draft at the ceiling to reach. Measured 2026-07-20.
- ~~**Two overlay modules are over the 300-line cap the TypeScript trees are not machine-gated at.**~~
  **Struck 2026-07-20: both were split along exactly the seams predicted here.** `overlayState.ts`
  went from 394 to 241 by handing the turn-event fold to `overlay/turnState.ts` (171: `Message`,
  `PendingConfirm`, `CAPTURE_SCREEN_TOOL`, `submit`, `applyEvent` and its helpers, `isTurnActive`,
  `latestReply`), which is the third file to leave the way `sessionState.ts` did and re-enters
  through the same re-export, so no call site moved. `useOverlay.ts` went from 321 to 181 by
  handing the chat catalog to `overlay/useSessionCatalog.ts` (170: the list refresh and its two
  triggers, cold-start adoption, open, rename, delete, pin, cycle), whose members the controller
  spreads in verbatim, so a component still sees one flat interface. The turn half kept what a turn
  is and gained `abandonTurn`, the deny-then-close pair that four call sites had written out by
  hand and the catalog needs. `scripts/linecap.py` still scans `.py` and `.rs` only, so nothing
  machine-enforced changed; what changed is that AGENTS.md's cap, which is about cognitive load and
  does not care which toolchain a file is in, is now met.
- **`bridge/demoBridge.ts` (326) is the one overlay source still over that cap, and staying.**
  It is the browser-dev fake, coverage-excluded as the frontend analog of the real Tauri bridge and
  exercised by hand rather than in CI. The obvious split is its canned script (the reply, the
  reasoning trace, the gated draft, the outage details) into a constants module, and that module
  would be 0% covered the moment it existed, since no test imports the demo bridge. So the split
  costs a new entry in `vite.config.ts`'s coverage `exclude` list, and widening that list is a
  bigger concession than a long dev-only fake. The trigger is the demo growing a second behaviour
  worth testing, at which point the script becomes real data with a real test and the exclusion
  question answers itself.

**Scrollbars as reserved chrome ([overlay-ux.md §2](../design/overlay-ux.md),
[ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 22, 2026-07-20):**
- **The reserved rail is exactly 6px only on the engine that ships.** Every scroll container holds
  `scrollbar-gutter: stable` and funds the rail out of its own inline-end padding, either
  subtracted from a padding big enough to hold it (`calc(16px - var(--rail))` on `.history` and
  `.rows`, the whole 6px inset on `.switcher` and `.reminders`) or added beside it where there was
  none to spend (`.thoughts-body`, `.confirm-draft`, `.field`). Every one of those numbers assumes
  the reserved rail really is `--rail`, which holds wherever `::-webkit-scrollbar` sets the width
  and nowhere else. Chromium honours the standards properties **over** the pseudo-elements when
  both are set, so leaving them both unfenced would reserve a band the padding never accounted for:
  measured 2026-07-20 on `.switcher`, the shipped fence gives a computed `scrollbar-width: auto`
  and a 6px gutter, and adding `scrollbar-width: thin` alone takes the gutter to 10px and 4px off
  the content width. The standards path is therefore fenced behind
  `@supports not selector(::-webkit-scrollbar)`, where `thin` is whatever the UA says it is. On
  those engines the subtraction does not balance and the inline-end margin reads a few px wider
  than the other side. The property that matters survives (nothing moves when the bar appears,
  because the gutter is reserved either way); what is lost is exact symmetry on an engine the body
  does not run on. The fix, whenever one of them becomes a target, is to stop assuming the width
  and measure it: a probe element read once at startup (`offsetWidth - clientWidth`) published back
  as `--rail` makes every subtraction true on any engine, at the cost of a small module and its
  tests, which is why it is not in a CSS-only slice.
- **The switcher and the reminder stack spend their whole inset on the rail.** Both cards carry a
  6px pad, which is exactly the rail, so their inline-end padding goes to 0 and the reserved gutter
  becomes the inset. That keeps the resting geometry (measured 2026-07-20: rows at x 190, width
  520, whether or not the list scrolls) and it costs the one thing spending a whole inset can cost:
  a row's box now reaches the reserved band. The painted thumb clears the right-most child box by
  1px (card inner right edge 716, thumb painted 711 to 714, row box ending at 710). Only the box
  gets that close, which is worth stating precisely because the box is not what the eye sees: the
  hairline between two reminders is a border-top on a 12px-radius row, so its straight run ends at
  697 (698 in the light theme) and its corner curve's last tinted pixel is 701, leaving nine
  untouched columns before the thumb's first at 711. Read off the border row's pixels in both
  themes at deviceScaleFactor 1, 2026-07-20. Text and controls are
  still 9px to 11px clear, because each row pads itself, and the row ends exactly where it ended
  before this change, so nothing regressed. Two things bring it back: a row that ever drops its own
  horizontal padding (the 6px has to go back on the card, and the inline-end inset becomes 12px
  against a 6px left unless the rail is narrowed for these two cards), or the maintainer reading the
  rail as touching the chrome. Either way it is a padding line, and both cards are already
  commented with the arithmetic.

**The chat's floor under the empty state ([overlay-ux.md §3](../design/overlay-ux.md),
[ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 12, 2026-07-20):**
- **The floor is a number in a stylesheet, and nothing checks it against the empty state.** The
  panel no longer shrinks when the first message is sent, because `.log` carries a `min-height` of
  185px: the empty state's own height, measured in Chromium at 640x720 and at 900x900, where it
  comes out the same because none of it is viewport-height-derived (32px of padding, a 54px mark,
  13px, a 16px line, 13px, a 31px row of chips, 26px). That is a measurement frozen into CSS. Change
  the mark's size, the invitation's font, or the number of example chips and the two drift: too low
  and the panel dips again by the difference, too high and the empty state gains that much dead
  space around the chips, split above and below by its `margin: auto`. Neither is dangerous at the few-px
  scale, and the CSS comment carries the arithmetic so the check is possible by hand; what is
  missing is that anything does it. Viewport *width* used to be one input the number quietly had,
  since `.empty-chips` was `flex-wrap: wrap`: measured across widths, the two chips sat on one row
  at 580px and above (185px) and took a second row at 560px and below (224px), so a first send in a
  560px window cost the panel 39px. **That half was closed on 2026-07-20**, not because the window
  became reachable but because a finer sweep showed the margin was thin: the labels wrap at a 526px
  panel and the shipping 640px window gives them a 560px one, so the clearance is 32px of label
  width, which the same string in Segoe UI could eat. The chips are now held to one row and shrink
  to an ellipsis rather than wrapping (`.empty-chips`, `flex-wrap: nowrap` with the caps that make
  the shrinking reach them), measured at 185px at every width from 700px down to 440px with no
  horizontal overflow, so the number no longer depends on width in any engine. The engine is still
  the same question asked once about the rest: 185px was measured on Chromium under Linux, and the body renders on WebView2 with
  Segoe UI, where the invitation's line box and the chips' height are the parts that could come out
  a pixel or two different. Same few-px consequence, and the same fix retires it. The version that
  cannot drift measures the rendered empty state once at startup and publishes it as a custom
  property the floor reads, which is the same probe the reserved rail's assumed width wants
  (above), and a shared one would answer both. It stays
  deferred because a CSS-only fix bought the whole behaviour, and a module plus its tests is a
  larger thing than the defect it would prevent. A structural test (`Panel.test.tsx`, "keeps the
  invitation and the bubbles that replace it in the same floored column") pins the other half: the
  floor only works while the empty state and the bubbles share the column it is on, which no
  stylesheet can defend.
- **A settled reasoning reply still shrinks the panel by about 4px.** *Landed 2026-07-20*
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 13.) The deferral read: traced at 60Hz at a
  900px viewport while verifying the floor, through the first send and the whole streamed reply the
  panel only grows, from 546px to 582px, and then eases *down* to 577.6px over about 130ms at the
  end. The cause is not the floor and not the geometry: it is the moment the turn completes, where
  the live thinking chip is dropped and the accumulated trace reappears as the collapsed "Thoughts"
  disclosure (ADR-0020 addendum), which is 4.5px shorter than the chip it replaces. The panel is
  correctly following its content; the content is what changes size. It is invisible on the body's
  own 720px window, where a chat that has streamed a reply is already against its ceiling. The fix
  is a component one (give the settled disclosure the chip's resting height, or cross-fade the two
  in place), not a motion one.

  The first of the two named fixes is what shipped, and both the diagnosis and the size were right:
  the chip is 24px and the disclosure was 20px, both single-line boxes of the same 12px text, so
  the whole of the difference was 8px of chip padding plus 2px of border against 6px of summary
  padding. Both rules now floor on `--trace-row`, and the summary centres its label in the taller
  box so the text does not step up 5px at the same moment. A/B in one browser session, with the old
  heights restored by an override, put the numbers past argument: 4.73px of descent over 11 frames
  became 0.19px over two, which is the sub-pixel snap where a predicted height and the natural one
  disagree, and the panel ends the turn at its maximum rather than 4.4px under it. The one thing
  the deferral did not say is that the pairing is a *contract*, not a coincidence, so it now has a
  structural test (`Message.test.tsx`, "settles the live thinking chip into the disclosure in
  place, one row for one row"): matching heights only mean anything while the two are one row in
  two states, and a second settled row or an empty slot would put the shrink straight back.
- **A move retargeted mid-stream restarts from a rounded height.** The panel measures itself with
  `offsetHeight` (`overlay/panelMemory.ts`), which is a whole number, and during a stream every
  token retargets the move: `place` cancels what is running, reads where the panel is, and opens
  the new animation's keyframes there. So the new move starts on the rounded pixel while the eye
  has the fractional one, and the panel steps back by the remainder for a frame. Measured 2026-07-20
  at 60Hz with `element.animate` instrumented, at 640x720 with the reminder stack acked, over one
  streamed reply: every down-step of the exchange lands on a frame carrying such a call, opening on
  exactly the rounded value (363.188 to 363 against `363px`, 365.344 to 365 against `365px`,
  386.328 to 386 against `386px`). Worst step anywhere is 0.39px; there are none at all at 640x720
  with the stack up, the panel being pinned at its ceiling. This is bounded and it is not the
  user's complaint: across five traced configurations the panel is never below its pre-send height
  at any frame, so the floor holds and what is left is invisible. The fix is to read the used height
  with its sub-pixels (`parseFloat(getComputedStyle(element).height)`, which Chromium resolves to
  the border-box height under this app's `box-sizing: border-box`, measured here as 363.188px
  against an `offsetHeight` of 363 on a panel with a 1px border). It is deferred because
  `offsetHeight` is what the hook and its fakes are built on: every case in
  `overlay/usePanelMotion.test.ts` defines `offsetHeight` on the element, so the swap is a harness
  rewrite for a snap no eye can see, and it would want the same check `offsetHeight` was given
  against the summon's scale transform before `Collapse` follows it, or the two measure differently.
  - **Not to be confused with the second rounding, which was a defect and is fixed.** A re-read
    measured a whole pixel at 640x720 with the stack up, which is exactly where this entry says
    there is nothing, and the two are unrelated: that one was `maxHeight` rounded on the way out to
    `max-height` and taken raw as the cap on a roll's predicted height, so a panel at its ceiling
    was placed for a height 0.2px taller than it could have and its bottom edge rounded the other
    way
    ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 16). This entry remains what it says: a
    fractional used height against a rounded `offsetHeight`, while a stream retargets a move.
- **Opening a Thoughts trace on a panel at its ceiling pushes the reply below the fold.** The
  disclosure rolls open in place and nothing touches the history's `scrollTop`, which is the right
  default: the row stays exactly under the pointer that clicked it and the trace unfolds beneath,
  where native `<details>` and every other disclosure put it. Where the panel can still grow that is
  the whole story, and nothing scrolls at all. Where it cannot, the growth is absorbed by the
  scroll box instead, and everything below the trace slides down by the height of it. Measured
  2026-07-20 at 60Hz at 640x720 (the body's own window) with the reminder stack up, so the panel
  was already at its 547px ceiling: the disclosure's top edge held at 360px for every frame of the
  roll and `scrollTop` never moved, while the distance from the tail grew 0 to 76px, leaving two
  lines of the answer visible above the composer. With a trace long enough to hit its own `28vh`
  cap the growth is 206px and the answer goes entirely. The reader can scroll, and the state is
  exactly reversible by closing the trace, so this is a comfort item rather than a defect. The fix
  is not "follow the tail": that scrolls the trace's own top edge off the screen as it grows and
  leaves the reader reading its bottom half. It is to scroll the history by the same curve and over
  the same 300ms, by as much as the growth that falls below the fold and no more, so the trace ends
  fully visible with as much of the reply below it as still fits. That wants a scroll animation
  alongside `Collapse`'s height animation (`components/Collapse.tsx` owns the only clock either
  could share), and it wants a rule for what "as much as fits" means when the trace alone is taller
  than the visible history. Deferred because it is a second motion to keep in step with the roll,
  and the roll itself is the thing the maintainer asked for.

  That animation has a second job now. `.history` turned scroll anchoring off
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 15) because the engine's version of it
  lurched the log 76px on the way open, and closing a trace that sits above the fold was the one
  thing it had been getting right: it eased `scrollTop` down with the shrink so the visible content
  never moved. A deliberate scroll on the roll's clock covers both directions with one rule, where
  the engine had one good half and one bad one.
- **The console's tab strip is a tab list by role but not by keyboard, and the pane being left is
  hidden from assistive tech without being untabbable.** The strip carries `role="tablist"` with a
  `role="tab"` per face and `aria-selected` on the one showing, and focus travels with the view:
  the arriving pane's selected tab takes it (`components/ConsoleView.tsx`), and leaving the console
  hands it back to the composer, whose `active` prop is "the panel is open AND no console tab is
  up" (`components/ChatView.tsx`). That handoff is load-bearing rather than polish, because a
  browser refuses to hide the focused element's ancestor from assistive tech, so without it the
  `aria-hidden` on the pane being left is ignored and the tree holds two consoles for the length of
  a morph (Chromium says so in the console, and the AX tree over CDP showed both before the handoff
  landed and one after). Two pieces of the pattern are deferred. The strip has no roving `tabindex`
  and no arrow-key navigation, so both tabs are in the tab order and Left/Right do nothing, where
  the ARIA practice is one stop for the whole strip and arrows to move along it. And a pane on its
  way out is `aria-hidden` but still focusable, so a Tab pressed during the 380ms of a crossing can
  land in it; the sanctioned fix is `inert`, which React types only from 19 (this tree is on 18,
  and setting the attribute by hand around a subtree React owns is the kind of thing that reads as
  a bug later). Deferred because neither is reachable with a pointer, both are invisible outside
  that 380ms window, and the half that changes what is ANNOUNCED, which is the half a screen reader
  actually reports, is done.
- **A new chat minted while the console is up leaves the console up.** `Ctrl+N` and the header's
  pencil clear the switcher and any pending confirm but not `consoleTab` (`overlay/overlayState.ts`,
  case `newChat`), so the panel mints the session and empties the chat *behind* the console while
  Appearance or Shortcuts stays on screen. Measured 2026-07-20 at 900x900: open the console from the
  hint strip's sliders, blur, press Ctrl+N, and the live tabpanel still reads "Appearance" while the
  title behind it has gone back to "New chat". This is older than the console, since the two sheets
  it replaced were not cleared by `newChat` either, so the merge neither caused it nor claims
  otherwise. The fix is one line in that case arm; which line is the question, and it belongs to the
  user rather than to a defect list. A new chat is arguably a request to be in the chat, and the
  case arm already puts the panel in `mode: "panel"` for exactly that reason. Against that, the
  console is the one surface that is about the app rather than the conversation, and closing it out
  from under someone who reached for a new chat while reading the shortcut list is the same
  surprise pointing the other way. Nothing else is ambiguous: `dismiss` and Esc both close the
  console on purpose and say so in their comments, so this is about the third door alone.
  **The user answered on 2026-08-03 and it LANDED the same day
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)): Ctrl+N closes the console.** A
  keystroke aimed at the conversation puts you in the conversation, so the chat is cleared, the tab
  goes with the chat it was opened over, and the empty chat is what is on screen. The entry framed
  the question correctly and undersold the answer by exactly one arm, which is the usual lesson
  here: `openSession` had the identical hole, and its version is reachable by keyboard, because
  Ctrl+Up and Ctrl+Down are global keys in `Overlay.tsx` and cycle straight into it while the
  switcher row that normally starts a load is `display: none` behind the console. Those two keys and
  Ctrl+N are the whole reachable surface, the pointer doors into both arms (the pencil, a switcher
  row) being under the console. So "one line in one reducer arm" was two lines in two, and the rule
  that shipped is a conversation arriving on the
  panel brings the chat with it, rather than a special case for one keystroke. The two chat swaps
  that do NOT clear the tab were read at the same time and are unchanged with their reasons now
  written down: `deleteSession` keeps it for the same reason it already keeps the switcher open (a
  delete comes from a switcher row, so the user is managing chats rather than asking for one) and is
  unreachable from the console besides, and `adoptSession` is a cold-start restore that must take
  nothing off the panel and cannot meet an open console anyway, a summon having set `touched`. Both
  halves are pinned in `overlay/overlayState.test.ts`, the arriving pair walked through both tabs
  and both doors, the standing pair asserted as standing, and each arm's clear was proven to redden
  its case by being removed in place. Both were also watched in the browser at the entry's own
  900x900, before and after, and the readings are in the ADR addendum: with the clears removed the
  console is still the live view after each press, and with them in place the chat is.
- **A liquid window edge gives up the backdrop blur.** Measured in the design pitch that chose it
  and pinned in ADR-0036: Chromium composites `backdrop-filter` output without clipping it by a
  `path()` clip, so a sculpted panel showed a sharp frosted rectangle ghosting behind the liquid
  outline. The shipped trade paints `--panel-solid` (a near-opaque theme token) on the clipped
  slab instead, which costs nothing visible today: the v1 window's ground behind the panel is
  opaque, so there is nothing behind the glass to blur. It becomes real at the transparent-window
  pass, when the desktop shows through and a Still panel is frosted while a liquid one is merely
  translucent. Two fix shapes were seen working in that same pitch: a `mask-image` built from the
  same outline (masks DO clip backdrop-filter output, the corner-dissolve candidate proved it), or
  re-testing the clip path once WebView2's Chromium fixes the compositing. Whoever picks this up
  should start by re-measuring, since the engine moves. Placed here 2026-07-21.
- **The voice could be a fourth picked row.** The whisper landed as the one streaming effect
  (ADR-0037 decision 1), but it was chosen from a pitched family (the Voice: Murmur, Whisper,
  Patter, Intone, each a breath, words and settle lifecycle) and it lands behind one component
  seam (`WhisperBubble` plus its clock), so promoting it to a registry beside the theme, the
  iris and the dream is data plus a swatch row rather than a redesign: the Face's anatomy
  extends to a light, an iris, a dream, and a voice. The pitch history lives in the artifact's
  labeled versions. Trigger: the user wanting a second voice back, or any second streaming
  treatment being asked for. Placed here 2026-07-21.
- **A streamed bubble's wrap width is measured once.** The whisper lays its letter DOM at the
  final wrap width measured when the bubble mounts (ADR-0037 decision 4), so a window resized
  mid-stream keeps the old wrap until the next message. Invisible in the v1 body, whose 640x720
  window cannot resize; only the browser dev flow can see it. The fix is re-measuring on a
  resize and re-laying the letters, which moves only invisible ones if the front is held during
  the re-lay. Trigger: the transparent-window pass or any resizable overlay window.
  Placed here 2026-07-21.
- **The drain can grow the bubble after the turn's last render.** The front trails arrivals by
  its catch-up time, so the box can gain its last line inside the half second after `complete`,
  when nothing re-renders and the panel's measured moves are not looking (ADR-0037
  consequences). The history's min-height floor hides it today (short chats sit inside the
  floor, long ones scroll), and the tail pin rides the whisper's own `onGrow`. Trigger: the
  chat floor changing, or a between-render growth visibly outrunning the panel on some future
  layout. The fix is the panel hearing between-render growth the way it hears a roll
  (`cortex:morphstart`'s lesson). Placed here 2026-07-21. **Landed 2026-07-21, the same day,
  by exactly that fix**: the first live look found the panel's top edge snapping
  backwards on every token of a reply past the chat floor (the same stale-measurement root,
  seen from the other side), so the whisper bubble now carries `data-morphing` from its first
  spoken letter to its settle and dispatches the contract's start and end events. Placements
  defer for the length of the stream, the panel's auto height follows the box frame by frame
  (the drain included), and the end event is the re-measure this entry asked for (ADR-0037
  addendum has the before and after traces).
- **The switcher's rows have no exit, and the hook for one is already in the tree.** Opened
  2026-08-03 with the reminder stack's per-row exit ([ADR-0035
  addendum](../adr/ADR-0035-console-and-motion.md)). Deleting a chat drops its row from
  `state.sessions` the moment the write lands, so it goes in a frame and the rows under it snap up,
  which is the defect the reminder stack no longer has. `overlay/usePresence.ts` is generic and was
  built to be shared, so the missing part is the wiring rather than the mechanism. What makes it a
  second surface rather than a free line: the row needs the same restructure the reminder row got
  (the `<li>` outside the roll, the row's box inside it), and the switcher's own rules have to be
  re-checked against that wrapper, `.switcher-li:hover .switcher-rename-btn` and its two siblings
  reaching for descendants, `.switcher-li.pinned` styling the row itself, and a row that is
  mid-rename or mid-delete-confirm being a different subtree of the same slot. It also wants its own
  frame trace, since a delete refreshes the list behind the roll and resets the panel outright when
  the chat being deleted is the one on screen. Nothing blocks it.
- **Per-letter boxes give up kerning pairs.** A whispered message's letters are one box each
  inside an unbreakable word box (ADR-0037 decision 6), so kerning inside a word is lost while
  that message's DOM is on screen (it re-renders plain only when its chat is next loaded).
  Checked by eye at 13.5px in the system stack in both themes and invisible there. Trigger:
  the overlay adopting a licensed face (overlay-ux.md §2 keeps that door open), whose kerning
  is worth re-checking against a settled reply's plain rendering side by side.
  Placed here 2026-07-21.
