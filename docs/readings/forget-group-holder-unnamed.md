# Readings: a row holding a forget's value only inside a longer value, beside a named row

How `kept_rows` (`forget_inside.py`) reads a forget whose call text, such as `4242`, is held by
one matched row the message names (a card) and by another only as a group of a longer value (a
mobile phone `0721 555 4242`) that the message does not name. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; the kind words are in
[forget-kind-and-value-names.md](forget-kind-and-value-names.md).

## What the reader does, 2026-11-13

A matched row holding the call's text only inside longer values (`_in_longer`: every place the
row holds it is inside a value span and never the whole span) is kept and listed under
`KEPT_LINE` when a word or kind word of the message, less the function words of its readings,
names another row this call matched, and none names this row (`_unnamed_groups`). Beside a clause
asking to keep, `unnamed` already keeps every such row that no word outside the clause names. A message asking for every row (`quantifies`, such as `Forget every 4242,
the card first.`) keeps nothing this way, and neither does a message naming only the value
(`Forget 4242.`) or naming no matched row. A row a call of the turn deleted does not count as
named, since `Forget my dog and the 4242 I just told you.` names the value as its own fact.

So `Forget the card ending in 4242.` over the card and the mobile phone deletes the card and keeps
the phone, from the calling chat and a new one; two cards ending in `4242` both stay listed. The
tests are `test_forget_group_unnamed.py`.

## The start build's kind word replay, read again

Taken 2026-11-13 over the per case list of the kind word change
([replay](forget-kind-and-value-names.md#replay-through-the-start-build-and-the-change)).

| Class | Cases | Strings | Right |
| --- | --- | --- | --- |
| A card kind word names a French or German card beside a code holding `4242` whole, which is kept | 61 | 23 | yes |
| `N'oublie pas ma carte.` no longer deletes the newest row of the chat | 16 | 1 | yes |
| A clause with `menos`, `moins` or `mai puțin` keeps a card for the whole card number | 22 | 3 | yes |
| A text holding a negation (tool results, assistant replies) keeps the French or German row the calling chat stored last, and the kept note names it | 18 | 12 | yes |
| `Uită codul 4242 mai puțin cel de pe card.` keeps the gym code and still deletes the French or German card | 4 | 1 | no |
| A card kind word deletes the card instead of the gym code or phone the chat stored last | 9 | 5 | yes |

The 121 cases listing fewer rows are the first five classes; the 9 listing another row are the
last. The Romanian message deletes the card it asks to keep at the start build too (both rows
there), and over the English card at both builds, since no word for minus opens a keep clause and
`card` is the English row's own word; the minus reader of
[forget-word-and-minus-unnamed.md](forget-word-and-minus-unnamed.md) keeps that card.
A forget whose other clause holds a negation kept a row named only by its kind at both builds;
the kind reader reads the negation per clause
([readings](forget-kind-and-value-names.md#a-negation-read-per-clause)).

## Replay through HEAD and the change

Taken 2026-11-13 with the scripts of the kind word replay, the strings of tests added since and
the night's proxy log (1,426 strings), and six more row sets: two cards ending in `4242`, a mobile
phone before the card, the French and German card beside the mobile phone, a desk phone
`0721 4242 555` holding `4242` as a middle group, and two cards beside the mobile phone.

| Cases | Changed | Lists more rows | Lists fewer rows | Lists another row |
| --- | --- | --- | --- | --- |
| 185,880 | 538 from 46 strings | 0 | 538 | 0 |

Each changed case keeps a row holding `4242` only inside a longer value beside a row the message
names: the mobile phone (324 cases) or the desk phone (46) for a card message such as `Forget my
card 4242.`, `Oublie la carte qui finit par 4242.` or `Forget my bank card.`, and a card (168) for
a phone message such as `Forget my phone ending in 4242.`, `Lösch meine Telefonnummer.` or
`Forget my phone account.`. Eight cases keep the French or German card beside the gym code or the
mobile phone for `Remember that I deleted my account.` and two `Remember:` messages, whose word
`remember` names the English row. `Forget 4242.` and `Forget every 4242` change no case. Scripts
`replay.py`, `group.py` and the logs `old.jsonl`, `new.jsonl` and `diff.txt` are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot5/`.

## Neighbouring flows on the live stack: rows and the rule

Written before any draw. The build is the working tree with the change, run as
`cortexn21-brain-s5group` through the recording proxy on the `cortexn21` stack (memory tools only,
like the stack brain), every card approved, every row deleted before each draw, and each fact
stored in a chat of its own.

| Row | Facts stored | Forget turn | Draws |
| --- | --- | --- | --- |
| j | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.`, same chat | 2 |
| v | `Remember that my card is 4111 1111 1111 4242.`, `Remember that my mobile phone is 0721 555 4242.` | `Forget 4242.`, a new chat | 2 |
| c | the same two facts | `Forget the card ending in 4242.`, a new chat | 2 |

The rule: in j every draw that calls a forget tool deletes the locker row; in v every draw that
calls one with the text `4242` deletes both rows; in c no draw deletes the mobile phone row, and
each draw calling one with the text `4242` deletes the card and names the phone in the kept note.
A draw with no forget call is counted apart and fails no item.

Added after the first j draw stored no row, before the draw it adds: one more j draw, j3, which
replaces a j draw whose store turn kept no row, under the same rule.

## Neighbouring flows on the live stack: what was drawn

Drawn from 03:29 to 03:33 on 2026-11-13 on `cortexn21-brain-s5group`, proxy log lines 396 to
451. The SM clock read 0.58 of its maximum between draws.

| Row | Draws with a forget call | Call text | Rows stored after |
| --- | --- | --- | --- |
| j | 1 of 3 reached a stored row (j2) | `7319` | none, 1 of 1 |
| v | 2 of 2 | `4242` | none, 2 of 2 |
| c | 2 of 2 | `4111 1111 1111 4242` | the mobile phone row, 2 of 2 |

Every item of the rule holds where its form was drawn. In j1 and j3 the store turn itself called
`forget_memories`, which matched no row, so the reply kept nothing in memory and the forget turn
matched nothing, since this build kept the forget tool on a plain English statement
([the store turn](forget-refusal-english-statement.md)).
In c both calls sent the whole card number, which the phone row does not hold, so the card listed
the card alone at HEAD too; no c draw sent `4242`, so the new keep was not drawn, as no x draw of
the kind word change sent it. Scripts `draw.sh` and `draw3.sh`, logs `draw.log`, `draw3.log` and
`draws.jsonl`, in the slot directory above.
