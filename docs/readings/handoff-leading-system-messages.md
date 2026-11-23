# Readings: three leading system messages on a handoff

What a handoff to the deep pick sends when its turn has a recalled memory and a recap, which
layout the adapter chose for the deep server, and whether the deep reply used what those messages
held. The decision it supports is [ADR-0071](../adr/ADR-0071-leading-system-messages.md), whose
template rows are in [system message templates](system-message-templates.md).

## The stack (2026-11-23)

24 GB card (24,463 MiB) beside the desktop's apps, engine build b12375 from the
`cortex-model-host` image, a brain built from the tree, Redis, the memory override's Postgres and
CPU embedder, and the model host, all from the repo's compose files. Beside the models mount, six
variables were named: `CORTEX_ESCALATION=1`, `CORTEX_MODELHOST_BACKEND=supervisor`,
`CORTEX_MODEL_FILE_BRAIN=unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf`,
`CORTEX_SWAP_BRAIN_VRAM_MIB=16991`, `CORTEX_HISTORY_CHAR_BUDGET=600`, so that a chat of four turns
folds, and `CORTEX_MEMORY_RECALL_AUDIT=1`, which writes one `memory.recall` log line per recall.
Every other setting was on its compose default: recall `judge`, scope `global`, no deep drafter.

The deep server started as `llama-server --model
/models/unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf --host 0.0.0.0 --port 8081 -ngl 99
--ctx-size 16384 --parallel 1 --jinja --cache-ram 0 --cache-type-k q8_0 --cache-type-v q8_0`, with
no drafter flag. The brain sent the default effort: `reasoning effort sent` with `sent_as=medium`.
The cortex was gemma-4-12B with its MTP drafter at 16384, as the compose files start it.

## The chat

Two runs, each on a fresh stack, each one chat of four turns: a code word to keep (`heron-42`); a
room for a review (`Lindgren 4B`) with a request for about 150 words on room names; about 150
words on tides; and a task the cortex hands over with `escalate_to_brain`, a two-sentence
reminder naming the code word and the room. The window kept the fourth turn alone, so the first
three reached each request of that turn only as the recap and as recalled memory. Run 2 asked for
a brief that does not repeat either value, and the driver deleted every memory row holding the
room just before the fourth turn, so in run 2 the room was in the recap and nowhere else the deep
phase read. The pass rule of each run was written before its launch.

| reading | run 1 | run 2 |
| --- | --- | --- |
| the cortex's brief | names both values | names neither: "the user's code word and the room location found in the conversation history" |
| memory rows deleted before the fourth turn | none | 1, the room's row |
| the recap while the deep tier served | both values, `covers` 6 | both values, `covers` 6 |
| the cortex's probe lines | `system_messages=2` at the third turn (preamble and recap; recall kept nothing), `system_messages=3` at the fourth, `delivers=True` both | the same |
| the deep phase's recall | pool 4, 3 hits: the code word's row, the room's row, the cortex's hand-over row of this turn | pool 3, 2 hits: the code word's row, the cortex's hand-over row of this turn |
| the deep probe line | `endpoint=http://model-host:8081 system_messages=3 delivers=True` | the same |
| deep requests, prompt and decoded tokens | recall judge 416 and 30; reply 1,701 and 79 | recall judge 348 and 22; reply 1,489 and 259 |
| the deep reply | "Reminder: Friday's review is in Lindgren 4B. Don't forget your code word: heron-42." | two sentences naming `heron-42` and `Lindgren 4B` |
| card's floor before and after | 2,409 and 2,409 MiB | 2,409 and 2,409 MiB |
| highest reading above the floor | 15,957 MiB | 15,955 MiB |
| the fit check's `free_mib` | 21,729 | 21,729 |
| warnings or errors in the brain's log | 0 | 0 |

- **The layout.** `delivers=True` means the adapter sent the three system messages unchanged,
  and the deep template renders them in order as one system block, the render of 2026-11-21 in
  [model swap](model-swap.md#a-handoff-on-the-deep-pick). So the deep server received the
  template's merge, not the adapter's join.
- **What the reply used.** In run 2 the room was in no memory row, not in the window and not in
  the brief, so the deep reply took it from the recap, the third of the three messages. The code
  word was in the recap and in the recalled row of the first turn. Run 1 shows less, since its
  brief named both values and the deep context ends with the brief.
- **The recap.** The cortex wrote it at the fourth turn's start, covering the first six
  messages, which is the deep phase's boundary too, so the deep phase used it as stored and did
  not fold again.
- **The rest of the handoff** read as in [model swap](model-swap.md#a-handoff-on-the-deep-pick):
  the cortex `stopped` and the deep tier `ready` while it served, then the deep tier `stopped`, a
  new cortex process `ready`, both handoff keys gone from Redis and all 9 messages in the
  session's list.
- **The hand-over row.** In both runs the deep phase's recall returned the row the cortex
  recorded for this same turn: the user's request, the `escalate_to_brain` run and the cortex's
  sentence about the handoff. Its similarity to the query was the highest of the pool, 0.935 and
  0.917, and the judge kept it in last place. The deep context leaves out the cortex's reply to
  this turn ([ADR-0030](../adr/ADR-0030-brain-handoff.md) step 4); this row puts it back
  ([R-1301](../refinements/tasks/1301-the-deep-phase-recalls-the-hand-over-row-its-own-turn-wrote.md)).
- In run 2 the cortex called `forget_memories` on the first turn's message, and the typed refusal
  answered it; the reply was `OK` and the row was stored.

Method: `bash ~/.cache/cortex-run/2026-11-23/s1/build.sh`, then `run.sh mem` and
`run.sh split split`, compose project `cortexn28`, with `teardown.sh` after each run. A run's
record is `logs/<label>/live.txt` there, beside `turns.jsonl`, `brain.log`, `host.log` and
`smi.txt`; `notes.md` has the pass rules, written before each launch.
