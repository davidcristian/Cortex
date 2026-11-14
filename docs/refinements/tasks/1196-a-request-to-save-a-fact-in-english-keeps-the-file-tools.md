# A request to save a fact in English keeps the file tools

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-14

`unasked_sidecar_tools` and `unasked_tools` (`unasked_tools.py`) withhold the file and side effect
tools only on a message that `asks_kept` or `asks_kept_alone` (`memory_request.py`) reads as a
request to remember. `Save my phone number 0721 555 019.` is read by `stores_fact`
(`fact_request.py`) and not by `asks_kept`, so every tool stays listed. In 2 of 8 store turns
drawn on 2026-11-14 the model called `list_allowed_directories`, a file result left the turn out
of memory, and no phone row was stored. One reply showed the unkept note; the other replied `I've
saved your phone number: 0721 555 019.` with no note
([readings](../../readings/forget-refusal-stated-fact.md#the-store-turn-and-the-asked-forget-what-was-drawn)).

## What to do

1. Write tests first: the five English store requests of
   [task 1184](1184-a-request-to-save-or-store-a-fact-in-english-keeps-the-forget-tool.md) withhold
   the sidecar tools; `Save the report to my notes folder.` and `Store this file in /tmp.` keep them.
2. Read `stores_fact` beside `asks_kept` in the two tool readers, and leave `asks_kept` unchanged,
   since it also decides what is stored.
3. Check why the reply `I've saved your phone number` showed no unkept note when the turn stored
   nothing, and replay every recorded message through both builds.
4. Draw the store turn on a side brain and count phone rows stored.

## History

- 2026-11-14: filed when the forget refusal read English store requests and the store turn draws
  lost the row to a file tool call on both builds.
