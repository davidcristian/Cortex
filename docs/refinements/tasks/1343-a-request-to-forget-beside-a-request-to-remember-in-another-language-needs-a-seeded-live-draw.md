# A request to forget beside a request to remember in another language needs a seeded live draw

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`reads_call_words` (`forget_unsaid.py`) reads no call words on a message `asks_to_forget` reads.
So on `Vergiss meine alte Karte und merk dir die neue: 5500 0000 0000 1234.`, `Lösch meine Karte.
Merk dir, dass ich eine neue habe.`, `Oublie ma carte et retiens que la nouvelle finit par 1234.`,
`Olvida mi tarjeta y recuerda que la nueva termina en 1234.` and `Uită cardul meu și ține minte că
cel nou se termină în 1234.` the call `4111 1111 1111 4242`, the stored value, is no longer
refused and meets the card. The replay over ten such messages, both families, the generator and
the recorded calls is in
[forget-refusal-call-words.md](../../readings/forget-refusal-call-words.md#a-request-to-forget-beside-it-2026-11-25):
refused calls on asked rows went from 10 of 18 to 0, and no recorded call that lost a row runs. A
change to what a tool refusal lets through is drawn live with the prior state seeded before it
ships; no draw has been made.

## What to do

1. A seeded live draw: the first message above after a stored card, and `Merk dir, dass mein Hund
   Bello heißt.` after `Merk dir, dass mein Hund Rex heißt.`, every card approved, counting old
   rows deleted and new facts stored. Write the pass rule into the readings before the first
   launch: no row the message asks to keep deleted, and the Bello draws no worse than the counted
   run of the same reading.

## History

- 2026-11-25: filed by the audit of the night's forget commits, from a probe of the shipped check.
- 2026-11-25: `reads_call_words` reads no call words on a message `asks_to_forget` reads, with the
  five forms as tests and the replay counts in the readings; the seeded live draw is left open.
