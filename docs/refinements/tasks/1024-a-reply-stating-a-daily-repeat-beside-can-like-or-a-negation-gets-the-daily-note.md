# A reply stating a daily repeat beside can, like or a negation gets the daily note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-07

`names_repeat` in `schedule_daily.py` reads a repeat only in a sentence with no `_CHOICE` word and
a clause with no `_NEGATION` word. `_CHOICE` holds `can`, `like` and `want`, which are common in a
plain statement of the repeat, and a purpose clause with "don't" or "n'" negates the clause that
names the repeat. Each reply below states that the reminder repeats, and gets `DAILY_STORED_NOTE`
appended, which repeats what the reply said. Each was read as naming a repeat before the change:

| Reply | Word that stops the read |
| --- | --- |
| "I'll remind you every day at 8 so you can take your pills." | `can` |
| "Done: a daily reminder at 8, like you asked." | `like` (the comma does not help: `_CHOICE` reads the sentence) |
| "I'll remind you every day at 8 so you don't forget your pills." | `n't` in the same clause |
| "Je te le rappellerai tous les jours à 8h pour que tu n'oublies pas." | `n'` in the same clause |

Reproduction, unit level: `SCRATCH/slot16/probe.py` prints `old=True head=False` for each. A
needless note is the safe direction here; the change kept a question or offer from hiding the note.

## What to do

1. Replay every recorded reply through both readers (`SCRATCH/slot15/replay.py` did this) and count
   how many state a repeat in one of these forms.
2. Read `_CHOICE` and `_NEGATION` only in the clause before the repeat word, or only when they
   govern it (`can` after `you` in a question, `if` opening the clause); write the four rows and
   the offers the change keeps out as tests first.

## History

- 2026-11-07: filed by the second audit of the night; reproduced at unit level, no turn sent.
