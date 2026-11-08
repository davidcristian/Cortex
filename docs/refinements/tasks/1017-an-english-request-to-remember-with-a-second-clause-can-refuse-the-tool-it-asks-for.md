# An English request to remember with a second clause can refuse the tool it asks for

**Status:** done 2026-11-08
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)

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
2. Neither rule tried on 2026-11-07 fits English. The clause rule of the other four languages
   fails 43 of the 532 tests of `test_unasked_tools.py` and `test_unasked_tools_languages.py`.
   Keeping both tools whenever a time of day or `me` follows the request changes 62 of the 516
   distinct English requests to remember among the night's turn records, the brain's test
   strings and the readings records, among them `Note that my mother's birthday is on 12 May.`,
   the form that stored a yearly reminder nobody asked for, and still refuses `set_volume` on the
   music message above.
3. Try a reading of a second imperative clause addressed to the assistant (`and` or a comma, then
   a verb with `me` or `the music`), count its changes over the same strings, and keep the tool
   when the reading is unsure: a reader that controls a refused tool fails toward keeping it.

## History

- 2026-11-07: filed by the slot that limited the refusal of those tools in four more languages
  to a request to remember with one clause.
- 2026-11-08: done. `actions_asked` (`memory_request.py`) reads a clause beside an English request
  that opens with a verb and its object, and `unasked_tools` keeps both tools when neither word
  list reads that clause, so both messages above keep the tool they ask for and the heating
  message keeps both. 57 of 13,291 replayed strings changed, all toward keeping; the replay,
  the near misses and six stack draws are in
  [the second clause readings](../../readings/side-effect-tools-second-clause.md). The draw of a
  weekday reminder filed
  [R-1036](1036-a-reminder-on-a-named-weekday-can-be-stored-to-repeat-every-week.md).
  A clause of a verb with no object is left open in
  [R-1037](1037-an-english-second-clause-with-a-verb-and-no-object-can-refuse-the-tool-it-asks-for.md).
