# A removal promised for later reads as a removal done

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`says_forgotten` in `numbers_left_claim.py` reads a removal the reply promises for later as one
done. Unit calls on 2026-11-09: `I will delete it.`, `I'll remove it from my memory.`, `It will be
deleted.`, `Il sera supprimé.`, `Es wird gelöscht.`, `Será borrado.` and `Va fi șters.` all
return `True`. After a turn whose approved forget deleted rows, such a reply gets no count note,
so the person is not told that rows were already deleted. This is the reply note's unsafe
direction, whose safe direction is to show.

## What to do

1. Write near misses as tests first: `I deleted it and it will not come back.`, `Il a été
   supprimé.` and `Es wurde gelöscht.` still read as a removal.
2. Read a future marker before the removal word in its clause (`will`, `'ll`, `going to`,
   `sera`, `wird`, `werde`, `será`, `va fi`, `voi`) as an offer, then replay every recorded reply
   string through the old and new reader.

## History

- 2026-11-09: filed from unit calls while reading conditions and abilities before a removal as
  an offer (`probe-future.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot17/`).
