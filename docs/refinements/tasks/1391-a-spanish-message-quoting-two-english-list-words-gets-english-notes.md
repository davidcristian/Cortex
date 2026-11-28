# A Spanish message quoting two English list words gets English notes

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-28

`message_language` (`note_language.py`) reads `Quiero un recordatorio a las 9 para decirle «tak
for i går» a Søren.` as English. The Spanish list counts `las` and `para`, and the quoted Danish
`tak for i går` holds `for` and `i`, which the English list counts. The tie goes to English,
since the message holds no Spanish letter, so every closing note of such a turn is English. The
form was found among the generated messages of
[R-1057](1057-a-romanian-reminder-reply-holds-a-broken-word.md): 48 of 3,456 Spanish messages,
all holding that quote ([readings](../../readings/cortex-sampling-broken-words.md#the-replay-and-the-generated-replies)).

## What to do

1. Find a reading that leaves quoted words out of the pick for the notes only, since
   `forget_language` reads the same lists and the forget message readers are frozen
   ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7).
2. Replay the recorded messages through the old and new pick and state every change, or decline
   the task when quoted words are needed to read a message that is only a quote.

## History

- 2026-11-28: filed from [R-1057](1057-a-romanian-reminder-reply-holds-a-broken-word.md), whose
  generated Spanish messages with this quote read as English.
