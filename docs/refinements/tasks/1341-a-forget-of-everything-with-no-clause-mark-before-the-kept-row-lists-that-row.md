# A forget of everything with no clause mark before the kept row lists that row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

A forget of everything that keeps a row with no clause mark before it lists that row:
`Forget everything the card stays.`, `Wipe everything the card stays.` and `Vergiss alles bis
auf die Karte.` delete the card for the call texts `card` and `4242`. Over the family of
`f3gen/every.py`, 222 of the 1,188 rows asked to keep in these forms are listed: 96 after a head
with no forget verb, 66 after a read head such as `Forget everything` and 60 after a word for all
left unread, such as `alles`
([readings](../../readings/forget-everything-unread-forms.md#the-later-clauses-read-2026-11-25)).
The same forms with a clause mark are read by `_kept_later` in `forget_permit.py`.

## What to do

1. The only rule known reads the forget verb's own clause too, as the runs after a value are. It
   keeps every row of these forms, and also 1,411 rows asked to delete over the generator and 92
   of the near misses, since with no new word read, `the card stays` differs from `the card
   holds` only by a word no reader reads
   ([readings](../../readings/forget-everything-unread-forms.md#two-rules-replayed-2026-11-24)).
   It is not built.
2. A word for stays, or a set of words for all read only to keep, is a new word list, which is
   not added. Find a rule that keeps these rows at a cost counted over the generator, or decline
   the task with that count.
3. Replay with `replay.sh`, `cmp.py` and `ecount2.py` in `~/.cache/cortex-run/2026-11-25/f2/`.

## History

- 2026-11-25: filed from [task 1230](1230-a-forget-of-everything-in-a-form-the-card-does-not-take-as-one-lists-a-row-its-message-keeps.md),
  whose forms with a clause mark before the kept row are now read.
