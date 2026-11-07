# A repeat word in the reminder text hides the daily note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-07

`names_repeat` (`schedule_daily.py`) reads a repeat in any clause that states one, so a repeat
word inside the reminder's own text counts as saying the reminder repeats. `limit_notes` then
leaves out `DAILY_STORED_NOTE` over a daily item although the reply describes one reminder at a
time. Each of these returns true:

- `I'll remind you at 8 to take your daily vitamins.`
- `I'll remind you at 8 to take the pill you take every morning.`
- `Ich erinnere dich um 8 Uhr an deine täglichen Tabletten.`
- `Je te rappellerai à 8h de faire ton footing quotidien.`
- `Te recordaré a las 8 tu paseo diario.`
- `Îți voi aminti la 8 de plimbarea zilnică.`

These two state the repeat and must stay true: `I've set a daily reminder for 8:00.` and
`Ich habe bereits einen täglichen Reminder für „Wäsche“ um 17:30 Uhr für dich eingerichtet.`
None of the 318 distinct replies recorded on 2026-11-07 by 07:25 has the form: each of the 13
that `names_repeat` reads as naming a repeat states it about the reminder.

## What to do

1. Write the replies above as tests first, beside `test_schedule_daily.py`.
2. Read an adjective form (`daily`, `täglich`, `quotidien`, `diario`, `zilnic`) as a repeat only
   beside a word for the reminder (`reminder`, `Erinnerung`, `rappel`, `recordatorio`,
   `memento`), or leave out a repeat form that follows the reminder text's verb (`to take`,
   `an`, `de`). Question which reading fails toward showing the note before choosing.
3. Replay every reply recorded in the run's scratch directory through the old and new reader.

## History

- 2026-11-07: filed by the review of the reader that reads a repeat only where a reply states it.
