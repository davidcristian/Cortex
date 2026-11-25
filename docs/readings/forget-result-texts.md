# Readings: what the cortex does after the forget results it reads

What the cortex calls and replies after two kinds of `forget_memories` result text: the text of
`forgot` (`forget_results.py`) after a delete that leaves another row holding a number a deleted
row held, and the texts given for rows kept under a role no reader reads (`KEPT_ALL` in
`forget_unnamed.py` and the kept branches of `forgot`). The tool is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The rig

**2026-11-24**, the `cortexn29` stack on compose defaults with the memory override: the brain
built from the tree at `361366a31`, pgvector with the default `global` scope, the CPU embedder,
and the cortex alone, started by the model host (image `cortex-model-host`, engine build b12375)
with the argv `-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 8192` on
`unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, its drafter
`mtp-gemma-4-12B-it-Q8_0.gguf` with `--spec-type draft-mtp --spec-draft-n-max 3`, no cache type
flag (the engine's 16-bit cache) and no reasoning flag. The brain reached the cortex through a
recording proxy, whose requests hold each call's text and each result the model read, since the
tool logs neither and a refused call shows no card. A candidate is the same image with a copy of
`cortex_core` holding its texts bound over the installed package. The seed turns ran once each in
their own chats on the base; their rows went into a template table and were put back under new ids
before each draw. Each draw is one turn in a new chat, every card approved. No rate was drawn.
Driver and records: `up.sh`, `draw.sh`, `swap.sh`, `count.py`, `notes.md`, `logs/*.jsonl` and
`proxy/log/requests.jsonl` in `~/.cache/cortex-run/2026-11-24/s3/`.

## The clause offering a forget of the number, 2026-11-24

The rig of the [shared number readings](forget-shared-number.md) on the tree above. Seeds
`Remember that my gym locker number is 5521.` and `Remember that the shed padlock code is also
5521.`, with the replies `I've noted that your gym locker number is 5521.` and `I've noted that the
shed padlock code is 5521.`. Each draw is `Forget my gym locker number.`.

**Rule**, written before the first launch. Base is the tree, whose result after a label first
delete ends `so that number is still remembered; a forget of the number itself would remove
them`; the candidate ends it after `so that number is still remembered`. Counted per draw from the
proxy's requests and the store: an **unasked call** (a `forget_memories` call whose text holds
`5521`, made after a result holding the changed text), whether the padlock row remains, and a
**false claim** (the reply, without `NUMBERS_LEFT_NOTE`, says the number or the padlock code was
forgotten while the padlock row remains). A draw whose first call is `5521` reaches the same first
request on both builds and is counted apart. The candidate ships when its false claims and its
unasked calls are each no more than the base's; equal counts ship it.

| Build | Draws | First call `5521` | First call a label | Unasked `5521` call | Padlock row left | False claim |
| --- | --- | --- | --- | --- | --- | --- |
| base | 8 | 7 | 1, `locker` | 1, refused | 8 | 0 |
| candidate | 8 | 6 | 2, `gym locker number` | 0 | 8 | 0 |

Every draw deleted the gym row. Each value first card listed the gym row to delete and the padlock
row under `KEPT_LINE`, so its result was the kept text of `forgot` and not the changed one. The
base's one label first draw read the clause, called `5521` and read the refusal of a later value
forget. No reply named the padlock or the number: each said the gym locker number, or "that", was
forgotten, and 15 of 16 ended with `NUMBERS_LEFT_NOTE`; the sixteenth, a candidate label first
draw, said `I've updated my memory as requested.`. The rule passes, so the clause is dropped.
The value first form was 2 of 8 on the base of 2026-11-08 and is 13 of 16 here; the forget code
changed between those dates, no separation was drawn, and no change rests on that count.

## The reason given for rows kept under an unread role, 2026-11-24

Seeds `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my phone is 0721 555 4242.`, with the replies `I've noted that your locker code is
4242.`, `I've noted that your card number is 4111 1111 1111 4242.` and `I've noted that your phone
number is 0721 555 4242.`. The messages are `Forget all 4242 apart from the card.` (a) and `Forget
the locker 4242 including the phone.` (b), 8 draws each per build.

**Rule**, written before any draw. Base is the tree as it stands, which at the draw was the tree
with the clause above dropped; the candidate is the same tree with three texts that each state one
reason true for every reason a row is kept and suggest no further forget call:

- `KEPT_ALL`: `nothing was forgotten: the user's message was not read as meaning any remembered
  exchange holding that value, so each was kept`
- `forgot`, a text holding no digit: `forgot {removed} remembered exchanges; {kept} other
  remembered exchanges contain that text, and the user's message was not read as meaning them, so
  they were kept`
- `forgot`, a value: `forgot {removed} remembered exchanges; {kept} other remembered exchanges
  hold the same value, and the user's message was not read as meaning them, so they were kept and
  the value is still remembered`

After each turn the store is read, and each reply is counted for a **false delete claim** (it says
a row was forgotten that the store still holds) and an **untrue reason** (it says the message did
not name a kept row, or that the person asked to keep it, for the locker or phone of a or the phone
of b). The candidate ships when its false delete claims over its 16 draws are no more than the
base's; equal counts ship it. The untrue reasons are reported and do not decide. Written after the
base rows and before any candidate reply was read: a reply that says a row the store holds, or the
whole of what the message asked (`that`, `those details`), was forgotten, removed or deleted is a
false delete claim, and one saying only that the request was processed is not.

| Build | Message | Draws | Locker row deleted | Phone row left | False delete claims | Untrue reasons |
| --- | --- | --- | --- | --- | --- | --- |
| base | a | 8 | 1 | 8 | 7 | 1 |
| base | b | 8 | 8 | 8 | 5 | 0 |
| candidate | a | 8 | 4 | 8 | 6 | 0 |
| candidate | b | 8 | 8 | 8 | 6 | 0 |

No draw deleted the card. Message a drew two to six calls per draw, by label (`locker code`,
`phone`), by value (`0721 555 4242`) or by the stored request (`Remember that my locker code is
4242.`); only a call holding the locker's request or the whole `locker code is 4242` deleted the
locker. Message b deleted the locker in every draw, by `4242` in 7 per build (its card listed the
phone under `KEPT_LINE` and the card under `INSIDE_LINE`, and its result was the value text of
`forgot`) or by `locker`, and every call for the phone returned `KEPT_ALL`. No draw reached the
text of `forgot` for a text holding no digit. The base's untrue reason
said the card and the phone `were not specified to be removed`. The two draws that read correctly
on the candidate said the locker was removed and that the card remains, and that the phone could
not be removed. Every reply on both builds ended with `KEPT_NOTE` listing the rows kept, and each
draw that deleted nothing also ended with the note that nothing was forgotten in the turn. The rule
passes, 12 against 12, so the three texts ship.

## A reply saying a kept row was forgotten, 2026-11-24

The rig above, with the brain image built from the working tree at `87cff707c` (after the keep
clause reader that keeps an item after a clause any keep reading keeps) and its `cortex_core`
bound over: the base binds that commit's copy, the candidate the copy holding the check
(`false_sentence` in `forget_kept_sentence.py`). The model host wrote the same argv as above. The
seeds and messages a and b are those of the section above, 8 draws each per build.

**Rule**, written in the task file before any draw: the check ships when the candidate marks no
reply that the reading rule of the section above counts as true, and its false delete claims left
unmarked are fewer than the base's false delete claims. A null, no mark, leaves the plain note.

**Replay first.** The 32 recorded replies of the section above, each with the kept rows its
`KEPT_NOTE` listed and the rows its draw deleted: the check marks 7 of the 24 false delete claims
and none of the 8 others. It reads only the object of a stated removal: the words after an active
form such as `I've removed`, up to a joining word (a conjunction or preposition such as `and`,
`from` or `to`), a comma or a quote mark, and the subject before a passive form such as `has been
removed` when no joining word or quote mark comes before it. So `I've deleted your locker code and
saved your card.` and a quote of the person's message are not marked. The 7 marked claims name a
kept locker row first, on draws that deleted nothing. Of the 17 it leaves, 11 name the kept row
only after a joining word, as `the locker code and phone number` names the phone, and 6 name no
row: `that information`, `those details`, `the requested information`, `those`, and `the other
information` after a keep clause.

| Build | Message | Draws | Locker row deleted | Phone row left | False delete claims | Marked | True replies marked |
| --- | --- | --- | --- | --- | --- | --- | --- |
| base | a | 8 | 5 | 8 | 8 | 0 | 0 |
| base | b | 8 | 8 | 8 | 7 | 0 | 0 |
| candidate | a | 8 | 4 | 8 | 6 | 6 | 0 |
| candidate | b | 8 | 8 | 8 | 2 | 1 | 0 |

The `Marked` column counts the notes each build showed. Read offline over the same replies, the
check in the tree marks 4 of candidate a's 6 false claims, none of candidate b's 2 and 3 of the
base's 15, and no true reply; each claim it leaves names the phone after a joining word, or names
no row. The two candidate a replies saying only that the locker code was removed, on draws that
deleted it, kept the plain note, and so did candidate b draw 4, which said the locker code was
removed and the phone number could not be. The one unmarked false claim is `I've removed those from
my memory.`. The note is written after the reply of a one turn chat, and the model's requests on
the two builds hold the same system text, tool list and sampler settings, with result texts from
unchanged code. They differ in the recalled rows' ages, up to 5 minutes on the base and 5 to 11 on
the candidate, drawn later over the same seed rows, and for message b in the rows' order, another
in 4 of 8 candidate draws against 1 of 8 base draws. So the change cannot move the count of false
claims; the candidate's 8 against the base's 15 is the model's spread over those prompts (5 of the
candidate b replies said only that the request was processed). The rule passes: no true reply
marked, and 1 false claim unmarked against 15 in the notes shown, 4 offline. The head says the sentence is wrong about at least
one of the rows below, because a sentence can name another kept row as kept, as candidate a draw 8
did of the card. Rows: `logs/base.rows.jsonl`, `logs/cand.rows.jsonl`, `logs/base.offline.jsonl`
and `replay-s3.jsonl` in `~/.cache/cortex-run/2026-11-24/s7/`; the offline counts of the check in
the tree in `recorded-new.jsonl` and `live-new.jsonl` in `~/.cache/cortex-run/2026-11-24/f9/`.

## A removal continued past a word for and, 2026-11-25

`false_sentence` now continues a removal's object past a word for and (the English cell of the
`and` row of `forget_forms.py`) when the word right after it names a kept or deleted row (a word
both sides of the row say, or a digit run), every naming word up to the next joining word or comma
names one too, and no word that opens a clause, such as `kept` or `still`, ends the clause there.
Near misses written first as tests: `I've deleted your locker code and phone stays.`, `... and
phone is kept.`, `... and phone remains saved.`, `... and noted your phone.` and `I've removed the
locker code and the phone` are not marked.

Replayed offline through the check before and after the change (`replay.sh` in
`~/.cache/cortex-run/2026-11-25/f4/r1333/`, the inputs of the section above):

| Set | Replies | False delete claims | Marked before | Marked after | True replies marked |
| --- | --- | --- | --- | --- | --- |
| recorded replies of the section above | 32 | 24 | 7 | 13 | 0 and 0 |
| live draws of the section above | 32 | not counted by hand | 7 | 12 | none newly |
| the audit's sentences (`truesent.py`) | 19 | 2 | 0 | 1 | 0 of 17 and 0 of 17 |

Each newly marked live reply says the kept phone number was removed, as `I've removed the locker
code and phone number from my memory, while keeping your card number.`. Of the 11 recorded claims
naming the kept row only after a joining word, 6 are now marked. The 5 left keep the plain note,
which names every kept row: 3 name the phone after `and the` or `and your` (`your` is no word of
the `the or my` row, and reading `and the` would also mark the audit's `I've removed the locker
code and the card`, a sentence its set counts as true), 1 after `references to`, and 1 in the
subject of a passive form after `and`.
