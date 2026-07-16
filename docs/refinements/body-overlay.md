# Body & overlay

These deferrals originate in [ADR-0011](../adr/ADR-0011-body-v1.md), the Slice 8 body v1
decision covering the host-native shell and the overlay UI. Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries
are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** multi-turn-within-one-stream + proto `Cancel`, deferred overlay polish, a real connection indicator

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
- **A real connection indicator.** The v1 header dot was decoration (always "ready") and the
  2026-07-03 design pass removed it (user direction, [overlay-ux.md §3](../design/overlay-ux.md));
  the meaningful green/amber/red indicator needs a health/status signal over the bridge. The
  seam's `Health` RPC exists, the `BrainBridge` doesn't carry it yet. Joins whichever slice first
  streams brain status to the overlay.
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
