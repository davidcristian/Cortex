# The voice as a fourth pickable row

**Status:** open, optional feature
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Trigger:** The user wanting a second voice back, or any second streaming treatment being asked for.
**Verified:** 2026-09-19

The whisper shipped as the only streaming effect (ADR-0037 decision 1), but it was chosen from a
pitched family of four, each with a breath, words and settle lifecycle. Promoting it to a pickable
registry beside the theme, the mark and the window edge would extend the Face's anatomy with a
voice.

It is not as cheap as it sounds. There is no whisper registry to add an entry to, where the theme,
the mark and the edge each have one. The lifecycle a pick would parameterize runs as one
`requestAnimationFrame` loop in `body/app/src/whisper/useWhisperClock.ts`, so a per-voice change
touches that loop. And every Appearance section is a live preview of the real thing, so a voice tile
needs an animated preview component and its tests. What is already in place is persistence:
`SetPreference` takes a free `key` and `value` and the brain stores whatever it is given. Naming the
row is left to the maintainer.

## History

- 2026-07-21: Filed when the whisper streaming redesign was committed.
- 2026-08-09: A costing pass found the entry is not the data plus a swatch row it calls itself, for
  the two reasons above.
- 2026-09-13: Checked again. `useWhisperClock.ts` is 288 lines rather than the 298 recorded before,
  because `metrics.ts` took the bubble's box arithmetic out of it, so a per-voice change starts with
  12 lines of headroom against the 300-line limit instead of 2. The shape is unchanged.
- 2026-09-19: Checked again; every count from 2026-09-13 still holds and nothing under
  `body/app/src/whisper/` has changed. The tile's neighbours are still `EdgeMini.tsx` at 87 lines
  and `BubbleMark.tsx` at 203. One detail to note: `overlay/usePreferences.ts` records a fixed
  triple of theme, mark and window, so a fourth key widens that type.
