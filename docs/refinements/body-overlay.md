# Body & overlay

These deferrals originate in [ADR-0011](../adr/ADR-0011-body-v1.md), the Slice 8 body v1
decision covering the host-native shell and the overlay UI, and in
[ADR-0031](../adr/ADR-0031-bubble-mark.md), the bubble mark that replaced its living rings.
Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries
are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** multi-turn-within-one-stream + proto `Cancel`, streamed
brain status (its producer landed 2026-07-18; only the push RPC remains), exit animations for
sections leaving the panel

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
- **Sections do not animate out.** The panel's size change eases in both directions, so closing
  the switcher or dismissing the last reminder collapses the panel smoothly, but the section
  itself vanishes on the first frame instead of sliding out: React unmounts a removed child
  immediately, and the growth animation only sees the height that is left behind. Animating an
  exit means keeping the element mounted through it (a leaving flag in the reducer, or a
  transition library), which is a real change to how the panel renders its sections rather than a
  CSS addition. Deferred because the asymmetry is barely visible at the durations in use: the
  collapse the eye follows is the panel's, and it is animated.
