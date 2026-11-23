# Readings: four cortex reply forms from early November, counted again

Three forms of a cortex reply were each drawn once or twice in early November, on older engine
builds and an older brain, and never counted, and a fourth was counted on the brain of that time.
This record counts all four again on one stack. The tasks are [R-1005](../refinements/tasks/1005-a-recall-question-that-finds-no-value-loops-in-its-thinking.md),
[R-1004](../refinements/tasks/1004-a-french-reply-can-hold-a-chinese-word.md),
[R-1057](../refinements/tasks/1057-a-romanian-reminder-reply-holds-a-broken-word.md) and
[R-995](../refinements/tasks/995-a-request-to-remember-spends-its-thinking-looking-for-a-tool-to-store-the-fact.md).
Each rule and prediction was written into the run's notes before its first launch. Counts depend
on the model file, the engine build, the sampling settings and the prompt, not on the machine.

## The stack, 2026-11-23

The brain was built from the tree and run on its compose defaults with the memory override
(pgvector, the CPU embedder, recall `judge`), escalation off and no tool sidecar. Schedules were off
for the first two counts and on (`CORTEX_SCHEDULE_BACKEND=redis`, zone `Europe/Berlin`) for the
last two, as the 2026-11-07 rig had them. The model host ran from the `cortex-model-host` image,
engine build `b12375-9d25e0014`, with the tree's model manager bound over the image's. Its argv for
the cortex tier, after the model path:

