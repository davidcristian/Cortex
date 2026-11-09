# Readings: a forget that reaches a second fact through its number

What the cortex does after a `forget_memories` delete whose result says other rows still hold a
number a deleted row held. Flow n1 of [the corrections flows](overlay-corrections-flows.md) saw it
forget that number in the same turn, unasked, and so delete a second fact. The tool is
[ADR-0008](../adr/ADR-0008-memory-v1.md)'s; the closing note that tells the person the number
remains is `NUMBERS_LEFT_NOTE` in `numbers_left_claim.py`.

## The rig

**2026-11-08**, the `cortexn16` GPU stack: the resident cortex (gemma-4-12B) at a context of
16,384 tokens, no deep tier, memory on pgvector with the default `global` scope. Two seed turns,
`Remember that my gym locker number is 5521.` and `Remember that the shed padlock code is also
5521.`, ran once in their own chats; the driver copied their two rows into a template table and,
before each draw, put a fresh copy of both rows back under new ids. Each draw is one turn in a new
chat, `Forget my gym locker number.`, with every card approved. After it the driver read which of
the two rows remain and the cards the turn showed. Driver and records: `draw.sh`, `base.log`,
`fixed.log`, `*.jsonl` and `req-*.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot17/`.

## Rows and rule

Written before the first draw.

| Build | Draws | What it is |
| --- | --- | --- |
| base | 8 | the stack brain, built from `f3e6d7fb3`: the result after the first delete ends "a forget of the number itself would remove them" |
| fixed | 8 | a second brain through the recording proxy, built from the working tree: a later `forget_memories` call in the turn whose text holds a value the message does not hold, after a delete that left rows holding a deleted row's number, is refused once, and the rows are kept |

