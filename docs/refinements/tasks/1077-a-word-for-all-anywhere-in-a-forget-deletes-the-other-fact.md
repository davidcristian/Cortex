# A word for all anywhere in a forget deletes the other fact

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`_apart` in `forget_unnamed.py` returns false when any word of the message is in `_EVERY`, so
`unnamed` keeps nothing and the card lists every row holding the value. With a bike lock row and
a shed padlock row both holding 7319, `Forget my bike lock code 7319.` keeps the shed row, but
`Forget my bike lock code 7319, keep everything else.`, `..., that's all.`, `Forget all about my
bike lock code 7319.`, `Oublie le code de mon vélo 7319, c'est tout.` and `Vergiss 7319, mein Hund
ist tot.` keep nothing. `Vergiss den Fahrradcode 7319, alles andere bleibt.` and `Olvida el código
de la bici 7319, eso es todo.` keep nothing too, through the message naming no word of either row
([readings](../../readings/forget-shared-number.md#audit-probes-of-the-keep-reader-2026-11-09)).
The destructive card's safe direction is to keep rows. In one live draw of the `keep everything
else` message the cortex called with the text `bike lock`, which reaches no value, so the card
listed only the bike row; how often a call names the value on such a message is not measured.

## What to do

1. Write near misses first: `forget it all`, `forget 7319 everywhere`, `that's all`, `keep
   everything else`, `all about`, and `tot` as German for dead.
2. Read a word of `_EVERY` only where it quantifies the forget (beside the verb or the value),
   never in a closing clause or one that asks to keep, and replay every recorded draw message in
   `docs/readings/` through the old and new reader.

## History

- 2026-11-09: filed from the audit probes of the keep reader.
