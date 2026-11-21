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

## A call naming a row the message does not name, 2026-11-15

Unit calls through `ForgetChosenTool` over an in-memory store, at the build before that day's
card changes (`git archive` of the published commit), at the build before this change and at the
tree. The first two builds gave the same rows, so the day's card changes did not make these.

| Message | Rows stored | Call text | Both earlier builds | Tree |
| --- | --- | --- | --- | --- |
| `Forget my gym code.` | card, gym code | `card` | card deleted | both kept |
| `Forget my locker code.` | locker code, card, phone | `phone` | phone deleted | all kept |
| `Forget all codes but my card.` | locker code, card, phone | `phone` | phone deleted | all kept |
| `Forget my gym code.`, two calls | card, gym code | `gym code`, then `card` | both deleted | card kept |
| `Forget what I just told you.`, `Please do it.`, `Forget that.` | card, gym code | `card` | card deleted | card deleted |
| `Forget my gym code.` | locker code, card, phone | `phone` | phone deleted | phone deleted |
| `Forget the 4242 of my locker.` | locker code, card, phone | `phone` | phone deleted | phone deleted |
| `Forget my locker code.` | locker code, card, phone | `my card is 4111` | card deleted | card deleted |

A match of a call text holding no digit was kept only when a word of the message named another
row the same call matched. `forget_named` now reads the store as `keep_named` does: in a message
holding no digit, a word of the part asking to forget that names the request of any stored row,
or of a row the turn deleted, keeps each match no word of the message names. A word for all that
ends a clause or is before a word for and asks for every row, so it keeps none this way. The last
three rows of the table are not fixed by this read: the second is kept by the rows the message
permits, in the last section, and the first and third are kept since 2026-11-21 by `_coded` and `_same_fact` (`forget_permit.py`): replayed over the 42,356 generated messages and 6,093 calls of the strings of the brain's forget tests, no generated case changed, no row was newly listed, and 605 rows were newly kept in 310 calls of 152 strings, each a card or phone row for the call text `card` or `phone` under a string holding a code word and naming neither.

Replay, the build before the change against the tree:

| Pool | Cases | Call texts | Changed | Rows newly listed | Rows newly kept |
| --- | --- | --- | --- | --- | --- |
| 2,522 forget strings of the tests and `docs/readings/`, over 3 rows and over 18 | 5,266 | the string's number, or `4242` | 0 | 0 | 0 |
| Generated heads and tails in five languages, with what each row is asked | 42,356 | the value | 0 | 0 | 0 |
| The same generator with the six heads asking for everything, and every single tail | 14,183 | the value and each row's own word | not counted | 0 | 1,072 |

Of the 1,072 newly kept rows, 698 are rows the message does not ask for, 56 it asks to keep, 20
it names in a role no reader reads, and 298 it asks to delete. All 298 are in Romanian messages
that start `Uită toate`, a word for all the card does not read. Scripts `replay_final.sh`,
`dcases.py`, `dlang.py` and log `replay_final2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/bd106a1a-a17f-4ca5-8841-82294e4917a8/scratchpad/slot10/`,
with slot 9's generator and runners.

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

## The committed build redrawn, 2026-11-15

Rows e1 and v1 again under the same rule, on the stack brain rebuilt from the commit holding the
card reading, the note and `with_forget_reach`, with two rows added before the draws: a1, the three
v1 facts then `Forget all 4242 apart from the card.`, and g1, the two e1 facts then `Forget my gym
code.`. Same engine build, proxy, recall and approval as above (proxy log lines 625 to 770). The
SM clock read 0.58 of its maximum before and after. No body listened, so a row counts as deleted
when an approved card listed it.

| Row | Draws | Forget calls | Card lists a row to delete | Rows to delete left stored | Card lists a row to keep | Replies with an untrue sentence |
| --- | --- | --- | --- | --- | --- | --- |
| e1 | 3 | 4: `gym code` twice, `4242` once, then one that matched no row left | 3 of 3 | 0 | 0 | 0 |
| v1 | 3 | 6, `locker code` then `0721 555 4242` or `phone` | 3 of 3, both rows | 0 | 0 | 0 |
| a1 | 2 | 4, `locker code` then `phone` | 2 of 2, both rows | 0 | 0 | 0 |
| g1 | 2 | 2, text `4242` | 2 of 2 | 0 | 0 | 0 |

