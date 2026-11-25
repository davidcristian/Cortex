# A forget of everything in a form the card does not take as one lists a row its message keeps

**Status:** done 2026-11-25
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

A forget of everything that names a stored row in a role no reader reads keeps every row
(`message_rows` in `forget_permit.py`). It is read only from a word for all of the table of forms
that follows a forget verb, with a clause mark or an unread word before the row. Over the rows
`Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my phone is 0721 555 4242.`, these still delete the card with the call text `card`
or `4242` ([readings](../../readings/forget-everything-unread-role.md)):

| Message | Why it is not read |
| --- | --- |
| `Forget everything my card stays.` | no clause mark: `my card` opens as a limit does |
| `Wipe everything, my card stays.` | `wipe` and `clear` are no forget verb of `FORGET` |
| `Everything must go, my card stays.` | no forget verb before the word for all |
| `Vergiss alles bis auf die Karte.` | `alles` is left unread, since Dutch has it too |
| `Olvida todo, la tarjeta se queda.` | `todo` is left unread, since Portuguese has it too |
| `Uită tot, cardul rămâne.` | `tot` also means still and is a Dutch word |
| `Uită tot în afară de card.` | the same word; the phrase for apart from is read as an unread role |

## What to do

1. Write near misses first: `Forget everything my card holds.`, `Forget all my card numbers.`,
   `Olvida todo sobre la tarjeta.`, `Vergeet 4242 tot morgen.` and `Forget my todo list.` must
   list what they list today.
2. For the forms with a clause mark before the kept row, read the clauses after the first forget
   verb's clause, or after the first clause of a message with none, as the runs after a value
   are, and keep a row named in a run whose role no reader reads. Name rows over the store, as
   `_beyond_every` does, not only from the rows the call lists: read from those alone, the rule
   keeps a row a later clause adds, 24 rows asked to delete in 7 test literals
   ([readings](../../readings/forget-everything-unread-forms.md#two-rules-replayed-2026-11-24)).
   Replay the family and the generator and count the rows asked to delete that are newly kept.
3. The forms with no clause mark stay open: read with no new word, the rule of step 2 widened to
   the forget verb's own clause keeps their rows, and also 92 rows asked to delete of the near
   misses and 1,411 of the generator. A word for stays or a set of words for all read only to
   keep is a new word list, which is not added.
4. Replay with `f3gen/every.py`, `replay4.sh`, `ebreak.py`, `gtable.py` and `delta.py` in
   `~/.cache/cortex-run/2026-11-24/f4/`.

## History

- 2026-11-15: filed from the replay of the forget of everything read by role
  ([readings](../../readings/forget-everything-unread-role.md)).
- 2026-11-15: checked against the rule of the unread role. No form above is covered without
  reading a new word: the form with no clause mark needs a word for stays or the limits of step
  3 kept, and the others need the set of step 2, read only to keep. `Uită tot în afară de card.`
  drew no forget call on the stack brain
  ([readings](../../readings/forget-everything-unread-role.md#drawn-after-the-card-changes-2026-11-15)).
- 2026-11-21: checked each message against the tree through `ForgetChosenTool`. All seven still
  delete the card with the call text `card` and with `4242`, and keep the locker code and the
  phone for `4242`. The four in other languages do the same over rows stored in their own
  language, for the word of the card row and for `4242`. No rule was built. With no new word
  read, `my card stays` differs from `my card holds` only by a word no reader reads, so a rule
  that keeps a named row before such a word also keeps the card of `Forget everything my card
  holds.`, a near miss of step 1, and its cost over the generator was not counted. Left open.
- 2026-11-23: checked again through `ForgetChosenTool` after the day's changes to the forget
  readers. All seven still delete the card with the call text naming it and with `4242`, and the
  near misses of step 1 list the card (`Forget everything my card holds.`, `Forget all my card
  numbers.`) or nothing (`Vergeet 4242 tot morgen.`, `Forget my todo list.`). No generator
  writes a forget of everything, so the cost of step 3 is still not counted; adding these forms
  to it comes first. No rule was built. Left open.
- 2026-11-24: added a forget of everything family to the generator: 846 messages in five
  languages with a keep clause after a read word for all, an unread one or no forget verb, with
  and without a clause mark, and 56 near misses. Before any change the card lists 340 of 3,468
  rows asked to keep, all in the forms with an unread part
  ([readings](../../readings/forget-everything-unread-forms.md)). Two rules were replayed. Read
  from the first forget verb, every form keeps its row, at 1,411 rows asked to delete newly kept
  over the generator and 92 of the near misses, so it is not built. Read from the next clause,
  118 rows are kept with none asked to delete over the generated cases, but 24 rows of 7 test
  literals that a later clause adds. Steps 2 and 3 now say this. Of the seven messages above,
  `Olvida todo, la tarjeta se queda.` and `Uită tot, cardul rămâne.` delete nothing for `4242`
  on this tree and delete the card for its own word; the other five delete it for both. No rule
  was built. Left open.
- 2026-11-25: done for the forms with a clause mark before the kept row. The clauses after the
  first one holding a forget verb outside a keep clause, or after the first clause of a message
  with none, are read as the runs after a value are, with rows named over the store, and a row a
  run names in a role no reader reads is kept (`_kept_later` in `forget_permit.py`). Over the
  family those forms list no row asked to keep, from 90; no case set lists a row it did not list
  before, and no row asked to delete is newly kept over the generator. The German requests to
  remember worded as a forget, as `Merk dir, dass meine Karte weg muss.`, now keep the row their
  forget call names (280 calls over the two families)
  ([readings](../../readings/forget-everything-unread-forms.md#the-later-clauses-read-2026-11-25)).
  The 222 rows of the forms with no clause mark are task [1341](1341-a-forget-of-everything-with-no-clause-mark-before-the-kept-row-lists-that-row.md).
