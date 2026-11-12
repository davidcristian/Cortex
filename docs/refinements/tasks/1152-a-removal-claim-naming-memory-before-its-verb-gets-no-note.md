# A removal claim naming memory before its verb gets no note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

On 2026-11-12 build A of the
[readings](../../readings/forget-keep-no-call.md#the-note-what-was-drawn) answered
`Forget everything but my card.` with no forget call and the reply `I have ensured that only your
card number (4111 1111 1111 4242) is kept in my memory; all other information has been cleared.`,
with no note, while the gym row was stored. `claims_forgotten` (`forget_claim.py`) reads a
removal verb only when a memory word follows it, and here `memory` comes first. On a message with
a keep clause `UNCALLED_FORGET_NOTE` now follows such a reply; on a forget with no keep clause,
such as `Forget my gym code.`, the same reply would still get no note.

## What to do

1. Prefer extending the note that is true on every turn it reaches over widening the claim
   reader: write rows and a rule for `UNCALLED_FORGET_NOTE` on any message that asks to forget and
   made no forget call, with near misses (`Don't forget ...`, a statement about forgetting) as
   tests first and a replay of the recorded forget strings.

## History

- 2026-11-12: filed from the build A draws of the note on a forget with a keep clause and no call.