The committed build matches the drawn one on e1 and v1. In a1 each card listed the one row its
call named and both rows were deleted, as in the earlier a1 draws: the role of `apart from the
card` is not read, and the card keeps every row under it only for a call text holding the value.
With the text `card` the same message keeps the card in a unit call. In g1 the
card listed the gym code and showed the card row as kept under `INSIDE_LINE`. Logs `A-*.jsonl`
and `B-*.jsonl` in `/home/david/.cache/cortex-run/2026-11-15/slot10/`. The rows were drawn again after the later card changes ([readings](forget-everything-unread-role.md#drawn-after-the-card-changes-2026-11-15)).

## The reach beside the defences already there, 2026-11-15

Unit runs of `assemble_inference_messages` over an in-memory store (`reach_audit.py`, same
directory as the replay above).

| Defence | What was run | Result |
| --- | --- | --- |
| Framing and taint | a tainted row holding `4242` and an instruction, reached and not ranked | inside the untrusted fence with the turn's nonce; the ledger is tainted and holds the row's id, as for a ranked row |
| Limits | 300 rows of 900 characters holding `4242`, `Forget 4242.` | 10 rows, the 5 ranked and the 5 oldest holding the value, each cut to 600 characters inside the one recall budget; a turn asking a question holds 5 |
| Scope | a session scope, a row of another chat holding the value | not reached by value or by nearness |
| Trigger | `Don't forget my card 4242.`, `I forgot my code 4242.`, `How do I make you forget 4242?`, and requests in Italian, Portuguese, Dutch and Polish | no row reached |
| Trigger | `Can you forget things like 4242?` | read as a request; 2 rows reached, framed as above |
| Logs | the added lines of the change | none writes a log line |
| State | `forget_reach.py` | one function over the store's reads; it keeps nothing between turns |

A reached row goes through `_render_memory_context` with the ranked ones, so the fence and the
ledger treat both alike. What the table leaves open is filed: the smaller share each row gets, no
line saying more rows hold the value, and the recall audit record, which holds only ranked rows.

## The message permits and the call selects, 2026-11-15

The card now builds, for a call text holding no digit, the card for each whole value of the
message and lists a match only when that card lists it, or when a word of the forget part names
it, it holds no value of the message as a whole group and no role keeps it. Replayed before and
after: 24,555 messages (the recorded word cases, and every fourth case of the two generated
mixes of head, tail and row in five languages), each with the value, each row's own word,
`code` and two mixed texts as the call text, 171,769 calls.

| Count | Before to after |
| --- | --- |
| Rows newly listed | 0 |
| Calls holding a digit, or beside a message without its value, that changed | 0 |
| Word calls beside a message holding its value that list a row the value call does not | 0 of 44,740 after |
| Rows newly kept that the generator marks asked to keep | 1,612 |
| Rows newly kept that it marks either way | 500 |
| Rows newly kept that it marks not asked | 3,073 |
| Rows newly kept that it marks asked to delete | 2,953 |
| Rows newly kept with no mark | 14 |

Each of the 2,953 is a row the call by value keeps too. The largest groups are a plain head with
one or two added rows (`Forget 4242, the card too.` keeps the phone and the locker code: 284
rows), a word for all with a limit then an added row (`Forget all 4242, only the card, also the
phone.`: 105) and an added row beside `stays` (382 over four forms). The reading of an added row
by the value call is filed. `Forget that.`, `Yes, forget it.`, `Forget what I just told you.` and
`Forget everything but my card.` list the same rows as before with every call text.

## The words read for a form, by language, 2026-11-15

Each translation of a word English reads was replayed as a filled cell of the table of forms
(`forget_forms.py`) over the messages and call texts of the section above, the 42,356 generated
messages with the value as the call text, 5,334 test strings and 61 requests in Italian,
Portuguese, Dutch and Polish. A cell is filled only when no row newly listed is kept or not asked.

| Cells filled | Replay | Asked to delete | Either way | Not asked | Asked to keep |
| --- | --- | --- | --- | --- | --- |
| Every translation | every call text | 2,510 | 413 | 374 | 92 |
| Every translation | value call | 3,268 | 748 | 341 | 30 |
| `nur`, `toute`, `jede`, `jeden`, `jedes` | value call | 490 | 92 | 96 | 0 |
| `toute`, `jede`, `jeden`, `jedes` | every replay | 0 | 0 | 0 | 0 |

The 92 rows by word: `toate` 50, `toate` with `doar` 22, `doar` 2, `seulement` 6, `también` 12.
Each is a row the message says stays (`rămâne`, `reste`, `se queda`) and names again, as in
`Oublie tout, la carte reste, seulement la carte.` with the call text `carte`, a form read since
([readings](forget-everything-unread-role.md)). `nur` lists a locker code no clause of `Vergiss alle 4242, die
Karte auch, nur das Handy.` asks for. `todos` and `alles` changed `Esqueça todos os 4242.` and `Verwijder alles,
de card ook.`, which the card does not read. So only the last row is filled. No generated message
holds its words: with `tous les` or `toutes les` swapped for `toute`, and `alle` for each German
form, 2,227 French and 1,960 German messages list the rows of the unswapped message. Of the 1,604
messages of at most one clause, 602 still keep a row asked to delete (505 with every cell filled). The four cells of the 92 rows were replayed again once that form was read and stay empty ([readings](forget-everything-unread-role.md#the-four-blocked-cells-replayed-2026-11-15)).
