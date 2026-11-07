# An English request to remember with a second clause can refuse the tool it asks for

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-07

`unasked_tools` (`unasked_tools.py`) leaves `schedule_task` and `set_volume` out of an English
request to remember unless `_REMINDER` or `_SOUND` names its use. A second clause that asks for
the tool in other words loses it: `Remember that I have the dentist tomorrow and give me a shout
at 9.` and `Remember that I like it like this and crank up the music.` both refuse the tool they
ask for. In French, German, Spanish and Romanian the refusal now applies only when no comma,
semicolon, conjunction or second sentence follows the request to remember. English keeps its
word lists, since the English tests require refusing both tools on `Remember that the remote is
under the couch, and turn the heating down.`

## What to do

1. Write the two messages above as tests first.
2. Compare the clause rule of the other four languages with keeping the tools whenever a second
   clause holds a time of day or a first person object (`me`), and count how many of the
   recorded requests to remember each rule changes.
3. A reader that controls a refused tool fails toward keeping the tool, so prefer the rule that
   keeps it on more of the messages that ask for it.

## History

- 2026-11-07: filed by the slot that limited the refusal of those tools in four more languages
  to a request to remember with one clause.
