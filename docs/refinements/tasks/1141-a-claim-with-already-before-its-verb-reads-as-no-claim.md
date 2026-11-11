# A claim with already before its verb reads as no claim

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Verified:** 2026-11-11

`claims_scheduled` (`schedule_claim.py`) allows `now`, `just`, `also` or `successfully` between the
auxiliary and the verb (`_ADVERB`), but not `already`. Called in the brain venv on 2026-11-11:
`I have moved the reminder for you.` and `I have scheduled the reminder.` are claims, while `I have
already moved the reminder for you.`, `I have already scheduled the reminder.` and `The reminder is
already set for 9:30.` are not. A turn with no scheduling call whose reply says it already
scheduled something gets no note, the reader's unsafe side.

Seen on the stack in chat `n19s8-a` on 2026-11-11: after a move, `And you already moved it, so I
don't need to do anything else?` called no tool and answered `I've already moved the reminder for
you, and it's all set for 9:30 every day.` with no note
([readings](../../readings/schedule-change-request.md#the-claim-note-pointing-to-a-list-2026-11-11)).
That reply was true, and the note it would now get asks only for a list.

## What to do

1. Write near misses first: `already` in a question, a negation (`I haven't already`) and a
   stored item described (`the reminder you already have`).
2. Add `already` to `_ADVERB`, and read the same word in the four other languages (`déjà`,
   `bereits` or `schon`, `ya`, `deja`) in `schedule_claim_other.py`.
3. Replay `docs/readings/` and the proxy logs through the old and new reader with counts.

## History

- 2026-11-11: filed from the status draws of the claim note pointing to a list.
