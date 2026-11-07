# A plain request to remember in another language keeps the reminder and sound tools

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-07

`unasked_tools` leaves `schedule_task` and `set_volume` out of a turn that only asks to remember,
since the cortex model called them unasked on such turns
([readings](../../readings/side-effect-tools-on-remember.md)). For French, German, Spanish and
Romanian, `asks_kept_alone` in `memory_request.py` now leaves them out only when `_SECOND_CLAUSE`
finds nothing after the request: no comma or semicolon, no second sentence and no conjunction.
These also occur inside one plain fact, so each message below kept the two tools offered, although
it asks for nothing but a fact to be kept. Each left them out before the second clause rule:

| Message | What `_SECOND_CLAUSE` reads |
| --- | --- |
| "Retiens que mon vélo est rouge et bleu." | `et` inside the fact |
| "Merke dir: mein Gewicht ist 72,5 kg." | a decimal comma |
| "Recuerda que mi código es 4512. Gracias." | a closing thanks as a second sentence |

Reproduction, unit level: `SCRATCH/slot16/probe.py` prints `old=True head=False` for each.

## What to do

1. Write the three rows as tests first, beside the second clauses the rule was built for.
2. Read a second clause only when it holds a verb or an object the reminder and sound readers can
   name, or read a comma only before a space, a conjunction only before a verb, and a second
   sentence only when it is more than a thanks. Count the forms over the recorded draw messages
   before choosing.

## History

- 2026-11-07: filed by the second audit of the night; reproduced at unit level, no turn sent.
