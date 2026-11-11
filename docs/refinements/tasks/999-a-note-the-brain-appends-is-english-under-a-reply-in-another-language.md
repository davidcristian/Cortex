# A note the brain appends is English under a reply in another language

**Status:** done 2026-11-11
**Area:** cross-cutting
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Every note `limit_notes` in `closing_notes.py` appends is a fixed English sentence, and the readers
that decide whether one is due (`names_time_of_day`, `claims_scheduled`, `claims_yearly`,
`claims_kept`, `names_removal` and the rest) read English forms. On 2026-11-07 the `cortexn15`
stack answered `Recuérdame cada año el 12 de octubre el cumpleaños de Ana.` in Spanish with no time
of day, and the reply ended with the English
`(The reminder set or changed in this turn is at 09:00. ...)`
([readings](../../readings/overlay-language-and-locale-flows.md)). The note was due, since the
reply named no time; only its language was wrong.

A reader that misses a non-English form fails one of two ways. A reader that adds a note when it
finds no form, such as `names_time_of_day`, adds a note the reply did not need: that one now reads
`17h30` and `9 Uhr`, but not a Spanish `a las 10` or a Romanian `la ora 14` without minutes. A
reader that adds a note when it finds a claim, such as `claims_scheduled`, misses a false claim in
another language and adds nothing.

## What to do

1. List, per note, the reader that decides it and whether a missed form adds a note or drops one.
   The dropped notes are the defects that matter: a false claim in another language that the
   person is never told about. Draw rows for the two most used, the unscheduled claim and the
   unkept claim, in four languages before writing any reader.
2. For the note text, the brain does not know the reply's language. Options to compare: a short
   note in the language the reply most likely uses, read from the person's message with a small
   word list per language, or one fixed form the model is asked to restate. Write the choice as
   an ADR before building it.

## History

- 2026-11-07: filed from the language and locale flows on the shared stack, where the stored time
  note read `17h30` and `10h00` as no time of day; that reader was widened the same night.
- 2026-11-07: a French turn made only a `list_scheduled` call and replied `D'accord, j'ai bien
  noté votre rappel [...] à 17h30.`, a false claim with no note, since `claims_scheduled` reads
  English forms ([readings](../../readings/schedule-one-time-in-other-languages.md#results)).
- 2026-11-08: step 1 done: every note `limit_notes` appends, its reader and what a missed form does
  are in the [readings](../../readings/closing-note-language.md); the readers that drop a note are
  task R-1049. Step 2 decided in [ADR-0076](../../adr/ADR-0076-closing-note-language.md), the
  language of the person's message, and built for `STORED_TIME_NOTE`, `DAILY_STORED_NOTE` and
  `NUMBERS_LEFT_NOTE`. Left open for the other notes' mappings.
- 2026-11-08: the second audit of the night found that `ONCE_STORED_NOTE`, added the same night
  for a one-time item stored after the weekly refusal, is English too, and that refusal reads
  French, German, Spanish and Romanian weekdays. It needs its mapping like the others.
- 2026-11-10: the compound request flows ended a German reply with the English
  `UNKEPT_CLAIM_NOTE`, and showed `STORED_TIME_NOTE` after French replies naming `demain à 9h de
  vider` and `**9h00**`, which `names_time_of_day` reads as no time
  ([readings](../../readings/overlay-compound-request-flows.md#counts)).
- 2026-11-11: done. The [readings](../../readings/closing-note-language.md#the-notes-and-their-readers-2026-11-11)
  table now names each note's own language. Twelve more notes got a mapping beside their English
  constant (`UNSCHEDULED_CLAIM_NOTES`, `UNKEPT_CLAIM_NOTES`, `REPLY_CAPPED_NOTES` and the rest),
  tested in `test_closing_note_languages.py`, and the three that fill words into their text
  write those words in the same language. The readers that drop a note are R-1049.
