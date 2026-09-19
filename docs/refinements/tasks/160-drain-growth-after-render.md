# Bubble growth after the turn's last render

**Status:** done 2026-07-21
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)

The whisper's letter front trails the arriving tokens by its catch-up time, so the bubble can gain
its last line in the half second after `complete`, when nothing re-renders and no measured move of
the panel is running (ADR-0037 consequences). The fix is for the panel to hear growth that happens
between renders, the same way it hears a section opening.

Fixed the same day it was filed. The first live look found the panel's top edge jumping backwards
on every token of a reply past the chat floor, which is the same stale-measurement cause seen from
the other side. The whisper bubble now sets `data-morphing` from its first spoken letter to its
settle and sends the start and end events, so panel placements wait for the length of the stream,
the panel's height follows the bubble frame by frame, and the end event re-measures. Traces before
and after are in [panel motion](../../readings/panel-motion.md#the-whisper-bubble).

## History

- 2026-07-21: Filed with the whisper streaming redesign and closed the same day, when the first live
  look showed the same stale-measurement cause as the per-token jitter (ADR-0037 decision 10).
