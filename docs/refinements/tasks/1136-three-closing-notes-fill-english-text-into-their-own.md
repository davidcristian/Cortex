# Three closing notes fill English text into their own

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-11

Every note `limit_notes` (`brain/packages/core/src/cortex_core/closing_notes.py`) appends is
written in the language `message_language` picks from the person's message, except three whose
text is filled with English words, so each needs more than a mapping beside its constant:

- `ROUNDS_SPENT_NOTE` (`turn_output.py`) names each tool the turn ran through `runs_line`, or
  `NO_TOOL_RAN` (`No tool ran.`).
- `QUOTED_STORED_NOTE` (`schedule_quoted.py`) fills in `{what}`, an English phrase naming the
  repeat and the time (`A daily reminder at 09:00`).
- `WEEKLY_STORED_NOTE` (`schedule_weekly_stored.py`) fills in `{days}`, English weekday names
  read from the stored call.

## What to do

1. For each, write the filled part in the five languages (weekday names as
   `schedule_weekday.py` already writes them for `WEEKDAY_OFF_NOTE`), then add the mapping and a
   `language` argument as `FIRST_FIRE_NOTES` does.
2. Test each through `limit_notes` in `test_closing_note_languages.py`.

## History

- 2026-11-11: filed from R-999, which gave every other note its mapping.
