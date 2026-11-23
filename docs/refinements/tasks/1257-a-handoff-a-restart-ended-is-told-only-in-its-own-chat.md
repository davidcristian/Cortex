# A handoff a restart ended is told only in its own chat

**Status:** declined 2026-11-23
**Area:** inference-model-manager
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)

Boot recovery appends a record to the chat of a handoff that a restart of the brain ended
(`record_unanswered` in
[stranded_handoff.py](../../../brain/packages/core/src/cortex_core/stranded_handoff.py)), and
`unanswered_handoff_note` reads that chat's history, so only the next reply in that chat says the
request got no answer. A person who opens a new chat after the restart gets no note from the brain.

Drawn live on 2026-11-18 ([readings](../../readings/handoff-restart-record.md)): a new chat asked
whether the handoff finished, and the cortex said it did not, from two recalled memory rows. That
reply is the model's own choice. The brain checks nothing on that turn.

Two more things are not drawn. The overlay shows a restored chat from the store, so the record is
shown there as a reply of its own and its text is shown again under the next reply; nobody has
looked at that in the overlay. A chat that could not be read at boot gets `UNSURE_HANDOFF_NOTE` in
English whatever the language of the request.

What would close it: a decision on where a note for another chat is kept. The `SessionStore` port
has no place for a record that belongs to no chat, and the `HandoffStore` port reads a record only
by its id or while it is active, so the first step is a port method that lists the handoffs a
restart ended and whether their note was shown, with a contract test and a fake.

## History

- 2026-11-18: filed when boot recovery began to store the record in the handoff's own chat.
- 2026-11-23: declined. The record is already told outside its chat: its `at` is the boot's time
  and the Redis store scores the chat by it (`append` in `cortex_session/store.py`), so the
  switcher lists that chat first, titled with the request and previewed with the record's first
  96 characters (`summarize_ends` in `sessions.py`). A note in a new chat would ask the person to
  hand over a request that chat does not hold, so no port for one is added. The English
  `UNSURE_HANDOFF_NOTE` stays: its chat could not be read, so no request text gives a language.
  How the overlay shows that chat is not yet seen: R-1315.
