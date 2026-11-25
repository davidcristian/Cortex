# A request to forget beside a request to remember in another language has its stored value call refused

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`forget_unsaid` (`forget_unsaid.py`) refuses a forget call naming a word the message lacks on
every message `asks_kept_other` reads, with no forget opened in the last two exchanges, also when
the message itself asks to forget with a forget verb. `Vergiss meine alte Karte und merk dir die
neue: 5500 0000 0000 1234.`, `Lösch meine Karte. Merk dir, dass ich eine neue habe.`, `Oublie ma
carte et retiens que la nouvelle finit par 1234.`, `Olvida mi tarjeta y recuerda que la nueva
termina en 1234.` and `Uită cardul meu și ține minte că cel nou se termină în 1234.` each refuse
the call `4111 1111 1111 4242`, the stored value, and run the call naming the noun. The row is
kept, which is the safe direction, but the person asked to forget it. None of the 198 and 194
refused calls of the two families in
[forget-refusal-call-words.md](../../readings/forget-refusal-call-words.md) is on such a message:
no message of either family names forgetting (`names_forgetting`) or asks to forget
(`asks_to_forget`). `asks_to_forget` reads all five messages above, and not `Merk dir, dass ich
nichts vergesse.`

## What to do

1. Add these forms to a case set with the stored rows, and calls naming the noun, the subject
   phrase and the stored value; count the refused calls on rows the message asks to delete.
2. Candidate: no call word check on a message `asks_to_forget` reads. Replay the two families,
   the generator and the recorded losing calls (none on a message naming forgetting): no call
   that lost a row may run.
3. A seeded live draw before it ships: the first message above after a stored card, and `Merk
   dir, dass mein Hund Bello heißt.` after `Merk dir, dass mein Hund Rex heißt.`, every card
   approved, counting old rows deleted and new facts stored.

## History

- 2026-11-25: filed by the audit of the night's forget commits, from a probe of the shipped check.
