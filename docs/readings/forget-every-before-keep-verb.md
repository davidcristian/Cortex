# Readings: a word for all before a keep verb in the same clause

How the card reads a forget message whose word for all and keep verb are in one clause, such as
`Forget every 4242 but keep the card.`. The comma forms, such as `Forget every 4242, keep the
card.`, are in [forget-keep-except.md](forget-keep-except.md). The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The words of a clause before its keep clause, 2026-11-24

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, `Forget every
4242 but keep the card.` deleted only the locker row and kept the phone, while `Forget every 4242,
keep the card.` deleted the locker and phone rows. `quantifies` (`forget_unnamed.py`) read no
clause holding a keep verb, so the word for all before `but keep` was not read.

`quantifies` now reads each clause up to the first word inside a keep clause
(`keeping` in `forget_clauses.py`), so the message above deletes the locker and phone rows and
keeps the card, and so do its French and Spanish forms. The German form deletes the locker row
and keeps the `Handy` row, which names no kind of the table of `forget_kinds.py`, and the Romanian
form keeps every row, each as its comma form does. It still reads no word for all
in `Keep every 4242.`, `Forget 4242 but keep every card.` or `Forget all but keep 4242.`. Kept as
before: every row for the first, the card and phone for the second, and a badge `9000 4242`, which
names no kind of the table either.

Method: the 2026-11-23 forget card generator (head, tail and tail over three rows in five
languages, with its oracle of what the message asks of each row), with this form added: the
generator's heads before a keep verb after `but` or `and` with no comma, in each language, mixed
with its adding, limiting, except and staying tails, 5,532 cases, and 26 near misses. Each case
ran through the card at the tree before and after the change, with the string literals of the
brain's forget tests under five call texts, 63,877 cases in all. The run is in
`~/.cache/cortex-run/2026-11-24/f1/` (`replay.sh`, `f3gen/f1forms.py`, `f3gen/count3.py`).

| Count over the 53,207 generated cases | Before | After |
| --- | --- | --- |
| Rows the message asks to keep that the card deleted | 0 | 0 |
| Rows the message asks to delete that the card kept | 30,986 | 30,918 |

Of the generated rows newly deleted, 68 are rows the message asks to delete and one is the phone of
`Forget 4242, all but keep the card.`, which the oracle reads as unsure. Each case whose rows
changed and whose message with a comma before its keep verb is also a case now deletes what that
message deleted before, 79 of 79. Four rows the message does not ask for are newly deleted, in
`Olvida todas las 4242 pero mantén la tarjeta solo de la tarjeta.` and three like it, and four are
newly kept, in `Forget all 4242 but keep the card, just the card.` and three like it, as their comma
forms did before. The word pairs and valued cases of the 2026-11-23 audit deleted the same rows
before and after. Cutting only a clause holding a keep verb, and leaving a clause whose keep clause
opens with a word for except or a negation whole, deleted the same rows in every case.
