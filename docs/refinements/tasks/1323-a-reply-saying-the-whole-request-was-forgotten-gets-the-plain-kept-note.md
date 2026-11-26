# A reply saying the whole request was forgotten gets the plain kept note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`false_sentence` (`forget_kept_sentence.py`) marks a reply sentence only when it names a kept row
by a word both sides of the row say or by its digits. A sentence that names the whole request by a
reference, such as `I've deleted those details from my memory.`, `I've removed that information
from my memory.` or `The requested information has been removed from my memory.`, names no row, so
the kept note keeps its plain head under a reply that says the opposite. On the
[draws](../../readings/forget-result-texts.md#a-reply-saying-a-kept-row-was-forgotten-2026-11-24)
this form was 6 of the 24 recorded false delete claims, 5 of the 15 on the new base and 1 of the 8
on the candidate.

What would close it: a reading of such a sentence that marks it only when the person's message
named a kept row to forget, so a reply about a request the turn did complete is never marked,
replayed over the recorded replies of those readings with no true reply marked, and written
without a list of reference words that a later form would extend. The reading has to look at the whole reply,
not one clause: `I've deleted those details from my memory, except the phone.` is true, and the
clause before `except` names no row. One form that needs no reference words: mark a sentence
stating a removal in a done form when no sentence of the reply names a kept or deleted row and
`forget_words` (`forget_keep_named.py`) of the message names a kept row, which `kept_claim` then
needs the message for.

## History

- 2026-11-24: filed with the check that marks a reply naming a kept row as forgotten.
- 2026-11-25: premise checked over the recorded replies of 2026-11-24 after the reading of a kept
  row named after a word for and: 6 of the 24 false claims still name no row, 5 of them on
  `Forget the locker 4242 including the phone.` (`those details` twice, `that information`, `The
  requested information`, `those`). Not built inside the slot's time box; the remedy above is
  written down.
- 2026-11-26: meets the bar of the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): it rests on the recorded replies of live draws, 5 of the 6 on `Forget the locker 4242 including the phone.`, and its remedy is a reply check that reads the message through `forget_words` as it stands, with no list of reference words.
