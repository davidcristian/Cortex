# Body & overlay

These deferrals originate in [ADR-0011](../adr/ADR-0011-body-v1.md), the Slice 8 body v1
decision covering the host-native shell and the overlay UI. Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries
are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** multi-turn-within-one-stream + proto `Cancel`, deferred overlay polish, streamed brain status

**Body / overlay in Slice 8 ([ADR-0011](../adr/ADR-0011-body-v1.md)):**
- **Multi-turn-within-one-stream + an explicit proto `Cancel` event.** One turn per `Converse`
  call; drop-to-cancel covers v1 (ADR-0011 decision 1 / risks). The interleaving half was
  taken by **Slice 8.8** (ADR-0022): the body's client stream now stays open past the first
  `UserTurn` to answer `ConfirmRequest`s mid-turn. Still deferred: multiple turns per call
  body-side and the client actually sending `Cancel` (drop-to-cancel remains the mechanism).
  When multiple turns per call land, Slice 8.8's single-slot `ConfirmRoute` (Tauri) and the
  `SeamConfirmer`'s "at most one confirm outstanding per stream" assumption need per-turn keying
  (a map, not one slot); the route is already generation-tagged, so the change is contained there.
- **Deferred overlay polish.** A proper transparent window + click-through margins (done
  together), the OS-window morph to a real screen corner, hide-on-blur, and a tighter CSP are
  detailed in [overlay-ux.md §4](../design/overlay-ux.md) and
  [body-overlay.md](../runbooks/body-overlay.md), recorded at ADR-0011 (2026-07-03 addendum). The
  design doc's smaller "later" marks (custom theme token sets, a licensed `@font-face`, a
  `Ctrl+K` command palette) ride along in §2-3 of the same doc.
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
