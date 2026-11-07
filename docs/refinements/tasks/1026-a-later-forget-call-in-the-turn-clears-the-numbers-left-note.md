# A later forget call in the turn clears the numbers left note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`run_round` in `dispatch_round.py` sets `taint.forget_numbers_left` from every `forget_memories`
result, so the last call of the turn decides whether `NUMBERS_LEFT_NOTE` closes the reply. A later
call that deletes an unrelated fact, matches nothing, or has its card denied writes `False` over a
count an earlier call reported, while the rows holding the earlier number are still stored. The
draws show the model calling the forget again with the value after the count, so a denied second
card is the common path.

Reproduction, through `TurnEngine` with the fakes (`SCRATCH/slot20/probe_left.py`, helpers from
`test_numbers_left_note.py`): rows `_DOOR`, `_ONLY_VALUE` (holds 1987) and `_FIAT`, every reply
saying the door code was forgotten, `m1` still stored after each turn:

| Calls in order | Card answers | Note |
| --- | --- | --- |
| `door code`, then `blue Fiat` | approve, approve | missing |
| `door code` and `blue Fiat` in one round | approve, approve | missing |
| `blue Fiat`, then `door code` | approve, approve | shown |
| `door code`, then `1987` | approve, deny | missing |
| `door code`, then `dentist` (matches nothing) | approve | missing |

## What to do

1. Write the five rows above as engine tests first, with the existing test that a later forget of
   the number itself clears the note.
2. Count over every row the turn deleted rather than the call's own rows: `_deleted_turns` already
   keeps the turn's deleted texts, so `_holding` can read them, and a result the tool did not write
   (a denied or refused card) must leave the ledger as it was.

## History

- 2026-11-07: filed by the third audit of the night's changes.