Counted per draw, on both builds: the **form** (a second `forget_memories` call naming 5521, read
from the second card on base and from the refusal in the proxy's requests on fixed), whether the
**padlock row** remains, and whether the reply says the padlock code or the number was forgotten.

**Rule.** The refusal ships when, on fixed, the padlock row remains in every draw whose first call
deletes the gym row alone, and every such draw with the form shows the refusal in its requests.
The form's count is recorded on both builds and does not decide, so a form that is rare on fixed
does not stop the fix. A fixed draw that retries the value after the refusal and deletes the row
fails the rule. A draw whose first call is the value itself is counted apart: its first request is
the same on both builds, so the change cannot reach it; this item was set apart after the base
rows and before the fixed ones. Unit tests decide the other side: a forget
the person asked for by value, in English, French, German, Spanish and Romanian, is never refused.

## Results

| Build | Draws | First call `gym locker number`, then `5521` unasked | First call `5521`, card lists both rows | Padlock row deleted | Reply names the padlock |
| --- | --- | --- | --- | --- | --- |
| base | 8 | 6 | 2 | 8 | 0 |
| fixed | 8 | 4 of 5 gym-first draws, each refused | 3 | 3, all value-first | 0 |

On base every draw deleted the padlock row with its card approved, and every reply said only "I've
forgotten your gym locker number." On fixed the padlock row remained in all 5 draws whose first
call was `gym locker number`; the 4 that then called `5521` each read the refusal and made no
retry, and all 5 replies ended with `NUMBERS_LEFT_NOTE`. The rule passes, so the refusal ships.
The 3 value-first draws deleted both rows through one card that listed both, and the reply named
only the gym locker; that form is drawn
[below](#a-first-call-by-value-that-lists-another-fact-rows-and-rule-2026-11-09).
The SM clock read 0.43 to 0.63 of its maximum (`clocks.sm` over `clocks.max.sm`) across both builds.

## A first call by value that lists another fact: rows and rule, 2026-11-09

The rig above on the `cortexn17` stack. The two seed turns ran once on the stack brain built from
`c4e83dea1`, whose replies were `I've noted that your gym locker number is 5521.` and `I've noted
that the shed padlock code is 5521.`. Driver and records: `draw.sh`, `base.log`, `fixed.log` and
`*.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot3/`.

Written before the first draw.

| Build | Draws | What it is |
| --- | --- | --- |
| base | 8 | the stack brain, built from `c4e83dea1`, which has the refusal of a later value forget |
| fixed | 8 | a second brain through the recording proxy, built from the working tree: when the call's text holds a value the person's message lacks, each matched row whose own request holds that value and that holds no word of the message is listed apart on the card and kept |

Counted per draw, on both builds: the **form** (the first call's text is `5521`), whether the
**padlock row** and the **gym row** remain, and the reply.

**Rule.** The change ships when, on fixed, every draw showing the form keeps the padlock row and
deletes the gym row, and no draw deletes the padlock row. The form's count is recorded on both
builds and does not decide; if no fixed draw shows it in 8, fixed is drawn until two do, within a
12 minute cap, and with none the change does not ship. A draw whose first call is a label reaches
the same first request on both builds, so its rows are counted but decide only the last item. Unit
tests decide the restatement side: each value first draw recorded in
[forget-value-repeats.md](forget-value-repeats.md) (fr2, yr1, frv1 to frv3, yrv1, en-r1, en-r2 and
pp1 to pp3) still deletes every row it deleted, since a recall row holds the value only in its
reply and each fact row holds a word of its message.

## The draws of both builds, 2026-11-09

The base draws ran on the stack brain and the fixed draws on a second brain through the proxy,
sharing the stack's model host and store, every card approved. The SM clock read 0.57 to 0.58 of
its maximum (`clocks.sm` over `clocks.max.sm`) before every draw on both builds.

| Build | Draws | First call `5521` (form) | Padlock row left | Gym row left | Later `5521` call, refused | Reply ends with `NUMBERS_LEFT_NOTE` |
| --- | --- | --- | --- | --- | --- | --- |
| base | 8 | 3 | 5, none of the 3 with the form | 0 | 5 of 5 label first draws | the 5 label first draws |
| fixed | 8 | 6 | 8 | 0 | 1 of 2 label first draws | 8 |

On base each of the 3 draws with the form deleted both rows through one card, and the replies were
`I've removed that from my memory.`, `OK. I've forgotten your gym locker number.` and `I've
forgotten that information.`. On fixed each of the 6 cards with the form listed the gym row to
delete and the padlock row under `Kept, since your message names none of their words:`, and each
reply was `I've forgotten your gym locker number.` with the note. No later call on either build
ran: every one was refused, so each held a value the message lacks. The fixed one was `5521`, and
the base audit keeps the texts as `<redacted>`. The rule
passes, so the change ships. Unit tests replay the value first draws of
[forget-value-repeats.md](forget-value-repeats.md), and each still deletes every row.

## Later calls when the message holds the value: count and rule, 2026-11-09

In the n1 setup the message holds no value, so a later call holding the asked value beside
another cannot occur there, and the 16 draws above show no later call that ran. The `n1v` flow
keeps the rig and asks `Forget my gym locker number, it is 5521.`, so a later call holding `5521`
runs. Eight draws on a second brain through the proxy, built from the commit that keeps a fact the
message does not name, count each later `forget_memories` call by form: the value alone, the value
beside a phrase or another value, a phrase naming the padlock, other.

Written before the draws: `value_unasked` changes only if a later call with the value beside a
phrase or another value, or a phrase naming the padlock, occurs. A later call of the value alone
is the forget the message asked for and is not counted against the check.

## The n1v draws, 2026-11-09

Eight draws, every card approved, the SM clock at 0.57 to 0.58 of its maximum before each.

| First call | Draws | Later calls, by form | Padlock row left |
| --- | --- | --- | --- |
| `5521` | 4 | none | 0: each card listed both rows, since the message holds the value |
| `gym locker number` | 4 | the value alone, in 2 | 2: the two draws with no later call |

No later call held the value beside a phrase or another value, and none named the padlock, so
`value_unasked` is unchanged. Over the 24 draws of both setups, all 8 later calls were the value
alone. Every reply said the gym locker number was forgotten, and both draws that left the padlock
row ended with `NUMBERS_LEFT_NOTE`; one of them first said `I have also cleared that specific
number`, which no call did, and the note then said the number is still held. The 6 draws that
deleted the padlock row, on a message naming the value only to identify the gym locker, are drawn
[below](#a-value-named-beside-a-label-rows-and-rule-2026-11-09). The run record is `n1v.jsonl` in
the slot directory above.

## A value named beside a label: rows and rule, 2026-11-09

The `n1v` rig above, with the two seed rows stored again from new seed turns on the stack brain
built from `e19b9df09`, and put back under new ids before each draw. The draws above are the base:
6 of 8 deleted the padlock row. Driver and records: `draw.sh`, `seed.log`, `fixed.log` and
`fixed.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot4/`.

Written before the draws.

| Build | Draws | What it is |
| --- | --- | --- |
| fixed | 8 | a second brain through the recording proxy, built from the working tree: when the person's message holds the call's value, a matched row whose request holds the value and that holds no word of the message is listed apart and kept, once a word of the message names another matched row or a row deleted earlier in the turn, and only when the message has no word such as `everywhere` or `all` |

Counted per draw: the **form** (a call whose text is `5521`, first or later), whether the padlock
and gym rows remain, the cards, and the reply.

**Rule.** The change ships when every fixed draw deletes the gym row and keeps the padlock row,
every card showing the padlock row lists it under `KEPT_LINE`, and no reply says nothing was
forgotten or that the padlock code was. The form's count is recorded and does not decide; if no
draw shows it in 8, fixed is drawn until two do, within a 12 minute cap, and with none the change
does not ship. Unit tests decide the other side: a message naming only the value, the value with
`everywhere` or `all`, both labels, or a label no stored row holds still deletes every row, and
each recorded value first draw of [forget-value-repeats.md](forget-value-repeats.md) and of this
file gets the same card through the old and the new reader, except the `n1v` draws.

## The fixed draws, 2026-11-09

Eight draws, every card approved, the SM clock at 0.57 to 0.58 of its maximum before each. The seed
replies were `I've noted that your gym locker number is 5521.` and `OK. I've remembered that the
shed padlock code is 5521.`.

| First call | Draws | Later call | Padlock row left | Gym row left |
| --- | --- | --- | --- | --- |
| `5521` (form) | 2 | none | 2 | 0 |
| `gym locker number` | 5 | `5521` (form) in 1, result `KEPT_ALL` | 5 | 0 |
| `gym locker number is 5521` | 1 | none | 1 | 0 |

Both cards of a first call of `5521` listed the gym row to delete and the padlock row under
`KEPT_LINE`. The later call read the gym row the turn had deleted as the fact the message names,
so its rows were kept and no card was shown. No card listed the padlock row for deletion, no reply
said nothing was forgotten, and none named the padlock. Seven replies said the gym locker number
was forgotten and ended with `NUMBERS_LEFT_NOTE`. The eighth, a label first draw whose requests
match the base build's, said `I've updated your gym locker number to 5521.` and ended with the note
that nothing in the message was kept
([task 1073](../refinements/tasks/1073-a-forget-naming-the-value-can-be-answered-as-an-update.md)).
The rule passes, so the change ships.

Replayed through the old and new reader, the value first draws of
[forget-value-repeats.md](forget-value-repeats.md) and the n1 draws above keep the same rows; only
the two `n1v` forms differ. Of the eleven recorded messages in these readings that hold the value
they forget, only `n1v` stored two facts sharing it, and the new reader keeps a row only when
another matched row, or one the turn deleted, holds a word of the message. The run record is
`fixed.jsonl` in the slot directory above, with the proxy lines `proxy-fixed.jsonl` and the replay
`replay.py` beside it.

## Audit probes of the keep reader, 2026-11-09

Unit calls of `unnamed` over two rows holding 7319, a bike lock row and a shed padlock row, with
the call text 7319. No turn was drawn. Kept rows per message:

| Message | Kept |
| --- | --- |
| `Forget my bike lock code 7319.` | shed |
| `Forget the bike lock code 7319 and nothing else.` | shed |
| `Forget my bike lock code 7319, keep everything else.` | none |
| `Forget my bike lock code 7319, that's all.` | none |
| `Forget all about my bike lock code 7319.` | none |
| `Oublie le code de mon vélo 7319, c'est tout.` / `... partout.` | none |
| `Vergiss 7319, mein Hund ist tot.` / `Vergiss den Fahrradcode 7319 überall.` | none |
| `Vergiss den Fahrradcode 7319, alles andere bleibt.` | none |
| `Olvida el código de la bici 7319, eso es todo.` / `... en todos lados.` | none |
| `Forget my user id 7319.` (a user id row and the shed row) | none |

A word of `_EVERY` anywhere in the message kept nothing; the German and Spanish rows name no
word of either English row, so they keep nothing by that rule as well. A label word in `_COMMON`
named no fact. Both are changed in the reader below.
A forget turn is never recorded unless every forget call matched nothing, and a call that kept
rows returns `KEPT_ALL` with `matched_nothing` false, so the kept-rows note is not written into a
stored exchange (read from `memory_claim.py` and `memory_forget_chosen.py`, not run).

One live draw on the stack brain, with the two rows stored by two chats and the card refused:
`Forget my bike lock code 7319, keep everything else.` drew a `forget_memories` call with the
text `bike lock`, so the value path was not reached, the card listed only the bike row and both
rows stayed. The SM clock read 0.58 of `clocks.max.sm`. Scripts `live1077.sh` and
`probe45.py` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot8/`.

## The keep reader reshaped, 2026-11-09

`unnamed` now fails toward keeping rows in three places. A word for all asks for every row only
within two words of a value (or alone in the clause after one), outside a clause asking to keep
and not before `about` or `else`; `tot` is no longer read. A word for all after the verb is not
read: it decides only when a word of the message names a fact, as in `Forget it all, my bike lock
code 7319.`, where the named fact is the one asked for. A row's `User:` and `Assistant:`
labels are removed before its words are read, so `user` and `assistant` can name a fact. A message
with no word and no value reads the newest row the calling chat stored as just said and keeps
every other row, as `Actually forget it` does; a call with no message still keeps no row.

Replay of every distinct string of `docs/readings/` holding a forget verb (1,706) through the old
and new reader, over seven rows holding the string's value (six other chats' rows and one of the
calling chat), with and without the calling chat's row: 96 cases changed. Each recorded draw
message of the n1, n1v, x6, f1 and `forget-value-repeats.md` flows is unchanged. The changed
messages are the audit probes above (each now keeps the rows it does not name, and `Forget my user
id 7319.` lists the user id row), the probes `Forget that.` and `Forget it, please.`, bare verbs,
and prose that holds `user`. No message keeps fewer rows except through `user` naming a row.
Script `replay.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot9/`.
A word in a clause asking to keep is read in [forget-keep-clause.md](forget-keep-clause.md).
