# A claim or unmatched note on a reply that hands off says nothing was deleted in the turn

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

A cortex reply whose own calls hand the turn to the deep model ends with `HANDED_FORGET_NOTE`
(`forget_uncalled.py`), which speaks of the time before the handoff, since the deep model's reply
belongs to the same turn and can delete. Two other notes `limit_notes` (`closing_notes.py`) puts
on the same reply still speak of the whole turn, so a delete by the deep model makes them false:

- `UNFORGOTTEN_CLAIM_NOTE` (`forget_claim.py`), on `Forget my gym code.` answered with
  `I have forgotten your gym code and handed the rest to the deep model.`, says
  `Nothing was forgotten in this turn` and asks the person to ask again in a message of its own.
  Its four translations say the same.
- `UNMATCHED_FORGET_NOTE` (`forget_unfound_claim.py`), after a forget call that matched nothing
  and a handoff, says `Nothing was deleted from memory in this turn.`

## What to do

1. Write both cases as tests through `limit_notes` with an approved `escalate_to_brain` run, and
   a declined one that keeps today's text.
2. Give each note a form said of the time before the handoff, as `uncalled_note` does, with the
   same four translations written to the slot's `translations.md`. The claim note's form drops the
   request to ask again, since the deep model has the message.
3. Prove each test can fail by reading the earlier runs as this reply's runs.

## History

- 2026-11-12: filed from the audit of the note before a handoff, which is true on every turn it
  reaches; these two notes are not.
