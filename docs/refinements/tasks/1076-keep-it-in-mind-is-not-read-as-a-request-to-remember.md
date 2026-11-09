# Keep it in mind is not read as a request to remember

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-09

`_REMEMBER` in `memory_request.py` reads `keep in mind` only with nothing between the two words, so
`asks_kept` is false for `My seat on the train is 14C, keep it in mind while we talk.`, `Keep it
in mind that my seat is 14C.` and `Keep that in mind: my seat is 14C.`. The refusals that need a
request to remember (`unasked_tools`, `unasked_sidecar_tools`, `unasked_forget`) then refuse
nothing. In 4 of 8 draws of the first message the cortex called `spawn_subagents` to store the
fact and the call ran
([readings](../../readings/chat-only-limit-words.md#the-draws-2026-11-09)).

## What to do

1. Write near misses first: `I keep it in mind.`, `Do you keep it in mind?`, `Don't keep it in
   mind.`, `keep it in mind for him` as a request about another person.
2. Read `keep it`, `keep this`, `keep that` and `keep these` before `in mind` beside the bare
   form, replay every recorded draw message in `docs/readings/` through the old and new reader,
   and keep `asks_not_kept`'s reading where both match, since a do-not-keep reader withholds when
   unsure.

## History

- 2026-11-09: filed from the eight chat-only draws in
  [the readings](../../readings/chat-only-limit-words.md#the-draws-2026-11-09).
