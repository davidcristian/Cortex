# A request to save a fact in English keeps the file tools

**Status:** done 2026-11-15
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

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
- 2026-11-15: done, with a narrower reader than step 2 names. `stores_fact` alone also reads
  `Save my draft 2.`, `Record my screen for 10 seconds.` and `Keep my volume at 40.`, where the
  same verb saves a file or asks for an action. Both tool readers read `_stores_a_value`
  (`unasked_tools.py`) instead: `fact_stored` (`fact_request.py`) reads the message, and the fact
  is a statement with `is` or its value follows `number`, `code`, `PIN`, `password`, `passcode`,
  `address` or `birthday`. Any other object of a store verb keeps every tool. `unasked_tools`
  searches only the fact for a second action, since `actions_asked` reads the store verb itself as
  one. The start build stored the phone row in 9 of 12 draws; the replay and the fix's draws are in
  the [readings](../../readings/store-request-unasked-tools.md). Step 3: `claims_kept` reads
  `saved` only before `in memory`, and `unkept_note_due` reads the request with `asks_kept`, so the
  reply showed no note in 3 of 3 start build draws that stored nothing
  ([task 1202](1202-a-store-request-whose-turn-stores-nothing-shows-no-note.md)).
