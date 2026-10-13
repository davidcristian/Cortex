# Nothing lets the person out of a recall-tainted block

**Status:** open, needs a port change first
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-10-13

With `CORTEX_MEMORY_ON_TAINTED=record` and the default `CORTEX_MEMORY_SCOPE=global`, a tainted row
is recalled into any chat whose request it matches, and every tool needing confirmation is blocked
on that turn ([ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md) decision 8). Each blocked
exchange is itself stored tainted, so the person's own email stays blocked while such a row exists.
Since [R-845](845-a-recall-tainted-turn-blocks-the-person-s-own-send.md) the refusal,
`RECALL_DENIED_MSG`, no longer names a way out that recall closes, but it names none, because
nothing in the product removes the row or skips recall. Deleting a chat forgets its memories only
under `session` scope (`SessionMemoryCascade` in `memory_cascade.py` returns 0 for `global`), and
under `session` a new chat does not recall another chat's rows anyway.

## What to do

Decide the way out and build it. Candidates, each a hypothesis:

- A per-turn choice to answer without recall: a field on `UserTurn` in
  [body.proto](../../../proto/body.proto) and an overlay control. The turn then reads nothing
  untrusted and its send is confirmed as usual.
- A way for the person to forget a tainted row: removal by id or by the tainted bit on the
  `MemoryStore` port, which today removes only by scope (`delete_scope`). It meets
  [R-074](074-per-provenance-eviction.md), which waits on removal by source.
- Not storing an exchange whose only outward call was blocked, which stops the rows from
  multiplying but leaves the first one.

The rows in [recall-tainted-send.md](../../readings/recall-tainted-send.md) are the place to start:
row S with the chosen way taken should reach the card and send to the Bridge account's own address.

## History

- 2026-10-13: filed while closing R-845, whose fix made the refusal accurate and left the person
  with no way to send.
