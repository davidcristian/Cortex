# The first fire note is English in every language

**Status:** done 2026-11-11
**Area:** scheduling
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)

`FIRST_FIRE_NOTE` (`brain/packages/core/src/cortex_core/schedule_first_fire.py`) names the first
fire of a repeat that fires before the day the person's message names. It has English text only,
so under the French reply to `Souviens-toi que le code de mon casier est 4417 et rappelle-moi
demain à 9h de vider le casier.` it shows in English
([readings](../../readings/schedule-daily-first-fire.md)). Its day word (`today`, `tomorrow`,
`in N days`) is stored in English on `TaintLedger.early_first_fire`, so a translation also needs
the day count there instead of the word.

## Proposed wording

For the maintainer to review, in the form of address of the other translated notes. `{when}` is
the day word, `{day}` the weekday from `_DAY_NAMES` in `schedule_weekday.py`.

| Language | Note | Day words |
| --- | --- | --- |
| fr | `(Un rappel créé ici se déclenche pour la première fois {when}, {day} {date} à {time}. Demandez à changer son premier jour si vous pensiez à un jour plus tard.)` | `aujourd'hui`, `demain`, `dans N jours` |
| de | `(Eine hier erstellte Erinnerung kommt zum ersten Mal {when}, {day}, {date} um {time}. Bitten Sie um einen anderen ersten Tag, wenn Sie einen späteren meinten.)` | `heute`, `morgen`, `in N Tagen` |
| es | `(Un recordatorio creado aquí suena por primera vez {when}, {day} {date} a {las} {time}. Pide cambiar su primer día si te referías a uno posterior.)` | `hoy`, `mañana`, `dentro de N días` |
| ro | `(Un memento creat aici sună prima dată {when}, {day}, {date} la ora {time}. Cere să-i fie schimbată prima zi dacă te gândeai la una mai târzie.)` | `azi`, `mâine`, `peste N zile` |

## What to do

1. Have the maintainer review the wording above.
2. Store the day count rather than the English word, add `FIRST_FIRE_NOTES` beside the English
   constant, and pick it with `in_language`, as `WEEKDAY_OFF_NOTES` is picked.
3. Draw the French row of the readings twice and check the note is French.

## History

- 2026-11-10: filed from the first fire note, which was built with English text only.
- 2026-11-11: done. `TaintLedger.early_first_fire` holds the day count, and the handoff codec
  reads the English day word of an older record as its count. `FIRST_FIRE_NOTES` and `day_word`
  write the note and its day words in the language `message_language` picks. The wording follows
  `STORED_TIME_NOTES`: `créé ou modifié ici` and its forms for "set or changed in this turn", the
  Spanish `el` before the weekday and `la` before one o'clock, and German `meldet sich` for
  "fires". One French draw that stored a daily rule first firing today showed the French note
  ([readings](../../readings/schedule-daily-first-fire.md#the-note-in-the-messages-language-2026-11-11)).
