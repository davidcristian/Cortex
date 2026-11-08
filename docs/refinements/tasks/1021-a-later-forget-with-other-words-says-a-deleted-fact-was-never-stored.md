# A later forget with other words says a deleted fact was never stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-08

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

1. Append a note after the reply, as `numbers_left_claim.py` does for its note, when a forget of
   the turn deleted rows (`deleted_memory(made, taint.forget_unmatched)` in `forget_claim.py`), a
   later call got the no-match result (`taint.forget_unmatched` above zero) and a typed reader says
   the reply calls something not stored, not found or not saved. Both inputs already reach
   `limit_notes` in `closing_notes.py`, so no ledger field is needed.
2. The note must be true for both later texts: one about the deleted fact (`locker combination`
   after `5819`) and one about a fact never stored (the passport after the phone). Write the
   reader's near misses as tests first: a reply saying only that the code was removed, `nothing
   else` with no claim about storage, a question back to the person.
3. Ship by the rule in the [readings](../../readings/forget-later-call-other-words.md#the-flows-and-the-rule-2026-11-08):
   the bk and lk flows drawn until four draws show the form. The form occurred in 2 of 10 draws,
   so that is about 20 draws, more than one 10 minute cap.

## History

- 2026-11-07: filed by the second audit of the night; reproduced at unit level, no turn sent.
- 2026-11-07: the recorded forget draws hold no second call in a turn. Both factual results were
  drawn on a flow whose second fact was never stored: two of three replies said it was deleted,
  against none of two on the start hash, where one reply said the deleted phone was not found
  ([readings](../../readings/forget-value-repeats.md#the-draws-of-both-results-2026-11-07)). Neither ships.
- 2026-11-08: premise checked on `d7a1afe0a`: in 10 draws of two flows that delete a code by its
  value and then name it in other words, the form occurred twice and one reply said the deleted
  locker combination was never saved
  ([readings](../../readings/forget-later-call-other-words.md#the-draws-2026-11-08)). In 6 draws the
  later text was the stored row's own words, which already gets the result naming the delete. The
  step reading a text as the same fact by its words is dropped: `combination` is no word of the
  row, so it would not reach the failing draw.
- 2026-11-08: a candidate for step 1 is `SCRATCH/slot7/unfound-note.patch` (`forget_unfound_claim.py`,
  wired in `limit_notes`, its tests at 100%), not in the tree since no form draw has run on it.
  Replayed over the 135 distinct recorded replies of turns that ran `forget_memories`, its reader
  reads 22, among them 4 saying a new phone number was not saved because the message asked to
  forget, which `FORGET_NOT_KEPT_NOTE` requires: add them as near misses, or check that their
  turns had no call that matched nothing, before drawing it.
