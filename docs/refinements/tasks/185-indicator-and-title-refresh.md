# Connection indicator and session-title refresh push

**Status:** done 2026-07-16
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

Both were expected to wait for a slice that streams brain status to the overlay, and that premise
was wrong for both. The indicator shipped by deriving its signal, and the title refresh shipped with
it: the chat list now also refreshes when the overlay becomes visible, sharing the one summon latch
(`useSummonEffect`) with the reminder pull and the connection probe. Its two existing triggers,
mount and turn completion, can both be arbitrarily old by the time anyone looks, since a
tray-resident body mounts once and the last turn may be days back, and a list that failed to load
while the brain was down had no way back until a turn completed.

The push itself is not deferred again, because nothing can produce it: session history has exactly
one writer, `ConversationEngine` inside a turn (`engine.py`), and the schedule ticker dispatches
tasks to the task store, never to a session. A title cannot change while the overlay watches except
through a turn the overlay itself ran, which already refreshes on completion. Brain-generated
summary titles would reopen it, since they could rewrite a title after the completing turn refreshed
the list, so that race belongs to that entry.

## History

- 2026-07-16: Both halves closed, since the two entries were one deferral written down twice. The
  indicator's own push half opened under [body-overlay.md](../index.md#body-overlay), blocked on a
  producer.
