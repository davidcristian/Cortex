# Readings: a forget of everything naming a row in a role no reader reads

How the forget card reads a message that asks to forget everything and then names a stored row in
words no reader reads, such as `Forget everything, my card stays.` (`message_rows` in
`forget_permit.py`). The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s. The
same rule for a row named after a value is in
[forget-keep-except.md](forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15).

## Every row kept under an unread role, 2026-11-15

Over `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my phone is 0721 555 4242.`. Before, a call naming the card deleted it:

| Message | Call text | Before | After |
| --- | --- | --- | --- |
| `Forget everything, my card stays.` | `card` or `4242` | the card | none |
| `Forget everything, leave my card.` | `card` or `4242` | the card | none |
| `Forget everything apart from the card.` | `card` or `4242` | the card | none |
| `Forget everything, the card stays, the phone too.` | `phone` | the phone | none |
| `Oublie tout, la carte reste.` | `carte` | the card | none |
| `Olvida todas, deja la tarjeta.` | `tarjeta` | the card | none |
| `Forget everything on my card, the phone stays.` | `phone` | the phone | none |
| `Forget everything on my card, the phone stays.` | `card` | the card | the card |

No verb for stays and no phrase for except was added. The words after the word for all are split
into runs as the words after a value are, and a run naming a stored row with a word that no
reader of a limit, an addition or an exception reads has no role. The three roles list different
rows, so the card lists only a row a read limit names and that run does not.

These list what they listed before, with every call text: `Forget everything.`, `Forget
everything but my card.`, `Forget everything except my card.`, `Forget everything, also the
card.`, `Forget everything, only the card.`, `Forget everything on my card.`, `Forget everything
about my gym.`, `Forget everything I told you today.`, `Forget all of that.`, `Forget the card
that stays in my wallet.`, `Forget what stays the same.` and `Forget all my card numbers.`.

## The replay

The messages and call texts of
[the earlier replay](forget-everything-but-call.md#the-message-permits-and-the-call-selects-2026-11-15):
24,555 messages with 171,769 calls, the 42,356 generated messages with the value as the call
text, 5,400 test strings and 61 requests in Italian, Portuguese, Dutch and Polish with 305 calls.

| Count | Before to after |
| --- | --- |
| Rows newly listed, every replay | 0 |
| Rows listed that the generator marks asked to keep | 3,808 to 689 |
| Rows newly kept that it marks asked to keep | 3,119 |
| Rows newly kept that it marks either way | 838 |
| Rows newly kept that it marks not asked | 1,760 |
| Rows newly kept that it marks asked to delete | 4,827 |
| Value calls over the generated messages that changed | 0 of 42,356 |
| Test strings that changed, each keeping more rows | 4 of 5,400, 12 rows |
| Calls in the four unread languages that changed | 0 of 305 |

The 4,827 rows are the other rows of the same messages: `Forget everything, the card stays.`
with the call text `phone` kept nothing before and keeps the phone now, since a limit to the card
would keep it. A separate set of 172 messages holding no value, in the five languages with six
call texts each, lists 302 rows asked to keep before and 83 after. The 83 are under a word for
all the card does not read (`alles`, `todo`, `toate`, `tot`), which is filed with three English
forms that still list the card: no clause mark before the row (`Forget everything my card
stays.`), a verb the card does not read as a forget (`Wipe everything, my card stays.`) and
`Forget everything else, my card stays.`.

## The four blocked cells replayed, 2026-11-15

With every row kept under an unread role, `toate`, `doar`, `seulement` and `también` were each
filled alone in the table of forms (`forget_forms.py`) and replayed over the same messages. Rows
newly listed, by what the generator marks:

| Cell filled | Replay | Asked to delete | Either way | Not asked | Asked to keep |
| --- | --- | --- | --- | --- | --- |
| `toate` | every call text | 480 | 0 | 40 | 26 |
| `toate` | value call | 427 | 0 | 54 | 22 |
| `doar` | every call text | 270 | 83 | 18 | 8 |
| `doar` | value call | 471 | 160 | 49 | 8 |
| `seulement` | every call text | 1,179 | 279 | 272 | 0 |
| `seulement` | value call | 854 | 316 | 76 | 0 |
| `también` | every call text | 811 | 69 | 14 | 0 |
| `también` | value call | 838 | 160 | 28 | 0 |

No cell is filled, since a cell is filled only when no row newly listed is kept or not asked. The
rows `toate` lists that the message keeps are named with the Romanian article, which names no
stored row: `Uită toate, dulapul rămâne, și cardul.` with the call text `dulap`, and `Uită toate
4242, dulapul rămâne.` by value. `doar` lists the card of `Uită toate, cardul rămâne, doar
cardul.` while `toate` is unread, and the locker code of `Uită 4242 doar de pe dulap exceptând
dulapul.`. `seulement` and `también` list no row the message keeps. Their rows not asked are
beside an added or kept row: `Oublie tous les 4242, la carte aussi, seulement le téléphone.` lists
the locker code, as English `only` does, and `Olvida 4242, el teléfono también, solo la tarjeta.`
lists the phone, since `solo` is unread. Filled, `doar` also changes the Polish `Zapomnij 4242,
doar card.`, 2 of 305 calls in the four unread languages; the other three cells change none. Of
the 1,604 generated messages of at most one clause, 602 keep a row asked to delete with no cell
filled, and 577, 584, 580 and 588 with `toate`, `doar`, `seulement` and `también` filled.
