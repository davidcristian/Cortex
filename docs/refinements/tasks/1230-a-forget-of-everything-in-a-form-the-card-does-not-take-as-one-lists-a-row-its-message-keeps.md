# A forget of everything in a form the card does not take as one lists a row its message keeps

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

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
| `Forget everything else, my card stays.` | `else` is a topic word (`TOPIC`) |
| `Vergiss alles bis auf die Karte.` | `alles` is left unread, since Dutch has it too |
| `Olvida todo, la tarjeta se queda.` | `todo` is left unread, since Portuguese has it too |
| `Uită tot, cardul rămâne.` | `tot` also means still and is a Dutch word |

## What to do

1. Write near misses first: `Forget everything my card holds.`, `Forget all my card numbers.`,
   `Vergeet 4242 tot morgen.` and `Forget my todo list.` must list what they list today.
2. Read `alles`, `todo`, `toda`, `todos` and `tot` only to keep: a set this rule alone reads can
   keep a row and can list none, so a Dutch or Portuguese message is not read as asking for
   every row.
3. For the form with no clause mark, keep every row when the words after the word for all name a
   row and end in a word no reader reads, and count the limits that then keep a row asked to
   delete (`Forget all my card numbers please.`).
4. Replay with `every.py`, `replay.sh` and `show.py` of the readings above, kept in
   `/home/david/.cache/cortex-run/2026-11-15/slot13/`.

## History

- 2026-11-15: filed from the replay of the forget of everything read by role
  ([readings](../../readings/forget-everything-unread-role.md)).
