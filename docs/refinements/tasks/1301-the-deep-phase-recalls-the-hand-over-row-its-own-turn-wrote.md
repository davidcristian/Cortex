# The deep phase recalls the hand-over row its own turn wrote

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-11-23

The cortex's part of a handed-over turn ends with `record_exchange`
(`brain/packages/core/src/cortex_core/turn_output.py`), which stores `User: <request> / Tools run:
escalate_to_brain (handoff started, answer not recorded here) / Assistant: <hand-over sentence>`
before the swap. The deep phase then recalls for the same request (`_recalled_context` in
`turn_context.py`, with the phase's recaller from `engines.py`), and nothing leaves out a row of
the current turn. `MemoryRecord` has a `session_id` and no turn id, so the store cannot tell that
row from an earlier turn's.

On 2026-11-23 the row was in the deep phase's recall in both handoffs drawn
([readings](../../readings/handoff-leading-system-messages.md)). Its text holds the request
itself, so its similarity was the highest of the pool, 0.935 and 0.917, and the deep model's
judge kept it both times, in last place. ADR-0030 step 4 leaves the cortex's reply to this turn
out of the deep context, because a context ending in the cortex's wrap-up made the deep model
restate the handoff. The recalled row puts that reply back, under the header for memories from
earlier conversations, with the note that the answer was not recorded. Both deep replies were
correct, so no draw has shown harm; the row takes one of the `DEFAULT_RECALL_K` slots and its
prompt tokens whenever the judge keeps it.

## What to do

Leave the row out of the deep phase's recall and nowhere else: a later turn and another chat
still find it. Two places can hold the rule, and the choice needs a reading of each one's cost:

- The handoff record keeps the id of the row `MemoryRecaller.record` stored for the cortex's part,
  and the deep phase drops that id from its hits. No store change; the record gains a field that
  `cortex_session/handoff_codec.py` must round-trip, written after the record already exists.
- The memory row gains the turn id, and recall takes a turn id to leave out. A schema change in
  `docker/postgres/init.sql` and every `MemoryStore` adapter.

Write the near-miss tests first: a deep phase whose pool holds its own turn's row and an earlier
turn's row with the same request text returns the earlier one only. Then draw the chat of the
readings once and count the deep recall's hits in its `memory.recall` line.

## History

- 2026-11-23: filed from the handoffs of
  [R-1269](1269-no-handoff-on-qwen38-27b-has-sent-three-leading-system-messages.md), where the
  deep phase recalled this row in both runs.
