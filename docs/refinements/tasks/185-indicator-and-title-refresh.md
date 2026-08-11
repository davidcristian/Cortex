# Connection indicator and session-title refresh push

**Status:** landed 2026-07-16
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

A real connection indicator and a session-title refresh push ride whichever slice first
streams brain status to the overlay (the ADR-0011 `Health`/status deferral, see
[body-overlay.md](../index.md#body-overlay)), not this one.
**Both closed 2026-07-16 ([ADR-0021 refresh addendum](../../adr/ADR-0021-session-read-seam.md)),
and the premise they shared was wrong.** Neither needed a status stream. The indicator landed
by deriving its signal ([body-overlay.md](../index.md#body-overlay)), and this half landed with it: the
chat list now also refreshes on the **rising edge of visibility**, sharing the one summon latch
(`useSummonEffect`) with the reminder pull and the connection probe. The two triggers it had,
mount and turn completion, can both be arbitrarily old by the time anyone looks, since a
tray-resident body mounts once and the last turn may be days back; and a list that failed to
load while the brain was down had no way back until a turn completed, which is now the same
gesture that turns the dot green. **The push itself is not deferred again, because nothing can
produce it:** session history has exactly one writer, `ConversationEngine` inside a turn
(`engine.py`), and the schedule ticker dispatches tasks to the task store, never to a session.
A title therefore cannot change while the overlay watches except through a turn the overlay
itself ran, which already refreshes on completion. What would reopen it: brain-generated
summary titles (above), which could rewrite a title *after* the completing turn refreshed the
list, so that race belongs to that entry.

## Trail

- 2026-07-16: Both halves closed, taking the area count from 5 to 4, because the two entries
  were one deferral written down twice and the premise they shared, waiting for a slice that
  streams brain status, was wrong for both. The index records the indicator landing under
  [body-overlay.md](../index.md#body-overlay), where it opened a push half of its own that is blocked
  on a producer.