| file | argv |
| --- | --- |
| `unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, text only | `-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 8192 --model-draft .../mtp-gemma-4-12B-it-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3` |

So the KV cache is the engine's f16 and the drafter is the multi-token-prediction file beside the
model at draft length 3. The brain sends no sampling field, and `/props` reads temperature 1.0,
`top_k` 64, `top_p` 0.95, `min_p` 0.05, repeat penalty 1.0, with DRY and XTC off. The reply thinks
with no trace budget (`CORTEX_REASONING_BUDGET` -1, `CORTEX_REPLY_THINKING` on, no reply cap).

Each draw is a new chat over `Converse`, sent by the turn driver, with the store emptied first and
every card approved. A recording proxy between the brain and the cortex tier kept each chat request
and its streamed trace, so recall hits, traces and tool calls are read from the requests. Method:
`up.sh`, `draw1.sh` and `draw2.sh` draw; `summary.py`, `trace_lines.py` and `script_scan.py` read;
all in `~/.cache/cortex-run/2026-11-23/s5/`, with the rows in `logs/` and the proxy log in
`proxy/log/requests.jsonl`. The project was removed after the draws.

## A recall question that finds no value

Each draw stores `Keep in mind that my car is a blue Fiat.` and then `Remember that my gym locker
code is 5819.`, each in its own chat, and then asks `Reply with only the number: which number did I
ask you to keep?` in a third. The car exchange stands in for the older car memory the 2026-11-07
recall returned. Counted: a trace that repeats one line to the length limit, and a reply that
states a number not stored. Predicted: 0 of 5 each.

| draw | judge order (0 is the code, 1 the car) | trace characters | most copies of a line of 20 or more characters | reply |
| --- | --- | --- | --- | --- |
| 1 | `[]` | 277 and 2,588 | 1 | `I do not have a number on record that you asked me to keep.` |
| 2 | `[1]` | 6,163 | 2 | `No number was provided.` |
| 3 | `[1]` | 9,102 | 3 | `You did not ask me to keep any number; you asked me to keep in mind that your car is a blue Fiat.` |
| 4 | `[1]` | 12,888 | 5 | `No number was provided in the request to keep.` |
| 5 | `[1]` | 3,951 | 3 | `None` |

No trace repeated a line twice in a row, every request stopped on its own, and no reply stated a
number: 0 of 5 for both forms, as predicted. Draw 1 first called `forget_memories` with the text
`number`, and the typed refusal answered it. The judge saw both notes in every draw and never picked
the code, so no reply could name it, and each reply that says no number was asked for was stored
as a row ([task 1312](../refinements/tasks/1312-a-question-for-the-number-to-keep-recalls-the-car-note-and-not-the-code.md);
the recorded judge request is line 14 of the proxy log). On the request to remember, the cortex
called `forget_memories` in 5 of 5 draws and on the car request in 2 of 5; every call was refused
and every exchange was stored.

## A French reply with a Chinese word

Ten draws of `Souviens-toi que le code de mon casier à la piscine est 7731.` Counted: a reply
holding a letter whose Unicode name does not start with `LATIN`, by `script_scan.py`, and a word
that is not French, by reading. Predicted: 0 of 10.

No reply held either: 0 of 10. Every reply opened with `C'est noté` or `C'est bien noté` and
restated the code, and three addressed the person as `tu` (`ton casier`). Every exchange was stored. Seven
draws called `forget_memories` first, one of them twice, and the typed refusal answered every call.

The same script over every file in `docs/readings/` finds one French, German or Spanish model reply
with a letter outside the Latin script, the 2026-11-07 one
([forget value repeats](forget-value-repeats.md#the-candidate-draws-2026-11-07)). The other hits
are test inputs (Hebrew text, Chinese characters, a Cyrillic letter in an English link).

## A Romanian reminder reply with a broken word

Eight draws each of M1 `Amintește-mi la ora 18 să scot gunoiul pentru colectarea de luni.`, M2
`Amintește-mi mâine la ora 9 să sun la dentist.` and M3 `Amintește-mi vineri la ora 17 să plătesc
factura la curent.`, on Monday 2026-11-23. Counted, by reading: a reply holding a word that is not
Romanian; a loanword is counted apart, and a name, a number, a time, a date and a note the brain
appends are not words here. The stored item's text is read the same way. Predicted: 0 of 8 for M1
and 0 of 16 for M2 and M3.

| message | replies with a broken word | the words | loanwords | items with a broken word |
| --- | --- | --- | --- | --- |
| M1 | 2 of 8 | `Scote` twice, quoting the item | `reminder` once | 4 of 8, each `Scote` |
| M2 | 4 of 8 | `aminteștetea`, `amânterea`, `amântarea`, `uninel` | none | 0 of 8 |
| M3 | 2 of 8 | `amenintire`; `unटेल przypomínání` | none | 0 of 8 |

`Scote` stands for `Scoate` (take out), and the others stand for `amintirea`, `un memento` or
`o amintire` (a reminder). The last M3 reply holds Devanagari letters and a word that mixes the
Polish `przypomnienie` and the Czech `připomínání`, both meaning a reminder, and `script_scan.py`
flags only that reply. Every draw called `schedule_task` once and stored one item
at the time asked; one M1 item was stored as daily, and the brain's note said so. The prediction
failed: 8 of 24 replies hold a broken word, and 4 of 24 items, which the person reads when the
reminder fires.

## The search for a store tool, counted again

Rows R01 to R15 of [the search record](remember-request-tool-search.md#rows-and-the-rule-2026-11-07),
each drawn once on the schedules-on brain, counted as that record defines its items. A search name
is found by `search995.py` (an identifier in the trace, in backticks or holding an underscore, that
is not in the request's tool list and holds one of the record's eight stems) and read by hand.
Predicted: a search in at least 10 of 15.

| Search | Median trace characters | Chat only | Forget, from events or cards | Forget, from the requests | Stored |
| --- | --- | --- | --- | --- | --- |
| 15 of 15 | 2,819 | 0 of 15 | 0 of 15 | 8 of 15 | 15 of 15 |

The prediction held: every trace looked for a tool, most often `remember_memory`,
`remember_memories`, `save_memory`, `add_memory` or a bare `remember`. The 2026-11-07 base read 15
of 15 with a median of 3,025 and 3,626 characters on its two runs.

The forget count from events reads 0 of 15, as on 2026-11-07, but a refused call sends no
`ToolActivity` event and shows no card. The requests show that 8 of 15 draws called
`forget_memories` and that the typed refusal answered each one, so a forget count read from events
alone misses every refused call. With the counts of the first two sections, the requests show the
call on 22 of 35 requests to remember tonight, every one refused and every fact stored.
