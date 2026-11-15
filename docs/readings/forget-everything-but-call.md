# Readings: a call naming a row beside a forget of everything but one fact

How the forget card (`unnamed` in `forget_unnamed.py`) reads `Forget everything but my card.` and
`Forget all 4242 except the card.` when the call names a row in the row's own words, such as
`gym code`. The draws that found the form are in
[forget-keep-no-call.md](forget-keep-no-call.md#rows-a-forget-request-holds-2026-11-15-what-was-drawn).
The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The card reading, 2026-11-15

Unit calls through `ForgetChosenTool` over an in-memory store. Before, a keep clause was read only
against the rows the call's text matched, and a part asking to forget that held only a word for all
listed no row, so each call below returned `KEPT_ALL`.

| Message | Rows stored | Call text | Before | After |
| --- | --- | --- | --- | --- |
| `Forget everything but my card.` | card, gym code | `gym code`, `gym`, `gym code is 4242`, `4242` | both kept | gym code deleted |
| `Forget everything but my card.` | locker code, card, phone | `locker code` or `phone` | all kept | the named row deleted |
| `Forget all 4242 except the card.` | locker code, card, phone | `locker code`, `phone`, `0721 555 4242` | all kept | the named row deleted |
| `Forget all 4242 except the card.` | locker code, card, phone | `card` | all kept | all kept |

Two readings changed. A word of the keep clause now counts as read when it names any stored row,
which `keep_named` finds by the word, and no longer only a row the call matched. And when the
words outside the keep clause are only a forget verb then a word for all, and the clause is one
opening word then only words naming a stored row, words for the or my and words for and, every
match the clause does not name is listed (`_all_else`).

These keep every row, as before: `Forget everything but my Visa.` and `... but my car.` over a row
holding `card` (the word names no stored row), `Forget everything but my card and my Visa.`,
`Forget them all but my card.`, `Now all but my card.`, `Forgot everything but my card.`,
`Forget everything but everything on my card.`, `Forget everything except the card, just the
phone.`, `Forget everything except the card, the phone too.`, `Vergiss alle außer der Karte, nur
die Karte.`, `Forget it except the card.` and `Forget my locker code but keep the card.` with the
call text `phone`. The tests are in `test_forget_all_else.py`.

Replay, the build before the change against the tree, same day:

| Pool | Cases | Call texts | Changed | Rows newly listed | Rows newly kept |
| --- | --- | --- | --- | --- | --- |
| 2,489 forget strings of the tests and `docs/readings/`, over 3 rows and over 18 | 5,186 | the string's number, or `4242` | 20 | 69 | 0 |
| Generated heads and tails in five languages, with what each row is asked | 42,356 | the value | 0 | 0 | 0 |
| The same generator with the heads `Forget everything`, `Forget all`, `Oublie tout`, `Vergiss alle`, `Olvida todas` and `Uită toate`, and every single tail | 14,183 | the value and each row's own word | not counted | 890 | 0 |

The pool's changed cases are 10 strings of the forms above, and each newly listed row
is a code row; no card row is listed. Each of the 890 rows the third pool newly lists
is one its message asks to delete: none is a row the message asks to keep, names in a role no
reader reads, or does not ask for. Scripts `gen9.py`, `run_words.py`, `cmp_words.py`, `replay.py`,
`run.py`, `poolcmp.py` and log `replay_all3.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/bd106a1a-a17f-4ca5-8841-82294e4917a8/scratchpad/slot9/`.

## A removal named after calls that kept every row, 2026-11-15

A draw earlier that day answered `Forget all 4242 except the card.`, after four forget calls that
each returned `KEPT_ALL`, with "I have updated your memories. I've removed the locker code and
phone number, but I've kept your card number." while both rows were stored. `claims_forgotten`
does not read that reply, since `removed` names no memory in its sentence, so the reply ended with
the note naming the kept rows and without `UNFORGOTTEN_CLAIM_NOTE`.

Unit calls of `unforgotten_claim` and `limit_notes`, same day. On a turn in which a forget call
kept every row it matched (`TaintLedger.forget_kept`, `forget_inside` or `forget_longer` holds a
row) and no forget call deleted a memory, the note is now also due when `names_removal` reads the
reply. Its first sentence, that no forget call in the turn deleted a memory, is true on every such
turn. It shows before the note naming the kept rows.

| Reply after calls that kept every row | Before | After |
| --- | --- | --- |
| `I've updated your memories and removed the locker code and phone number.` | kept rows note only | `UNFORGOTTEN_CLAIM_NOTE`, then the kept rows note |
| `The locker code is gone now.` | kept rows note only | `UNFORGOTTEN_CLAIM_NOTE`, then the kept rows note |
| `Your locker code and your phone number are still stored.` | kept rows note only | the same |
| `Nothing was removed.`, `I have not deleted the locker code.`, `Should I remove the locker code?` | kept rows note only | the same |
| Any of the first two after a later call deleted a row | no `UNFORGOTTEN_CLAIM_NOTE` | the same |

The reader is English only; a reply in another note language is read by `claims_forgotten_other`
as before. The tests are in `test_forget_kept_claim.py`.

## The rows and the card reading together, 2026-11-15

Rows e1 and v1 and the rule are those written before the first draws
([forget-keep-no-call.md](forget-keep-no-call.md#rows-a-forget-request-holds-2026-11-15-the-premise-the-rows-and-the-rule)),
where build A made a forget call in 1 of 6 draws and left the row to delete stored in 5 of 6. Build
B here is the stack brain `cortexn23-brain-1` rebuilt from the tree holding the card reading above,
the note above and `with_forget_reach` (`forget_reach.py`), which adds to the ranked rows of a
request to forget up to 5 rows it reaches. Drawn through the recording proxy (lines 490 to 579) on
engine build `b12375-9d25e0014`, default `judge` recall, a new chat for each turn, every card
approved, every row deleted before each draw. The SM clock read 0.58 of its maximum before and
after.

| Build | Row | Draws with a forget call | First request holds the row to delete | Card lists it | Left stored | Card lists the card row | Replies with an untrue sentence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B | e1 | 3 of 3 | 3 of 3 | 3 | 0 of 3 | 0 | 0 |
| B | v1 | 3 of 3 | 3 of 3 | 3 | 0 of 3 | 0 | 0 |

Every item holds. The e1 calls named `gym code` in 3 of 3 and each card listed the gym row alone.
The v1 calls named `locker code` and then `phone number` or `phone`, and each card listed that one
row, so the phone row, which the rule counts and does not judge, was deleted in 3 of 3. No card
listed the card row; the database held the card row alone after the last draw. The six replies say
the gym code, or the locker code and phone number, were forgotten and the card kept, which is what
was stored, and no reply ended with a note.

Item 5 was drawn against a side brain of the commit before these changes, both builds given the
same two stored rows. `Remember that my dentist is Dr. Pop.` had the same bytes.
`What is my card number?` had the same bytes once the date-time in the `schedule_task`
description, read from the clock per request, is masked. `Hello.` differed in its first pair: the
two rank requests were the same bytes and the rank answered no row for one build and both rows for
the other, so one first request held the recalled rows. Two more `Hello.` draws per build each got
no row from the rank, and all four pairs are the same bytes with the date-time masked. The rank
runs before `with_forget_reach`, which returns the ranked rows unchanged for a message that asks
to forget nothing.

The drawn build differed from the committed card reading in three checks these messages do not
reach: it also required `asks_to_forget` to read the message, it let a function word of the
message's language stand in the keep clause, and it read a kind word of a negated clause from a
stored row. The unit tests with these two messages and the call texts `gym code`, `locker code`
and `phone` pass on the committed build.
Scripts `draws.sh`, `ident.sh`, `ident2.sh`, `analyze.py`, `identcmp.py` and `ident2cmp.py` in the
slot directory above; logs `B-*.log`, `B-*.jsonl` and `ident*.log` in
`/home/david/.cache/cortex-run/2026-11-15/slot9/`.
