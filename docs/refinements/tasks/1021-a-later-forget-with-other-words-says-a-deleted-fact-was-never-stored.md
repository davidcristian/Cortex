# A later forget with other words says a deleted fact was never stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

When a `forget_memories` call matches nothing after an earlier call in the same turn deleted rows,
`_about` in `memory_forget_chosen.py` returns `_ALREADY_DELETED` only when the new text is a
substring of a deleted row or of an earlier call's text, the reverse, or shares a whole value with
one. A model that first passes the value and then checks with its own words for the same fact gets
`_NONE_FOUND`, which tells it to say that nothing about it was stored, though the fact was stored
and deleted a moment earlier in the same turn. Before the same fact test, any earlier delete in the
turn gave `_ALREADY_DELETED`.

Reproduction, unit level (`SCRATCH/slot16/probe.py`): one row "Remember that my bike lock code is
4512", a call `4512` approved and deleted, then a second call in the same turn:

| Second call text | Before the same fact test | Now |
| --- | --- | --- |
| `bike code` | `_ALREADY_DELETED` | `_NONE_FOUND` |
| `lock combination` | `_ALREADY_DELETED` | `_NONE_FOUND` |
| `my bike lock`, `bike lock code` | `_ALREADY_DELETED` | `_ALREADY_DELETED` |

`test_a_later_call_naming_a_deleted_row_names_the_earlier_delete` asserts `_NONE_FOUND` for
`old phone` after the phone row was deleted, so the tests already require this result for a
paraphrase.

## What to do

1. Count the second texts the recorded forget flows passed after a delete in the same turn
   (`docs/readings/` forget flow records) and how many are substrings of the deleted row.
2. Read a text as the same fact when every word of four or more letters in it is a word of a
   deleted row, and write the near misses first: a text about another stored fact must still get
   `_NONE_FOUND`.

## History

- 2026-11-07: filed by the second audit of the night; reproduced at unit level, no turn sent.
