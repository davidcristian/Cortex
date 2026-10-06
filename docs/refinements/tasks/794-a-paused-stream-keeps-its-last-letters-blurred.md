# A paused stream keeps its last letters blurred

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md) decision 2
**Verified:** 2026-10-06

The whispered reply condenses letters on a front that trails the arrivals, and a letter inside the
nine-letter band (`BAND_LETTERS` in `body/app/src/whisper/front.ts`) holds part opacity and blur.
`advance` stops the front at the last letter received, and only the settle runs it a band further.
So while a turn is still streaming but no text arrives, the last nine letters stay unreadable.

In a handoff that pause is the whole swap: in the overlay run on 2026-10-06 the end of the cortex's
hand-over sentence ("eq" and a blur, where the text was "equals $n^2$.") stayed blurred from the
loading status until the deep model's first text, minutes later
([readings](../../readings/model-swap.md#the-overlays-view-of-a-handoff)). A tool call that takes
long, or a confirm card left open, can pause the stream the same way.

**Do.** Finish the band when the stream pauses: for instance, run the front a band past the last
letter when a status that is not a reasoning delta arrives, as the settle does, and resume from
there on the next text. The front never moves backward, so letters already clear stay clear. Keep
the paced-not-timed rule: what ends the pause is an event, not a timer.

## History

- 2026-10-06: filed by the overlay's view of a handoff on the Linux shell
  ([H-018](../../host/tasks/018-tier-scale-swap.md)).
