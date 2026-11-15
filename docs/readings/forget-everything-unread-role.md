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
