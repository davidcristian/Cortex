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
