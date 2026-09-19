# Design-doc interaction gaps

**Status:** done 2026-07-12
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

The nine interaction gaps a browser pass found on 2026-07-03 all shipped behind the unchanged
`BrainBridge` port and reducer, covered at 100% in CI and checked in a browser in both themes:
history auto-scroll while streaming (held at the bottom, and scrolling up keeps the reader's
place), composer focus on summon, click-away dismiss (Esc leaves the orb mid-stream and hides it
when idle), the tool and status chips the reducer already tracked (slim accent-dotted pills above
the streaming bubble, which gave the ADR-0020 thinking status a visible surface), the empty-state
mark with tappable example prompts, the pre-first-token thinking shimmer, the `?` shortcut sheet
(`sheetOpen` in the reducer, and Esc closes it before dismissing), composer auto-grow, and preview
hover pausing the fade timer (leaving restarts the countdown, with the drain bar remounting in
step so bar and timer agree).

The streaming stop control shipped 2026-07-07: the send button becomes a real stop mid-turn
through a `stop` reducer action that drops the stream via the bridge `Cancellation` and ends the
reply in place. The header and composer glyphs were unified onto one outline icon set
(`components/icons.tsx`) the same day.

## History

- 2026-07-07: The streaming stop control shipped, and the glyphs were unified onto one icon set.
- 2026-07-12: All nine items shipped behind the unchanged `BrainBridge` port and reducer.
