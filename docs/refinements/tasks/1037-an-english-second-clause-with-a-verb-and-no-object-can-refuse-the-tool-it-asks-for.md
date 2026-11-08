# An English second clause with a verb and no object can refuse the tool it asks for

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-08

`actions_asked` (`memory_request.py`) reads a clause beside an English request to remember as an
asked action only when its first word is followed by an object: `me`, `us`, `at me`, `to me`, a
pronoun or a determiner. A clause whose verb has no object, such as `and ring at 9` or `and shout
at 9`, is not read, so `unasked_tools` still refuses both `schedule_task` and `set_volume` on
`Remember that I have the dentist tomorrow and ring at 9.` when no reminder word names it. That is
the unsafe side of this reader.

## What to do

1. Write the message above and two near misses as tests first: facts with a verb and no object
   after `and` (`Remember that I swim and run on Mondays.`), which keep the refusal today.
2. Count over the replay corpus of
   [the second clause readings](../../readings/side-effect-tools-second-clause.md) how many
   requests to remember a clause of a verb and a time (`at 9`, `in 5 minutes`) would change, and
   keep both tools when the reading is unsure.

## History

- 2026-11-08: filed by the slot that kept both tools beside an English clause of a verb and its
  object; reproduced at unit level, no turn sent.
