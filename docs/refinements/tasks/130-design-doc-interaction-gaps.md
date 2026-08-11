# Design-doc interaction gaps

**Status:** landed 2026-07-12
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

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

## Trail

- 2026-07-07: The streaming stop control landed, the send button becoming a real stop mid-turn, and
  the header and composer glyphs were unified onto one outline icon set the same day.
- 2026-07-12: All nine items surfaced by the 2026-07-03 browser pass landed behind the unchanged
  `BrainBridge` port and reducer, CI-gated at 100% and browser-validated in both themes.
