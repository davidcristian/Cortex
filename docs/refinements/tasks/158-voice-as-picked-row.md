# The voice as a fourth picked row

**Status:** open, feature breadth
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Trigger:** The user wanting a second voice back, or any second streaming treatment being asked for.

The whisper landed as the one streaming effect
(ADR-0037 decision 1), but it was chosen from a pitched family (the Voice: Murmur, Whisper,
Patter, Intone, each a breath, words and settle lifecycle) and it lands behind one component
seam (`WhisperBubble` plus its clock), so promoting it to a registry beside the theme, the
iris and the dream is data plus a swatch row rather than a redesign: the Face's anatomy
extends to a light, an iris, a dream, and a voice. The pitch history lives in the artifact's
labeled versions. Trigger: the user wanting a second voice back, or any second streaming
treatment being asked for. Placed here 2026-07-21.

## Trail

- 2026-07-21: Placed in the feature-breadth bucket when the whisper streaming redesign landed.
- 2026-08-09: A costing pass against the tree found the entry is not the data plus a swatch row it
  calls itself, and it fails that description in two independent places. The lifecycle a pick would
  parameterize lives in one file at the cap, `body/app/src/whisper/useWhisperClock.ts` at 298 lines
  against the 300-line limit, with all three phases driven from one rAF loop, so the first per-voice
  edit overruns it and opens a responsibility split plus a re-cover of both halves; and there is no
  registry to add a literal to, the theme, the mark and the edge each owning one while the whisper
  directory holds only the clock and `front.ts`. The row costs too: every existing Appearance
  section is a live preview of the real thing, and a voice tile's subject is motion over time rather
  than a still surface, so it needs an animated preview component and its tests beside neighbours of
  87 and 203 lines. What survives is the persistence half, preferences riding generic string keys so
  a fourth key costs no proto change and no brain change. Naming the row is deliberately left to the
  maintainer.
