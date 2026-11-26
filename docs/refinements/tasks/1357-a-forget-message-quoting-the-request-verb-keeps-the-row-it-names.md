# A forget message quoting the request verb keeps the row it names

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

Over the request verb family, forget messages quoting a form of the verb every stored request
opens with beside a row word, such as `Forget what you remember about my card.`, `Olvida lo que
recuerdas de mi tarjeta.` or `Uită ce ai ținut minte despre cardul.`, 1,652 of 2,184 rows asked
to delete are kept: 384 of 648 in English, 252 of 384 in French, 318 in German, 326 in Spanish
and 372 in Romanian ([readings](../../readings/forget-request-verb.md)). The card refuses most of
these calls and deletes nothing, which is the safe direction. Where the verb form is the
request's own word (`remember`, `minte`), it names every row as a whole word, which `_apart`
(`forget_keep_named.py`) does not read.

## What to do

1. Find which reader refuses `Forget what you remember about my card.` with the call text
   `4242`, and `Olvida lo que recuerdas de mi tarjeta.` with `4242`.
2. Make a word every stored request holds name no row there too, replayed over the family in
   `~/.cache/cortex-run/2026-11-26/x0/` (`rvgen.py`) and the other case sets so no row is newly
   listed, or decline with the count of rows it leaves.

## History

- 2026-11-26: filed from the replay of `_apart`, which keeps these counts unchanged.
