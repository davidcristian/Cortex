# Readings: a forget of everything in a form the card does not read as one

How the forget card treats a message that asks to forget every row and to keep one, in a form
that `everything` (`forget_permit.py`) does not read: no clause mark before the kept row, no
forget verb, or a word for all that no cell of the table of forms (`forget_forms.py`) holds. The
decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s. The forms the card does read
are in [forget-everything-unread-role.md](forget-everything-unread-role.md).

## The generated family, 2026-11-24

Over the generator's three rows in each of five languages (a card, a phone and a locker code,
each holding `4242`), with the call text `4242` and with each row's own word. Each message asks
to forget every row and keeps one, in each of the generator's keep clauses (except, but, keep,
stays, not) and six more per language: the stays clause with no clause mark, as in `Forget
everything the card stays.`, and `leave`, `apart from`, `à part`, `bis auf`, `menos` and `în
afară de`. That is 3,468 cases over 846 messages, each case with one row asked to keep. The rows
asked to keep that the card lists, on the tree of this date:

| Head | Clause mark before the kept row | Messages | Rows asked to keep | Listed |
| --- | --- | --- | --- | --- |
| read, as `Forget everything`, `Oublie tout`, `Olvida todas` | yes | 213 | 852 | 0 |
| read | no | 96 | 432 | 66 |
| word for all unread, as `Vergiss alles`, `Olvida todo`, `Uită tot`, `Uită totul` | yes | 174 | 696 | 28 |
| word for all unread | no | 96 | 384 | 60 |
| no forget verb, as `Wipe everything`, `Everything must go`, `Alles muss weg` | yes | 183 | 732 | 90 |
| no forget verb | no | 84 | 372 | 96 |

Of the 340 rows listed, 158 are listed for the call text `4242` and 182 for the kept row's own
word. `Forget everything the card stays.` lists the card alone for `4242`: `the card` opens as a
limit does. `Olvida todo, la tarjeta se queda.` lists the card only for `tarjeta`, since the
words after the call text in the message name no row.

The family also writes near misses: 51 messages asking to forget one row with a word for all,
such as `Forget everything the card holds.`, `Forget all card numbers.`, `Olvida todo sobre la
tarjeta.`, `Vergiss alles über die Karte.` and `Uită tot despre card.`, and five naming no stored
row, such as `Forget my todo list.` and `Vergeet 4242 tot morgen.`.

## Two rules replayed, 2026-11-24

Both keep a row named in a run whose role no reader reads (`kept_again` in `forget_clauses.py`),
with the runs read as the runs after a value are, from the first forget verb or, in a message
with none, from its first word. Each was replayed over the family, the generator of the previous
night's forget slots (71,332 cases, with the test literals), the a1 word pairs (12,768) and the
valued cases (4,104). Rows asked to keep still listed, and rows asked to delete newly kept:

| Runs read | Keep rows listed in the family | Newly kept: family | Generator | Pairs and valued |
| --- | --- | --- | --- | --- |
| from the first forget verb, its own clause included | 0 | 92 | 1,411 | 0 |
| only the clauses after that verb's clause | 222 | 0 | 0 | 0 |

The first rule makes every form above fail safe. It also keeps the row of every near miss naming
one, in 47 messages such as `Forget everything the card holds.` and `Forget all card numbers.`,
and of 1,198 generated messages such as `Forget all 4242 and the card.`, and 389 rows the
generator marks as either way. With no new word read, `my card stays` differs from `my card
holds` only by a word no reader reads, so no rule keeps one without the other.

The second keeps the rows of every form with a clause mark, 118 of the 340, and 3 rows asked
to keep in the valued cases, as the locker code of `Forget my lockers 1234, the locker stays.`.
It names rows only from those the call lists, so a row a later clause adds is read as unread: it
keeps 24 rows asked to delete in 7 forget messages of the test literals, as the phone of `Forget
the locker code 4242, the phone and the card too.` for the call text `phone`. The near misses
list what they listed before under both rules. Neither rule is built.

Scripts: `f3gen/every.py` (the family), `ecount.py`, `ebreak.py`, `gtable.py`, `delta.py` and
`replay4.sh` in `~/.cache/cortex-run/2026-11-24/f4/`; the generator is `f3gen/` there.
