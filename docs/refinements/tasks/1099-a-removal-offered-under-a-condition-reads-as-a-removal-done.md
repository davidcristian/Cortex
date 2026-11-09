# A removal offered under a condition reads as a removal done

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`says_forgotten` in `numbers_left_claim.py` reads `_REMOVED` with only a negation before it in the
clause as a hedge, so a reply that offers a removal under a condition or as an ability reads as one
done. Unit calls on 2026-11-09: `Poate fi șters dacă vrei.`, `Dacă vrei, poate fi șters.`, `Peut
être supprimé si tu veux.` and `Kann gelöscht werden, wenn du willst.` all return `True`. After a
turn whose approved forget deleted rows, such a reply gets no count note, so the person is not told
that rows were deleted. This is the reply note's unsafe direction.

## What to do

1. Write near misses as tests first: `Amintirea a fost ștearsă.`, `Il a été supprimé.` and `Sie
   wurde gelöscht.` still read as a removal, and a condition after the clause (`Am șters codul,
   dacă vrei să știi.`) is still read.
2. Read a condition or ability word in the sentence (`dacă`, `poate`, `si`, `peut`, `wenn`,
   `kann`, `puede`) as a hedge for `_REMOVED`, then replay every recorded reply string
   through the old and new reader.

## History

- 2026-11-09: filed from unit calls while widening the Romanian removal forms (`probe3.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot15/`).
