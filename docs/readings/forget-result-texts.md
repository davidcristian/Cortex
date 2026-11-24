# Readings: what the cortex does after the forget results it reads

What the cortex calls and replies after a `forget_memories` result text: the text of `forgot`
(`forget_results.py`) after a delete that leaves another row holding a number a deleted row held.
The tool is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

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
